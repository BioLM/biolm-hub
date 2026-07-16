"""Pure, config-driven helpers for composing model pipelines over the knowledge graph.

Everything here is a plain function of :class:`~gateway.model_discovery.ModelMapper` plus the shared
knowledge loader — no MCP, no Modal, no network — so it is trivially unit-testable and keeps the
server module thin. Three concerns live here:

- **Graph traversal** — ``alternatives_for`` / ``complements_for`` surface a model's ``alternatives``
  and ``complements`` edges (from ``comparison.yaml``), and ``suggest_pipeline`` follows the
  ``complements`` edges into an ordered, *deterministic* chain an agent can refine.
- **The compose prompt** — ``build_compose_prompt`` seeds an agent with the capability vocabulary and
  a catalog summary and asks it to draft a probe-then-compose plan.
- **OpenAPI** — ``build_openapi_spec`` generates the gateway's full OpenAPI document in-process (no
  running gateway), lazily importing FastAPI so the ``[mcp]`` extra stays free of the ``[serve]`` deps.

The output models are the structured payloads the compose tools/resources return; they mirror
:mod:`gateway.mcp.catalog`'s style.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field

from gateway.mcp import catalog as cat
from gateway.model_discovery import ModelMapper
from models.commons.catalog.knowledge import (
    Alternative,
    Complement,
    load_model_knowledge_for_slug,
)
from models.commons.core.logging import get_logger

if TYPE_CHECKING:
    from gateway.mcp.catalog import CatalogSnapshot

logger = get_logger(__name__)

# A pipeline is a *starting point*, not a solver — cap the chain so a densely-connected
# complements graph can't produce a runaway plan. Truncation is reported (and logged) so the
# agent knows to keep probing beyond the suggested steps.
_MAX_PIPELINE_STEPS = 5


class AlternativesResult(BaseModel):
    """A model's competing alternatives, with when-better / when-worse notes."""

    slug: str
    alternatives: list[Alternative] = Field(default_factory=list)


class ComplementsResult(BaseModel):
    """A model's complements — models it composes with in a pipeline."""

    slug: str
    complements: list[Complement] = Field(default_factory=list)


class PipelineStep(BaseModel):
    """One step of a suggested pipeline: which model, its role, and why it's here."""

    slug: str
    role: str
    why: str


class PipelineSuggestion(BaseModel):
    """A transparent, heuristic pipeline: an ordered chain of steps plus how it was built."""

    goal: str
    steps: list[PipelineStep] = Field(default_factory=list)
    rationale: str
    truncated: bool = False


def alternatives_for(base: str) -> AlternativesResult:
    """The ``alternatives`` edges for a base model slug (already resolved by the caller)."""
    knowledge = load_model_knowledge_for_slug(base)
    return AlternativesResult(slug=base, alternatives=knowledge.alternatives)


def complements_for(base: str) -> ComplementsResult:
    """The ``complements`` edges for a base model slug (already resolved by the caller)."""
    knowledge = load_model_knowledge_for_slug(base)
    return ComplementsResult(slug=base, complements=knowledge.complements)


def _next_complement(
    mapper: ModelMapper, base: str, visited: set[str]
) -> Optional[tuple[str, Optional[str]]]:
    """First ``complement`` edge of ``base`` that resolves to an unvisited catalog model.

    Deterministic: complements are followed in the order they appear in ``comparison.yaml``.
    Returns ``(next_base_slug, workflow)`` or ``None`` when the chain can't be extended.
    """
    for comp in load_model_knowledge_for_slug(base).complements:
        if not comp.model:
            continue
        nxt = cat.resolve_base_slug(mapper, comp.model)
        if nxt is not None and nxt not in visited:
            return nxt, comp.workflow
    return None


def suggest_pipeline(
    mapper: ModelMapper,
    snapshot: CatalogSnapshot,
    goal: str,
    max_steps: int = _MAX_PIPELINE_STEPS,
) -> PipelineSuggestion:
    """Draft a deterministic, explainable pipeline for a free-text goal.

    A transparent heuristic — **not** an LLM call: it seeds the chain with the top keyword match
    for ``goal`` (via :func:`gateway.mcp.catalog.search_cards`), then walks each model's
    ``complements`` edges (in file order) to append downstream steps. The chain is capped at
    ``max_steps``; if more edges remain the result is flagged ``truncated`` and the truncation is
    logged. Treat the output as a starting point to refine — verify every step with
    ``get_model_schema`` before invoking.
    """
    ranked = cat.search_cards(snapshot, goal)
    if not ranked:
        return PipelineSuggestion(
            goal=goal,
            steps=[],
            rationale=(
                "No catalog models matched the goal keywords. Broaden the terms, or call "
                "search_models / list_models with a molecule/task filter to browse candidates."
            ),
        )

    seed = ranked[0].slug
    seed_card = ranked[0]
    steps = [
        PipelineStep(
            slug=seed,
            role="primary",
            why=seed_card.one_liner
            or f"Top keyword match in the catalog for '{goal}'.",
        )
    ]
    visited = {seed}
    frontier = seed
    truncated = False

    while True:
        if len(steps) >= max_steps:
            truncated = _next_complement(mapper, frontier, visited) is not None
            if truncated:
                logger.info(
                    "suggest_pipeline: capped chain at %d steps for goal %r",
                    max_steps,
                    goal,
                )
            break
        nxt = _next_complement(mapper, frontier, visited)
        if nxt is None:
            break
        next_slug, workflow = nxt
        steps.append(
            PipelineStep(
                slug=next_slug,
                role="complement",
                why=workflow
                or "Complements the previous step (per its knowledge-graph complements edge).",
            )
        )
        visited.add(next_slug)
        frontier = next_slug

    rationale = (
        "Heuristic starting point (not an LLM plan): seeded from the top keyword match for the "
        "goal, then following each model's `complements` edges in the knowledge graph, in file "
        "order. Read get_model_knowledge for each step and verify get_model_schema before "
        "invoking; treat this as a draft to refine, not a finished plan."
    )
    return PipelineSuggestion(
        goal=goal, steps=steps, rationale=rationale, truncated=truncated
    )


def build_compose_prompt(
    snapshot: CatalogSnapshot, capabilities: cat.Capabilities, goal: str
) -> str:
    """Seed an agent to draft a probe-then-compose plan for ``goal``.

    Returns a self-contained instruction that hands the agent the capability vocabulary and a
    compact catalog summary, then asks it to probe (search → knowledge → schema) and compose an
    ordered pipeline. Pure text — the MCP prompt wrapper in the server just returns this.
    """
    catalog_lines = "\n".join(
        f"- {card.slug} ({card.display_name}): {card.one_liner or 'no summary'}"
        for card in snapshot.cards
    )
    return f"""\
You are composing a pipeline over the biolm-hub catalog of open biological ML models to achieve
this goal:

    {goal}

Capability vocabulary (the exact axes to filter on):
- molecules: {', '.join(capabilities.molecules)}
- tasks: {', '.join(capabilities.tasks)}
- actions: {', '.join(capabilities.actions)}

Catalog (slug — display name — one-liner):
{catalog_lines}

Draft a plan by probing before you commit:
1. `search_models` (with a molecule/task filter) to find candidate models for each sub-goal.
2. `get_model_knowledge` on the front-runners — read when-to-use / when-NOT, and especially the
   `complements` edges: they tell you which models chain together and in what order.
3. Order the chosen models into a pipeline; for each, note the action it runs and why it's there.
4. `get_model_schema` for every step to confirm the exact request shape before you run anything.

`suggest_pipeline` will give you a deterministic first draft to react to. Return an ordered list of
{{slug, action, role, why}} steps, then the open questions you'd resolve before invoking.
"""


def build_openapi_spec(
    mapper: ModelMapper, base_slug: Optional[str] = None
) -> dict[str, Any]:
    """Generate the gateway's OpenAPI document in-process (no running gateway needed).

    Builds the FastAPI gateway app from the same config-driven mapper and returns ``app.openapi()``.
    FastAPI lives in the ``[serve]`` extra (not ``[mcp]``), so it is imported lazily and a missing
    install is turned into a clean, actionable :class:`ValueError` rather than an import stack trace.

    When ``base_slug`` is given (already resolved to a base by the caller), the ``paths`` are sliced
    to that family's variant routes. Only ``paths`` is filtered — ``info``/``components`` are left
    intact, so the sliced document is still self-describing.
    """
    try:
        from gateway.routing import build_gateway_app
    except ImportError as e:
        raise ValueError(
            "get_openapi needs the [serve] extra: pip install 'biolm-hub[serve]'"
        ) from e

    spec: dict[str, Any] = build_gateway_app(mapper, use_cache=False).openapi()
    if base_slug is None:
        return spec

    prefixes = tuple(
        f"/api/v1/{variant}/"
        for variant, info in mapper.get_all_variant_mappings().items()
        if info["base_model_slug"] == base_slug
    )
    paths = spec.get("paths", {})
    spec["paths"] = {
        path: item for path, item in paths.items() if path.startswith(prefixes)
    }
    return spec
