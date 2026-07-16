"""Pure, config-driven builders for the MCP server's tools and resources.

Everything here is a plain function of :class:`~gateway.model_discovery.ModelMapper` plus the shared
knowledge loader — no MCP, no Modal, no network — so it is trivially unit-testable and keeps the
server module thin. The output models are the structured payloads the MCP tools/resources return.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from gateway.model_discovery import ModelMapper
from models.commons.catalog.knowledge import load_model_knowledge_for_slug
from models.commons.model.schema import ModelActions
from models.commons.model.tag import (
    Architecture,
    InputModality,
    InputMolecule,
    OutputModality,
    Task,
)


class ModelCard(BaseModel):
    """A compact, catalog-level summary of one model family."""

    slug: str
    display_name: str
    one_liner: Optional[str] = None
    molecules: list[str] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    variants: list[str] = Field(default_factory=list)
    license: Optional[str] = None


class ActionSchema(BaseModel):
    """Request + response JSON Schema for a single model action."""

    action: str
    request_schema: dict[str, Any]
    response_schema: dict[str, Any]


class ModelSchemas(BaseModel):
    """All (or one) action schemas for a model."""

    slug: str
    actions: list[ActionSchema] = Field(default_factory=list)


class Capabilities(BaseModel):
    """The catalog's controlled vocabulary — the exact axes an agent can search on."""

    molecules: list[str]
    tasks: list[str]
    input_modalities: list[str]
    output_modalities: list[str]
    architectures: list[str]
    actions: list[str]


class CatalogSnapshot(BaseModel):
    """The catalog listing plus a per-model search blob, built once at server startup."""

    cards: list[ModelCard]
    # slug -> lowercased searchable text. Internal to search; not returned by any tool.
    search_text: dict[str, str] = Field(default_factory=dict)


def resolve_base_slug(mapper: ModelMapper, slug: str) -> Optional[str]:
    """Resolve a base or variant slug to its base model slug, or None if unknown."""
    if slug in mapper.get_all_registered_models():
        return slug
    info = mapper.get_variant_info(slug)
    return str(info["base_model_slug"]) if info else None


def _variants_for(mapper: ModelMapper, base: str) -> list[str]:
    return sorted(
        slug
        for slug, info in mapper.get_all_variant_mappings().items()
        if info["base_model_slug"] == base
    )


def _actions_for(mapper: ModelMapper, base: str) -> list[str]:
    return sorted(
        action for action, _req, _res in mapper.get_all_actions_for_model(base)
    )


def _card_and_text(mapper: ModelMapper, base: str) -> tuple[ModelCard, str]:
    family = mapper.get_model_family(base)
    kg = load_model_knowledge_for_slug(base)
    molecules = [m.value for m in family.tags.input_molecule] if family else []
    tasks = [t.value for t in family.tags.task] if family else []
    card = ModelCard(
        slug=base,
        display_name=family.display_name if family else base,
        one_liner=kg.one_liner,
        molecules=molecules,
        tasks=tasks,
        actions=_actions_for(mapper, base),
        variants=_variants_for(mapper, base),
        license=kg.license.type if kg.license else None,
    )
    search_text = " ".join(
        [
            base,
            card.display_name,
            kg.one_liner or "",
            " ".join(molecules),
            " ".join(tasks),
            " ".join(kg.use_when),
            " ".join(kg.strengths),
        ]
    ).lower()
    return card, search_text


def build_snapshot(mapper: ModelMapper) -> CatalogSnapshot:
    """Build the catalog listing + search index once (config + KG files are static at runtime)."""
    cards: list[ModelCard] = []
    search_text: dict[str, str] = {}
    for base in sorted(mapper.get_all_registered_models()):
        card, text = _card_and_text(mapper, base)
        cards.append(card)
        search_text[base] = text
    return CatalogSnapshot(cards=cards, search_text=search_text)


def build_capabilities() -> Capabilities:
    """The controlled vocabulary an agent uses to filter the catalog."""
    return Capabilities(
        molecules=[m.value for m in InputMolecule],
        tasks=[t.value for t in Task],
        input_modalities=[m.value for m in InputModality],
        output_modalities=[m.value for m in OutputModality],
        architectures=[a.value for a in Architecture],
        actions=[a.value for a in ModelActions],
    )


def build_model_schemas(
    mapper: ModelMapper, base: str, action: Optional[str] = None
) -> ModelSchemas:
    """Request/response JSON Schemas for a model's actions (all, or one via ``action``)."""
    schemas: list[ActionSchema] = []
    for name, req, res in mapper.get_all_actions_for_model(base):
        if action and name != action:
            continue
        schemas.append(
            ActionSchema(
                action=name,
                request_schema=req.model_json_schema(),
                response_schema=res.model_json_schema(),
            )
        )
    return ModelSchemas(slug=base, actions=sorted(schemas, key=lambda s: s.action))


def search_cards(
    snapshot: CatalogSnapshot,
    query: Optional[str] = None,
    molecule: Optional[str] = None,
    task: Optional[str] = None,
    action: Optional[str] = None,
) -> list[ModelCard]:
    """Filter by capability, then (if a query is given) keyword-rank over each model's search blob."""

    def keep(card: ModelCard) -> bool:
        if molecule and molecule not in card.molecules:
            return False
        if task and task not in card.tasks:
            return False
        if action and action not in card.actions:
            return False
        return True

    filtered = [card for card in snapshot.cards if keep(card)]
    if not query:
        return filtered

    terms = [term for term in query.lower().split() if term]
    scored: list[tuple[int, ModelCard]] = []
    for card in filtered:
        text = snapshot.search_text.get(card.slug, "")
        score = sum(1 for term in terms if term in text)
        if score:
            scored.append((score, card))
    scored.sort(key=lambda item: (-item[0], item[1].slug))
    return [card for _score, card in scored]
