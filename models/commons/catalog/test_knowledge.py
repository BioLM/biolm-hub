"""Modal-free tests for the shared knowledge-graph loader.

Covers the Markdown section parser (incl. fenced-code safety), the typed loader against a real
model, graceful handling of an empty directory, and a uniformity sweep asserting every registered
model has a loadable knowledge graph — so adding a model can never silently break this surface.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway.model_discovery import get_model_mapper
from models.commons.catalog.knowledge import (
    ModelKnowledge,
    load_model_knowledge,
    load_model_knowledge_for_slug,
    parse_markdown_sections,
)

REGISTERED_SLUGS = sorted(get_model_mapper().get_all_registered_models())

_FENCED = """# Title

> **One-line summary**: A test model.

## Usage

```python
# Encode -- a comment inside a fence, NOT a heading
x = 1
```

## Limits

Body text.

### Detail

Nested body.
"""


def test_parser_unwraps_single_h1_and_nests() -> None:
    sections = parse_markdown_sections(_FENCED)
    titles = [s.title for s in sections]
    assert titles == ["Usage", "Limits"]
    limits = sections[1]
    assert [sub.title for sub in limits.subsections] == ["Detail"]
    assert limits.subsections[0].level == 3


def test_parser_ignores_headings_inside_code_fences() -> None:
    sections = parse_markdown_sections(_FENCED)
    all_titles = {s.title for s in sections} | {
        sub.title for s in sections for sub in s.subsections
    }
    assert "Encode -- a comment inside a fence, NOT a heading" not in all_titles
    # The fenced comment stays in the Usage section body, verbatim.
    assert "# Encode" in sections[0].body


def test_parser_language_tagged_fence_line_does_not_close_block() -> None:
    # A ```lang line INSIDE a bare fence must not close it (only a bare same-char run does), so a
    # heading-looking line between them stays fenced.
    text = "# T\n\n## Example\n\n```\n```python\n## still fenced\n```\n\n## After\n\nBody.\n"
    titles = [s.title for s in parse_markdown_sections(text)]
    assert titles == ["Example", "After"]
    assert "still fenced" not in titles


def test_model_source_dir_uses_slug_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # The knowledge_graph() container method resolves its model dir from the _BIOLM_MODEL_SLUG env
    # var the source layer bakes in (inspect/sys.modules are unreliable under Modal's __main__ runner).
    from models.commons.model.base import _model_source_dir
    from models.commons.model.naming import MODELS_DIR

    class _Local:
        pass

    monkeypatch.setenv("_BIOLM_MODEL_SLUG", "esm2")
    assert _model_source_dir(_Local) == MODELS_DIR / "esm2"
    # A hyphenated slug resolves to its underscore directory.
    monkeypatch.setenv("_BIOLM_MODEL_SLUG", "dna-chisel")
    assert _model_source_dir(_Local) == MODELS_DIR / "dna_chisel"


def test_loader_reads_a_real_model() -> None:
    kg = load_model_knowledge_for_slug("esm2")
    assert kg.slug == "esm2"
    assert kg.display_name == "ESM2"
    assert kg.one_liner and "protein language model" in kg.one_liner.lower()
    assert kg.license and kg.license.type == "MIT"
    assert kg.strengths and kg.weaknesses
    assert kg.use_when and kg.dont_use_when
    assert any(alt.model for alt in kg.alternatives)
    assert kg.primary_papers and kg.primary_papers[0].title
    readme_titles = {s.title for s in kg.documents["README"]}
    assert "Overview" in readme_titles
    assert kg.missing == []


def test_to_markdown_round_trips_key_content() -> None:
    kg = load_model_knowledge_for_slug("esm2")
    md = kg.to_markdown()
    assert md.startswith("# ESM2")
    assert "## Strengths" in md
    assert "## README" in md


def test_malformed_yaml_is_tolerated(tmp_path: Path) -> None:
    # A syntactically broken YAML file must not crash the load (one bad model can't take down a
    # catalog-wide build like the MCP server's snapshot).
    (tmp_path / "sources.yaml").write_text("model_slug: x\ntasks: [unclosed\n")
    kg = load_model_knowledge(tmp_path)
    assert isinstance(kg, ModelKnowledge)
    assert kg.tasks == []
    assert kg.strengths == []


def test_empty_directory_is_tolerated(tmp_path: Path) -> None:
    kg = load_model_knowledge(tmp_path)
    assert isinstance(kg, ModelKnowledge)
    assert kg.slug == tmp_path.name
    assert set(kg.documents) == {"README", "MODEL", "BIOLOGY"}
    assert len(kg.missing) == 5
    assert kg.strengths == []


@pytest.mark.parametrize("slug", REGISTERED_SLUGS)
def test_every_registered_model_has_loadable_knowledge(slug: str) -> None:
    kg = load_model_knowledge_for_slug(slug)
    assert kg.slug
    assert kg.display_name
    assert set(kg.documents) == {"README", "MODEL", "BIOLOGY"}
    # The hard-required KG files must all resolve; comparison.yaml is the only tolerated omission
    # (matching `bh kb validate`'s error-vs-warning split). This catches both the hyphen/underscore
    # slug→dir trap AND a model that forgets a knowledge file.
    assert set(kg.missing) <= {
        "comparison.yaml"
    }, f"{slug}: missing KG files {kg.missing}"
    assert kg.to_markdown().strip()
