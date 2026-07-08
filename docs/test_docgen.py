"""Unit tests for the pure docs-site rendering helpers in ``_docgen``.

These cover the edge-case-heavy logic that gates the public site — fence-aware
heading demotion, link rewriting (in-page anchors / GitHub fallback / ``..``
resolution), HTML-comment stripping, and the JSON-schema -> Markdown table
render. None of it requires Modal or the network, so it runs in the unit tier.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel, Field

# ``docs/`` is not a package; make the sibling ``_docgen`` importable regardless
# of how pytest is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _docgen as dg  # noqa: E402

# --------------------------------------------------------------------------- #
# demote_headings (fence-aware)
# --------------------------------------------------------------------------- #


def test_demote_headings_shifts_and_strips_first_h1() -> None:
    out = dg.demote_headings("# Title\n\n## Section\n\ntext\n", by=1)
    assert "# Title" not in out  # the embedded doc's title is dropped
    assert "### Section" in out  # h2 -> h3


def test_demote_headings_keeps_h1_when_not_stripping() -> None:
    out = dg.demote_headings("# Title\n", by=1, strip_first_h1=False)
    assert out.strip() == "## Title"


def test_demote_headings_caps_at_level_six() -> None:
    out = dg.demote_headings("###### Deep\n", by=2, strip_first_h1=False)
    assert out.strip() == "###### Deep"


def test_demote_headings_is_fence_aware() -> None:
    md = "```\n# not a heading\n```\n\n## real\n"
    out = dg.demote_headings(md, by=1, strip_first_h1=False)
    assert "# not a heading" in out  # untouched inside the code fence
    assert "### real" in out


def test_demote_headings_fence_aware_with_tildes() -> None:
    md = "~~~\n## fenced\n~~~\n\n## real\n"
    out = dg.demote_headings(md, by=1, strip_first_h1=False)
    assert "## fenced" in out  # left alone inside the ~~~ fence
    assert "### real" in out


# --------------------------------------------------------------------------- #
# rewrite_links
# --------------------------------------------------------------------------- #


def test_rewrite_links_page_map_hit_to_in_page_anchor() -> None:
    out = dg.rewrite_links(
        "[a](MODEL.md)", "models/x", {"MODEL.md": "#architecture-training"}
    )
    assert out == "[a](#architecture-training)"


def test_rewrite_links_page_map_strips_dot_slash_prefix() -> None:
    out = dg.rewrite_links("[a](./MODEL.md)", "models/x", {"MODEL.md": "#arch"})
    assert out == "[a](#arch)"


def test_rewrite_links_relative_becomes_github_blob() -> None:
    out = dg.rewrite_links("[cfg](config.py)", "models/x")
    assert out == f"[cfg]({dg.GITHUB_BLOB}/models/x/config.py)"


def test_rewrite_links_resolves_parent_dir() -> None:
    out = dg.rewrite_links("[c](../commons/core.py)", "models/x")
    assert out == f"[c]({dg.GITHUB_BLOB}/models/commons/core.py)"


def test_rewrite_links_preserves_anchor_on_blob() -> None:
    out = dg.rewrite_links("[s](util.py#foo)", "models/x")
    assert out == f"[s]({dg.GITHUB_BLOB}/models/x/util.py#foo)"


def test_rewrite_links_keeps_image_bang() -> None:
    out = dg.rewrite_links("![d](diagram.png)", "models/x")
    assert out == f"![d]({dg.GITHUB_BLOB}/models/x/diagram.png)"


def test_rewrite_links_passes_through_absolute_and_anchor() -> None:
    for target in (
        "https://example.com",
        "http://x.io",
        "#section",
        "mailto:a@b.c",
        "/abs",
    ):
        src = f"[t]({target})"
        assert dg.rewrite_links(src, "models/x") == src


# --------------------------------------------------------------------------- #
# strip_html_comments
# --------------------------------------------------------------------------- #


def test_strip_html_comments_removes_inline_comment() -> None:
    assert "secret" not in dg.strip_html_comments("a <!-- secret --> b")


def test_strip_html_comments_multiline() -> None:
    out = dg.strip_html_comments("before\n<!--\nTODO: internal\n-->\nafter")
    assert "TODO" not in out
    assert "before" in out and "after" in out


def test_strip_html_comments_keeps_fenced_code() -> None:
    assert "keep me" in dg.strip_html_comments("```\n<!-- keep me -->\n```")


# --------------------------------------------------------------------------- #
# render_schema_md
# --------------------------------------------------------------------------- #


class _Tiny(BaseModel):
    seq: str = Field(..., description="An input sequence.", min_length=1)
    top_k: int = Field(5, description="How many to return.", ge=1, le=20)


def test_render_schema_md_table_and_constraints() -> None:
    md = dg.render_schema_md(_Tiny)
    assert "| Field | Type | Required | Constraints | Description |" in md
    assert "`seq`" in md and "An input sequence." in md
    assert "yes" in md  # seq is required
    assert "≥1" in md and "≤20" in md  # ge=1, le=20
    assert "default `5`" in md  # top_k default
    assert "Raw JSON Schema" in md  # collapsible always emitted


def test_render_schema_md_no_fields() -> None:
    class _Empty(BaseModel):
        pass

    assert "_No fields._" in dg.render_schema_md(_Empty)
