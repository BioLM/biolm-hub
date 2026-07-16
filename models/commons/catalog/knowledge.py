"""Shared, typed loader for a model's knowledge graph.

Every model directory carries a small knowledge graph:

- ``sources.yaml`` — license, molecule/task tags, primary & applied papers, source repos.
- ``comparison.yaml`` — strengths, weaknesses, use-when / don't-use-when, alternatives, complements.
- ``README.md`` / ``MODEL.md`` / ``BIOLOGY.md`` — prose (overview, architecture, benchmarks,
  applied use-cases, biological background, citations).

This module turns those five files into one typed :class:`ModelKnowledge` object. The structured
YAML becomes typed fields; the prose is parsed into an identified, heading-keyed **section tree**
(``documents``) so every subsection (Overview, Strengths & Limitations, Applied Use Cases, …) is
individually addressable. Absent files/fields are tolerated but recorded in ``missing``.

The same object serializes two ways from one source, so JSON and Markdown never drift:

- ``ModelKnowledge`` (or ``.model_dump()``) — the structured JSON payload (the default).
- :meth:`ModelKnowledge.to_markdown` — one normalized Markdown document.

It is deliberately **config-free** (no Modal, no ``ModelFamily`` import): a pure function of the
files on disk, so it loads and tests offline and runs inside a model container. Consumers: the
gateway ``/knowledge`` route, the per-model ``knowledge_graph()`` container method, and the MCP server.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from models.commons.core.logging import get_logger
from models.commons.model.naming import MODELS_DIR

logger = get_logger(__name__)

# The prose documents, in the order they appear in a normalized render. The key (label) is what
# ``documents`` is keyed by; the value is the on-disk filename.
_PROSE_FILES: tuple[tuple[str, str], ...] = (
    ("README", "README.md"),
    ("MODEL", "MODEL.md"),
    ("BIOLOGY", "BIOLOGY.md"),
)

# Files a complete knowledge graph is expected to contain (used to populate ``missing``).
_EXPECTED_FILES: tuple[str, ...] = (
    "sources.yaml",
    "comparison.yaml",
    "README.md",
    "MODEL.md",
    "BIOLOGY.md",
)


class LicenseInfo(BaseModel):
    """A model's license, from ``sources.yaml``'s ``license`` block."""

    model_config = ConfigDict(extra="allow")

    type: str | None = None
    url: str | None = None
    notes: str | None = None


class Paper(BaseModel):
    """A primary or applied-literature reference from ``sources.yaml``."""

    model_config = ConfigDict(extra="allow")

    title: str | None = None
    year: int | str | None = None
    doi: str | None = None
    arxiv: str | None = None
    url: str | None = None
    venue: str | None = None
    authors: list[str] = Field(default_factory=list)


class SourceRepo(BaseModel):
    """A source repository (github / huggingface / …) from ``sources.yaml``."""

    model_config = ConfigDict(extra="allow")

    type: str | None = None
    url: str | None = None


class Alternative(BaseModel):
    """A competing model and when it is better/worse, from ``comparison.yaml``."""

    model_config = ConfigDict(extra="allow", protected_namespaces=())

    model: str | None = None
    when_better: str | None = None
    when_worse: str | None = None


class Complement(BaseModel):
    """A model that composes with this one in a pipeline, from ``comparison.yaml``."""

    model_config = ConfigDict(extra="allow", protected_namespaces=())

    model: str | None = None
    workflow: str | None = None
    example_protocol: str | None = None


class DocSection(BaseModel):
    """One identified subsection of a prose document, with its nested subsections.

    ``level`` is the Markdown heading depth (1–6); ``body`` is the verbatim text directly under
    the heading (before the first child heading); ``subsections`` holds deeper headings.
    """

    title: str
    level: int
    body: str = ""
    subsections: list[DocSection] = Field(default_factory=list)


class ModelKnowledge(BaseModel):
    """The full, typed knowledge graph for a single model."""

    slug: str
    display_name: str
    one_liner: str | None = None

    # From sources.yaml
    license: LicenseInfo | None = None
    molecule_types: list[str] = Field(default_factory=list)
    applicable_to: list[str] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    primary_papers: list[Paper] = Field(default_factory=list)
    applied_literature: list[Paper] = Field(default_factory=list)
    source_repos: list[SourceRepo] = Field(default_factory=list)

    # From comparison.yaml
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    use_when: list[str] = Field(default_factory=list)
    dont_use_when: list[str] = Field(default_factory=list)
    alternatives: list[Alternative] = Field(default_factory=list)
    complements: list[Complement] = Field(default_factory=list)

    # Parsed prose, keyed by document label (README / MODEL / BIOLOGY) → its section tree.
    documents: dict[str, list[DocSection]] = Field(default_factory=dict)

    # Expected knowledge-graph files that were absent (a completeness signal).
    missing: list[str] = Field(default_factory=list)

    def to_markdown(self) -> str:
        """Render one normalized Markdown document from this typed object."""
        return _render_markdown(self)


# --- Markdown parsing -------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})(.*)$")
_ONE_LINER_RE = re.compile(
    r"^>\s*\*\*One-line summary\*\*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE
)


def _clean_body(lines: list[str]) -> str:
    """Drop leading/trailing blank lines from a section body, preserving interior text."""
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[start:end])


def parse_markdown_sections(text: str) -> list[DocSection]:
    """Parse a Markdown string into a tree of :class:`DocSection` by heading level.

    Fenced code blocks (``` / ~~~) are skipped so ``#``-prefixed lines inside code (e.g. a
    ``# comment`` in a Python example) are never mistaken for headings. If the document has a
    single top-level heading (the usual ``# Title``), it is unwrapped so the returned list is the
    meaningful subsections rather than one title node.
    """
    lines = text.splitlines()
    entries: list[tuple[int, str, list[str]]] = []
    preamble: list[str] = []
    current: list[str] | None = None
    in_fence = False
    fence_char = ""
    fence_len = 0

    for line in lines:
        stripped = line.lstrip()
        fence = _FENCE_RE.match(stripped)
        if fence:
            run, info = fence.group(1), fence.group(2).strip()
            if not in_fence:
                # An opener may carry an info string (```python); remember its char + length.
                in_fence, fence_char, fence_len = True, run[0], len(run)
            elif run[0] == fence_char and len(run) >= fence_len and not info:
                # A closer is a bare run of the same char, at least as long as the opener.
                in_fence, fence_char, fence_len = False, "", 0
            (preamble if current is None else current).append(line)
            continue

        if not in_fence:
            heading = _HEADING_RE.match(line)
            if heading:
                entries.append((len(heading.group(1)), heading.group(2).strip(), []))
                current = entries[-1][2]
                continue

        (preamble if current is None else current).append(line)

    roots: list[DocSection] = []
    stack: list[DocSection] = []
    for level, title, body_lines in entries:
        node = DocSection(title=title, level=level, body=_clean_body(body_lines))
        while stack and stack[-1].level >= level:
            stack.pop()
        (stack[-1].subsections if stack else roots).append(node)
        stack.append(node)

    if len(roots) == 1 and roots[0].level == 1 and roots[0].subsections:
        return roots[0].subsections
    return roots


def _extract_one_liner(readme_text: str) -> str | None:
    """Pull the ``> **One-line summary**: …`` tagline from a README, if present."""
    match = _ONE_LINER_RE.search(readme_text)
    return match.group(1).strip() if match else None


# --- Loading ----------------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file into a dict, returning ``{}`` for a missing, malformed, or non-mapping file.

    Tolerant by design: a syntactically broken ``sources.yaml`` / ``comparison.yaml`` in one model
    must not crash a catalog-wide load (e.g. the MCP server building its snapshot over every model).
    """
    if not path.exists():
        return {}
    try:
        loaded = yaml.safe_load(path.read_text())
    except yaml.YAMLError:
        logger.warning("Malformed YAML in %s; treating as empty.", path)
        return {}
    return loaded if isinstance(loaded, dict) else {}


def load_model_knowledge(model_dir: Path) -> ModelKnowledge:
    """Load the knowledge graph from a model directory into a typed :class:`ModelKnowledge`.

    Tolerant of missing files and fields: anything absent is recorded in ``missing`` and left at
    its default rather than raising, so a partially-documented model still loads.
    """
    sources = _load_yaml(model_dir / "sources.yaml")
    comparison = _load_yaml(model_dir / "comparison.yaml")

    documents: dict[str, list[DocSection]] = {}
    one_liner: str | None = None
    for label, filename in _PROSE_FILES:
        path = model_dir / filename
        if path.exists():
            content = path.read_text()
            documents[label] = parse_markdown_sections(content)
            if label == "README":
                one_liner = _extract_one_liner(content)
        else:
            documents[label] = []

    missing = [name for name in _EXPECTED_FILES if not (model_dir / name).exists()]

    return ModelKnowledge(
        slug=str(sources.get("model_slug") or model_dir.name),
        display_name=str(
            sources.get("display_name") or sources.get("model_slug") or model_dir.name
        ),
        one_liner=one_liner,
        license=sources.get("license"),
        molecule_types=sources.get("molecule_types") or [],
        applicable_to=sources.get("applicable_to") or [],
        tasks=sources.get("tasks") or [],
        primary_papers=sources.get("primary_papers") or [],
        applied_literature=sources.get("applied_literature") or [],
        source_repos=sources.get("source_repos") or [],
        strengths=comparison.get("strengths") or [],
        weaknesses=comparison.get("weaknesses") or [],
        use_when=comparison.get("use_when") or [],
        dont_use_when=comparison.get("dont_use_when") or [],
        alternatives=comparison.get("alternatives") or [],
        complements=comparison.get("complements") or [],
        documents=documents,
        missing=missing,
    )


def model_dir_for_slug(slug: str) -> Path:
    """Resolve a model slug to its directory in the repo tree.

    Base slugs use hyphens (``dna-chisel``) while directories use underscores (``dna_chisel``),
    so try the hyphen→underscore form first and fall back to the slug verbatim.
    """
    underscored = MODELS_DIR / slug.replace("-", "_")
    if underscored.exists():
        return underscored
    return MODELS_DIR / slug


def load_model_knowledge_for_slug(slug: str) -> ModelKnowledge:
    """Load a model's knowledge graph by slug, resolving ``models/<slug>/`` in the repo tree."""
    return load_model_knowledge(model_dir_for_slug(slug))


# --- Markdown rendering -----------------------------------------------------------------------


def _render_sections(sections: list[DocSection]) -> str:
    """Render a section tree back to Markdown, preserving heading levels and bodies."""
    parts: list[str] = []
    for section in sections:
        parts.append(f"{'#' * section.level} {section.title}")
        if section.body:
            parts.append(section.body)
        if section.subsections:
            parts.append(_render_sections(section.subsections))
    return "\n\n".join(part for part in parts if part)


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _render_meta(kg: ModelKnowledge) -> str | None:
    meta: list[str] = []
    if kg.license and kg.license.type:
        meta.append(f"- **License:** {kg.license.type}")
    if kg.molecule_types:
        meta.append(f"- **Molecule types:** {', '.join(kg.molecule_types)}")
    if kg.tasks:
        meta.append(f"- **Tasks:** {', '.join(kg.tasks)}")
    return "## Metadata\n\n" + "\n".join(meta) if meta else None


def _render_alternatives(kg: ModelKnowledge) -> str | None:
    if not kg.alternatives:
        return None
    lines = [
        f"- **{a.model or '?'}** — better when: {a.when_better or 'n/a'}; "
        f"worse when: {a.when_worse or 'n/a'}"
        for a in kg.alternatives
    ]
    return "## Alternatives\n\n" + "\n".join(lines)


def _render_complements(kg: ModelKnowledge) -> str | None:
    if not kg.complements:
        return None
    lines = [
        f"- **{c.model or '?'}** — {c.workflow or ''}".rstrip(" —")
        for c in kg.complements
    ]
    return "## Complements\n\n" + "\n".join(lines)


def _render_papers(kg: ModelKnowledge) -> str | None:
    papers = kg.primary_papers + kg.applied_literature
    if not papers:
        return None
    lines: list[str] = []
    for paper in papers:
        ref = paper.doi or paper.arxiv or paper.url or ""
        year = f" ({paper.year})" if paper.year else ""
        suffix = f" — {ref}" if ref else ""
        lines.append(f"- {paper.title or 'Untitled'}{year}{suffix}")
    return "## Papers\n\n" + "\n".join(lines)


def _render_prose(kg: ModelKnowledge) -> list[str]:
    blocks: list[str] = []
    for label, _filename in _PROSE_FILES:
        sections = kg.documents.get(label) or []
        if sections:
            blocks.append(f"---\n\n## {label}\n\n{_render_sections(sections)}")
    return blocks


def _render_markdown(kg: ModelKnowledge) -> str:
    """Assemble a single normalized Markdown document from a :class:`ModelKnowledge`."""
    blocks: list[str] = [f"# {kg.display_name}"]
    if kg.one_liner:
        blocks.append(f"> {kg.one_liner}")

    blocks.append(_render_meta(kg) or "")
    for heading, items in (
        ("Use when", kg.use_when),
        ("Don't use when", kg.dont_use_when),
        ("Strengths", kg.strengths),
        ("Weaknesses", kg.weaknesses),
    ):
        if items:
            blocks.append(f"## {heading}\n\n{_bullets(items)}")
    blocks.append(_render_alternatives(kg) or "")
    blocks.append(_render_complements(kg) or "")
    blocks.append(_render_papers(kg) or "")
    blocks.extend(_render_prose(kg))

    return "\n\n".join(block for block in blocks if block) + "\n"
