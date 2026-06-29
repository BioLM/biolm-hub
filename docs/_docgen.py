"""Pure rendering helpers for the docs site generator.

Kept free of any ``mkdocs_gen_files`` import so the logic is unit-testable on its
own; ``docs/gen_pages.py`` imports these and handles the mkdocs build wiring.
"""

from __future__ import annotations

import re
from typing import Any

GITHUB_BLOB = "https://github.com/BioLM/biolm-models/blob/main"


# --------------------------------------------------------------------------- #
# JSON-schema -> Markdown
# --------------------------------------------------------------------------- #


def type_str(prop: dict[str, Any]) -> str:
    """A short, human-readable type for a JSON-schema property."""
    if "$ref" in prop:
        return _ref_name(prop["$ref"])
    if "anyOf" in prop:
        # e.g. an Optional field renders as ``X | null``.
        return " | ".join(type_str(p) for p in prop["anyOf"])
    if "allOf" in prop and len(prop["allOf"]) == 1:
        return type_str(prop["allOf"][0])
    if prop.get("type") == "array":
        items = prop.get("items")
        return f"list[{type_str(items)}]" if items else "list"
    if prop.get("type") == "null":
        return "null"
    if "enum" in prop:
        return prop.get("type", "enum")
    return str(prop.get("type", "object"))


def _ref_name(ref: str) -> str:
    return ref.split("/")[-1]


def constraints_str(prop: dict[str, Any], required: bool) -> str:
    """Render the constraints / default cell for a field."""
    bits: list[str] = []
    rng = {
        "minimum": "≥",
        "exclusiveMinimum": ">",
        "maximum": "≤",
        "exclusiveMaximum": "<",
    }
    for key, sym in rng.items():
        if key in prop:
            bits.append(f"{sym}{prop[key]}")
    if "minLength" in prop or "maxLength" in prop:
        lo = prop.get("minLength", "")
        hi = prop.get("maxLength", "")
        bits.append(f"len {lo}–{hi}")
    if "minItems" in prop or "maxItems" in prop:
        lo = prop.get("minItems", "")
        hi = prop.get("maxItems", "")
        bits.append(f"items {lo}–{hi}")
    if "pattern" in prop:
        bits.append(f"pattern `{prop['pattern']}`")
    if "enum" in prop:
        vals = ", ".join(f"`{v}`" for v in prop["enum"][:8])
        if len(prop["enum"]) > 8:
            vals += ", …"
        bits.append(f"one of {vals}")
    if not required and "default" in prop and prop["default"] not in (None, [], {}):
        bits.append(f"default `{_short(prop['default'])}`")
    return "; ".join(bits)


def _short(val: Any, limit: int = 40) -> str:
    s = str(val)
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _esc(text: str) -> str:
    """Escape a cell for a Markdown table."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _fields_table(block: dict[str, Any]) -> str:
    props = block.get("properties", {})
    if not props:
        return ""
    required = set(block.get("required", []))
    rows = [
        "| Field | Type | Required | Constraints | Description |",
        "|-------|------|----------|-------------|-------------|",
    ]
    for name, prop in props.items():
        is_req = name in required
        desc = _esc(str(prop.get("description", "")))
        rows.append(
            f"| `{name}` | {_esc(type_str(prop))} | "
            f"{'yes' if is_req else 'no'} | "
            f"{_esc(constraints_str(prop, is_req))} | {desc} |"
        )
    return "\n".join(rows)


def _enum_line(block: dict[str, Any]) -> str:
    vals = ", ".join(f"`{v}`" for v in block.get("enum", []))
    return f"Allowed values: {vals}"


def render_schema_md(schema_cls: Any) -> str:
    """Render one Pydantic model's JSON schema as Markdown (tables + raw JSON)."""
    import json

    js = schema_cls.model_json_schema()
    out: list[str] = []
    root = _fields_table(js)
    if root:
        out.append(root)
    elif not js.get("$defs"):
        out.append("_No fields._")

    defs = js.get("$defs", {})
    if defs:
        nested: list[str] = []
        for name, block in defs.items():
            nested.append(f"**`{name}`**")
            nested.append("")  # python-markdown needs a blank line before a table
            if "enum" in block:
                nested.append(_enum_line(block))
            else:
                tbl = _fields_table(block)
                nested.append(tbl if tbl else "_No fields._")
            nested.append("")
        out.append('??? note "Nested types"\n')
        body = "\n".join(nested)
        out.append("\n".join("    " + ln if ln else "" for ln in body.split("\n")))

    raw = json.dumps(js, indent=2)
    out.append(
        '??? abstract "Raw JSON Schema"\n\n'
        + "\n".join("    " + ln for ln in (["```json", *raw.split("\n"), "```"]))
    )
    return "\n\n".join(out)


# --------------------------------------------------------------------------- #
# Markdown transforms for embedded knowledge-graph prose
# --------------------------------------------------------------------------- #

_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_LINK = re.compile(r"(!?)\[([^\]]*)\]\(([^)]+)\)")


def demote_headings(md: str, by: int, strip_first_h1: bool = True) -> str:
    """Shift every ATX heading down ``by`` levels (capped at 6), fence-aware.

    Optionally drops the first level-1 heading (the embedded doc's title, which
    the page already provides via its section header).
    """
    out: list[str] = []
    in_fence = False
    dropped = False
    for line in md.split("\n"):
        if _FENCE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        m = _HEADING.match(line)
        if not m:
            out.append(line)
            continue
        level = len(m.group(1))
        if strip_first_h1 and level == 1 and not dropped:
            dropped = True
            continue
        new_level = min(level + by, 6)
        out.append(f"{'#' * new_level} {m.group(2)}")
    return "\n".join(out)


def rewrite_links(
    md: str, base_dir: str, page_map: dict[str, str] | None = None
) -> str:
    """Rewrite repo-relative links so the strict mkdocs build resolves them.

    ``base_dir`` is the source file's directory (POSIX, repo-relative). A target
    listed in ``page_map`` is rewritten to that in-site page; any other relative
    target becomes an absolute GitHub blob URL. Absolute/http/anchor/mail links
    are left untouched.
    """
    page_map = page_map or {}

    def repl(m: re.Match[str]) -> str:
        bang, text, target = m.group(1), m.group(2), m.group(3)
        anchor = ""
        if "#" in target and not target.startswith("#"):
            target, anchor = target.split("#", 1)
            anchor = "#" + anchor
        if (
            target.startswith(("http://", "https://", "mailto:", "/", "#"))
            or target == ""
        ):
            return m.group(0)
        key = target.lstrip("./")
        base = key.split("/")[-1]
        if key in page_map:
            return f"{bang}[{text}]({page_map[key]}{anchor})"
        if base in page_map:
            return f"{bang}[{text}]({page_map[base]}{anchor})"
        resolved = _resolve(base_dir, target)
        return f"{bang}[{text}]({GITHUB_BLOB}/{resolved}{anchor})"

    return _LINK.sub(repl, md)


def _resolve(base_dir: str, target: str) -> str:
    parts = [p for p in base_dir.split("/") if p] if base_dir else []
    for seg in target.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts:
                parts.pop()
        else:
            parts.append(seg)
    return "/".join(parts)


def strip_html_comments(md: str) -> str:
    """Drop HTML comments (internal authoring TODOs) but keep fenced code intact."""
    # Split on fenced code blocks (odd indices) and strip comments elsewhere.
    parts = re.split(r"(```.*?```|~~~.*?~~~)", md, flags=re.DOTALL)
    return "".join(
        part if i % 2 else re.sub(r"<!--.*?-->", "", part, flags=re.DOTALL)
        for i, part in enumerate(parts)
    )


def embed(md: str, base_dir: str, page_map: dict[str, str] | None = None) -> str:
    """Prepare an embedded knowledge-graph doc for inclusion in a model page."""
    return rewrite_links(
        demote_headings(strip_html_comments(md), by=1), base_dir, page_map
    )
