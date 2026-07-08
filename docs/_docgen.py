"""Pure rendering helpers for the docs site generator.

Kept free of any ``mkdocs_gen_files`` import so the logic is unit-testable on its
own; ``docs/gen_pages.py`` imports these and handles the mkdocs build wiring.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any, get_args, get_origin

from pydantic import BaseModel

GITHUB_BLOB = "https://github.com/BioLM/biolm-hub/blob/main"

_MISSING = object()


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


def _annotation_models(ann: Any) -> Iterator[Any]:
    """Yield every ``BaseModel`` subclass referenced by a type annotation.

    Recurses through generics (``list[X]``, ``Optional[X]``, ``dict[str, X]``,
    unions) so nested request/response models are all discovered.
    """
    if get_origin(ann) is None:
        if isinstance(ann, type) and issubclass(ann, BaseModel):
            yield ann
        return
    for arg in get_args(ann):
        yield from _annotation_models(arg)


def _reachable_models(
    model_cls: Any, acc: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Map ``__name__`` -> class for ``model_cls`` and every model reachable via its fields.

    The keys line up with the ``$defs`` names in ``model_json_schema()``, so a
    ``$defs`` block can be paired back to the Pydantic class that produced it.
    """
    acc = {} if acc is None else acc
    if not (isinstance(model_cls, type) and issubclass(model_cls, BaseModel)):
        return acc
    if model_cls.__name__ in acc:
        return acc
    acc[model_cls.__name__] = model_cls
    for field in model_cls.model_fields.values():
        for sub in _annotation_models(field.annotation):
            _reachable_models(sub, acc)
    return acc


def _factory_default_json(field: Any) -> Any:
    """Resolve a field's ``default_factory`` to a JSON-native value (or ``_MISSING``).

    ``model_json_schema()`` omits the default for a ``default_factory`` field, so
    resolve it here. A nested-model default (e.g. a ``params`` object) is skipped —
    its own fields already carry the real defaults, and dumping the whole object as
    a "default" would just be noise.
    """
    factory = getattr(field, "default_factory", None)
    if factory is None:
        return _MISSING
    try:
        value = factory()
    except TypeError:
        # Pydantic 2.10+ may pass validated data to the factory; such a
        # data-dependent default has no single static value to show.
        return _MISSING
    if isinstance(value, BaseModel):
        return _MISSING
    try:
        return json.loads(
            json.dumps(value, default=lambda o: getattr(o, "value", str(o)))
        )
    except (TypeError, ValueError):
        return _MISSING


def _inject_factory_defaults(block: dict[str, Any], model_cls: Any) -> None:
    """Populate ``default`` on schema properties whose field uses a ``default_factory``.

    Mutates ``block["properties"]`` in place so the Constraints/default cell renders
    a value (e.g. esm2 ``repr_layers`` -> ``[-1]``, ``include`` -> ``["mean"]``).
    """
    props = block.get("properties")
    if not props:
        return
    for fname, field in getattr(model_cls, "model_fields", {}).items():
        prop = props.get(fname) or props.get(getattr(field, "alias", None) or fname)
        if prop is None or "default" in prop:
            continue
        value = _factory_default_json(field)
        if value is not _MISSING:
            prop["default"] = value


def render_schema_md(schema_cls: Any) -> str:
    """Render one Pydantic model's JSON schema as Markdown (tables + raw JSON)."""
    js = schema_cls.model_json_schema()
    # model_json_schema() drops default_factory defaults; resolve and inject them
    # (both on the root model and each nested $defs block) so the tables show them.
    models = _reachable_models(schema_cls)
    _inject_factory_defaults(js, schema_cls)
    for def_name, def_block in js.get("$defs", {}).items():
        def_cls = models.get(def_name)
        if def_cls is not None:
            _inject_factory_defaults(def_block, def_cls)

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
        out.append('???+ note "Nested types"\n')
        body = "\n".join(nested)
        out.append("\n".join("    " + ln if ln else "" for ln in body.split("\n")))

    raw = json.dumps(js, indent=2)
    out.append(
        '???+ abstract "Raw JSON Schema"\n\n'
        + "\n".join("    " + ln for ln in (["```json", *raw.split("\n"), "```"]))
    )
    return "\n\n".join(out)


# --------------------------------------------------------------------------- #
# Minimal example request bodies (for the per-action calling contract)
# --------------------------------------------------------------------------- #


def _str_example(name: str) -> str:
    """A readable placeholder string for a leaf field, keyed off its name."""
    n = name.lower()
    if "smiles" in n:
        return "CC(=O)Oc1ccccc1C(=O)O"
    if "pdb" in n:
        return "<contents of a .pdb file>"
    if "cif" in n or "mmcif" in n:
        return "<contents of a .cif file>"
    if "msa" in n:
        return ">seq1\nMKTAYIAK\n>seq2\nMKTAYIAK"
    if any(k in n for k in ("heavy", "light", "chain", "sequence", "seq")):
        return "MKTAYIAKQRQISFVKSHFSRQLEERLGLIE"
    return "string"


def _example_scalar(node: dict[str, Any], name: str) -> Any:
    """A placeholder value for a scalar JSON-schema leaf (honouring any minimum)."""
    kind = node.get("type")
    if kind in ("integer", "number"):
        for key in ("minimum", "exclusiveMinimum"):
            if key in node:
                bump = 1 if (kind == "integer" and key == "exclusiveMinimum") else 0
                return int(node[key]) + bump if kind == "integer" else node[key]
        return 1 if kind == "integer" else 0.1
    if kind == "boolean":
        return False
    if kind == "string":
        return _str_example(name)
    return None


def _example_node(node: dict[str, Any], defs: dict[str, Any], name: str = "") -> Any:
    """Build a minimal JSON-native example for one JSON-schema node.

    Follows ``$ref``/``anyOf``/``allOf``, honours an explicit ``default``/``enum``,
    and only fills *required* object properties so the body stays minimal.
    """
    if "$ref" in node:
        return _example_node(defs.get(_ref_name(node["$ref"]), {}), defs, name)
    if "anyOf" in node:
        opts = [o for o in node["anyOf"] if o.get("type") != "null"] or node["anyOf"]
        return _example_node(opts[0], defs, name)
    if "allOf" in node and len(node["allOf"]) == 1:
        return _example_node(node["allOf"][0], defs, name)
    if "default" in node:
        return node["default"]
    if "enum" in node:
        return node["enum"][0]
    kind = node.get("type")
    if kind == "object" or "properties" in node:
        props = node.get("properties", {})
        required = set(node.get("required", []))
        return {
            key: _example_node(prop, defs, key)
            for key, prop in props.items()
            if key in required
        }
    if kind == "array":
        return [_example_node(node.get("items", {}), defs, name)]
    return _example_scalar(node, name)


def example_request(schema_cls: Any) -> Any:
    """A minimal, JSON-native example request body for a request schema."""
    js = schema_cls.model_json_schema()
    return _example_node(js, js.get("$defs", {}))


def curl_snippet(base_url: str, slug: str, action: str, body: Any) -> str:
    """A copy-pasteable ``curl`` block for ``POST {base_url}/api/v1/{slug}/{action}``."""
    body_json = json.dumps(body, indent=2)
    return "\n".join(
        [
            "```bash",
            f"curl -X POST {base_url}/api/v1/{slug}/{action} \\",
            '  -H "Content-Type: application/json" \\',
            "  -d '" + body_json + "'",
            "```",
        ]
    )


# --------------------------------------------------------------------------- #
# Markdown transforms for embedded knowledge-graph prose
# --------------------------------------------------------------------------- #

_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_LINK = re.compile(r"(!?)\[([^\]]*)\]\(([^)]+)\)")
_SEE_ALSO = re.compile(r"^\s*[*_]*\s*See also:", re.IGNORECASE)
_BIBTEX_FENCE = re.compile(r"```bibtex\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def strip_sections(md: str, deny: set[str]) -> str:
    """Drop whole sections whose ATX heading text is in ``deny`` (case-insensitive).

    Removes the matched heading line plus everything beneath it up to (but not
    including) the next heading at the *same or a higher* level, so nested
    subsections are carried out with their parent. Fence-aware: a ``#`` inside a
    code fence is never mistaken for a heading. ``deny`` holds lowercased,
    stripped heading texts (e.g. ``"license"``, ``"references & citations"``).
    """
    if not deny:
        return md
    out: list[str] = []
    in_fence = False
    skip_level: int | None = None  # level of the section currently being dropped
    for line in md.split("\n"):
        is_fence = bool(_FENCE.match(line))
        if is_fence:
            in_fence = not in_fence
        heading = None if (is_fence or in_fence) else _HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            if skip_level is not None and level <= skip_level:
                skip_level = None  # a same-or-higher heading ends the dropped run
            if skip_level is None and heading.group(2).strip().lower() in deny:
                skip_level = level  # drop this heading and its body
                continue
        if skip_level is None:
            out.append(line)
    return "\n".join(out)


def extract_bibtex(md: str) -> list[str]:
    """Return the body of each ```bibtex code fence in a doc, in order.

    Used to lift a README's citation into the generated ``Sources & license``
    block so the hand-written ``References`` section can be dropped from the
    rendered page without losing the BibTeX humans want.
    """
    return [m.group(1).rstrip() for m in _BIBTEX_FENCE.finditer(md)]


def strip_see_also(md: str) -> str:
    """Drop the trailing ``See also: README.md | MODEL.md | ...`` cross-link footer.

    Each knowledge-graph doc ends with an italic footer linking to its sibling
    files. Concatenated into a single model page those become same-page anchor
    links that leak raw filenames as link text, so drop the footer line entirely.
    """
    return "\n".join(ln for ln in md.split("\n") if not _SEE_ALSO.match(ln))


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


def embed(
    md: str,
    base_dir: str,
    page_map: dict[str, str] | None = None,
    deny_sections: set[str] | None = None,
) -> str:
    """Prepare an embedded knowledge-graph doc for inclusion in a model page.

    ``deny_sections`` (lowercased heading texts) are stripped whole — heading and
    body — *before* heading demotion, so redundant/internal README sections never
    reach the rendered page.
    """
    cleaned = strip_see_also(strip_html_comments(md))
    if deny_sections:
        cleaned = strip_sections(cleaned, deny_sections)
    return rewrite_links(demote_headings(cleaned, by=1), base_dir, page_map)
