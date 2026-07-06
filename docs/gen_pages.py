"""Generate the docs site from each model's config + knowledge graph.

Run automatically by mkdocs at build time via the ``gen-files`` plugin (see
``mkdocs.yml``). For every shipped model this emits one rich page — generated
API/schema reference plus the model's knowledge-graph prose — and a catalog
index. Top-level prose pages (Philosophy / Contributing / Future work) are
mirrored from the single-source root Markdown so they never drift.

Nothing here is committed: the whole ``docs/models/`` tree is virtual, rebuilt on
every ``mkdocs build``, so the docs can never go stale relative to the code.
"""

from __future__ import annotations

import importlib
import logging
import re
import sys
from pathlib import Path
from typing import Any

import mkdocs_gen_files
import yaml
from mkdocs.structure.files import InclusionLevel

sys.path.insert(0, str(Path(__file__).parent))

import _docgen as dg  # noqa: E402

log = logging.getLogger("mkdocs.gen_pages")

REPO = Path(__file__).resolve().parent.parent
MODELS_DIR = REPO / "models"
# ``dummy`` is the model *template* (unresolved placeholder prose), so it is
# render-skipped here. NOTE: a second, divergent discovery copy lives in
# ``tooling/check_schema_docs.py`` — it keeps ``dummy`` so the template's schema
# stays guarded. The two SKIP sets should be factored into one shared
# ``discover_models(skip=...)`` helper (deferred de-duplication, see FIX_PLAN S14).
SKIP = {"commons", "dummy", "__pycache__"}

# Cross-links between the top-level prose pages resolve to their in-site page;
# anything else relative becomes a GitHub blob URL.
ROOT_PAGE_MAP = {
    "PHILOSOPHY.md": "philosophy.md",
    "CONTRIBUTING.md": "contributing.md",
    "FUTURE_WORK.md": "future-work.md",
    "README.md": "index.md",
}
# Link map used when embedding a model's own knowledge-graph prose. Top-level
# prose pages resolve to their in-site page (one directory up). A model page
# concatenates that model's README / MODEL.md / BIOLOGY.md into the "Usage" /
# "Architecture & training" / "Biology" sections, so the model's own "see also"
# cross-links resolve to the matching in-page anchor instead of bouncing off-site
# to GitHub for content that is the next section down on the same page.
MODEL_PAGE_MAP = {
    **{k: "../" + v for k, v in ROOT_PAGE_MAP.items() if k != "README.md"},
    "README.md": "#usage",
    "MODEL.md": "#architecture-training",
    "BIOLOGY.md": "#biology",
}


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _load_yaml(path: Path) -> dict[str, Any]:
    text = _read(path)
    if not text:
        return {}
    try:
        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        log.warning("could not parse %s", path)
        return {}


def _first_paragraph(md: str) -> str:
    para: list[str] = []
    for line in md.split("\n"):
        s = line.strip()
        if s.startswith("#") or s.startswith("<") or s.startswith(">"):
            if para:
                break
            continue
        if not s:
            if para:
                break
            continue
        para.append(s)
    return " ".join(para)


def _one_liner(md: str) -> str:
    """Return the authored one-line summary from a README's leading blockquote.

    Every README states its summary as a Markdown blockquote
    (``> **One-line summary**: ...``), which ``_first_paragraph`` skips — so the
    tagline would otherwise fall through to the verbose Overview paragraph. Pull
    that first blockquote out (stripping the ``>`` markers and the
    ``**One-line summary**:`` lead-in); fall back to the first body paragraph
    when no blockquote is present. HTML comments are stripped first so a stray
    template comment can't be mistaken for the summary.
    """
    quote: list[str] = []
    for line in dg.strip_html_comments(md).split("\n"):
        s = line.strip()
        if s.startswith(">"):
            quote.append(s.lstrip(">").strip())
            continue
        if quote:  # the leading blockquote just ended
            break
        if s.startswith("#") or not s:
            continue
        break  # body content before any blockquote -> none present
    one = " ".join(q for q in quote if q)
    for lead in ("**One-line summary**:", "One-line summary:"):
        if one.startswith(lead):
            one = one[len(lead) :].strip()
            break
    return one or _first_paragraph(md)


def _bullets(items: list[Any]) -> str:
    return "\n".join(f"- {str(i).strip()}" for i in items if str(i).strip())


def _gpu(spec: Any) -> str:
    gpu = getattr(spec, "gpu", None)
    return str(getattr(gpu, "value", gpu)) if gpu else "CPU"


# --------------------------------------------------------------------------- #
# page sections
# --------------------------------------------------------------------------- #


def _badges(fam: Any, src: dict[str, Any]) -> str:
    lic = (src.get("license") or {}).get("type") or "see sources"
    mol = ", ".join(src.get("molecule_types") or []) or "—"
    tasks = ", ".join(src.get("tasks") or []) or "—"
    actions = ", ".join(f"`{a.name}`" for a in fam.action_schemas)
    nvar = len(fam.resolved_variants)
    return (
        f"**License:** {lic} · **Molecules:** {mol} · **Tasks:** {tasks}\n\n"
        f"**Actions:** {actions} · **Variants:** {nvar}"
    )


def _at_a_glance(cmp: dict[str, Any], known: set[str]) -> str:
    if not cmp:
        return ""
    out = ["## At a glance", ""]
    if cmp.get("use_when"):
        out += ["**Use it when**", "", _bullets(cmp["use_when"]), ""]
    if cmp.get("strengths"):
        out += ['???+ success "Strengths"', "", _indent(_bullets(cmp["strengths"])), ""]
    if cmp.get("weaknesses"):
        out += [
            '???+ warning "Limitations"',
            "",
            _indent(_bullets(cmp["weaknesses"])),
            "",
        ]
    if cmp.get("dont_use_when"):
        out += [
            '???+ failure "Reach for something else when"',
            "",
            _indent(_bullets(cmp["dont_use_when"])),
            "",
        ]
    alts = cmp.get("alternatives") or []
    if alts:
        rows = [
            "**Alternatives**",
            "",
            "| Model | Better when | Worse when |",
            "|-------|-------------|------------|",
        ]
        for a in alts:
            slug = str(a.get("model", "") or "").strip()
            # Link to the sibling model page when the alternative ships here;
            # otherwise keep it as a plain code span (no dead link).
            model_cell = f"[{slug}]({slug}.md)" if slug in known else f"`{slug}`"
            rows.append(
                f"| {model_cell} | {dg._esc(str(a.get('when_better','') or ''))} "
                f"| {dg._esc(str(a.get('when_worse','') or ''))} |"
            )
        out += rows + [""]
    return "\n".join(out)


def _indent(text: str) -> str:
    return "\n".join("    " + ln if ln else "" for ln in text.split("\n"))


# The `bh serve` local catalog serves the API on this same-origin base by
# default (see cli/serve.py). A deployed gateway has its own https URL — see
# the HTTP API page.
SERVE_BASE_URL = "http://127.0.0.1:8000"


def _api(fam: Any) -> str:
    out = ["## API & schema", ""]
    variants = fam.resolved_variants
    if len(variants) > 1 or (variants and variants[0].name):
        out += [
            "**Variants**",
            "",
            "| Variant | Endpoint slug | GPU | CPU | Memory |",
            "|---------|---------------|-----|-----|--------|",
        ]
        for v in variants:
            spec = v.modal_resource_spec
            raw_mem = getattr(spec, "memory", None)
            mem = (
                f"{raw_mem / 1024:.0f} GB" if isinstance(raw_mem, int | float) else "—"
            )
            out.append(
                f"| {v.name or '—'} | `{v.public_endpoint_slug}` | {_gpu(spec)} "
                f"| {getattr(spec, 'cpu', '—')} | {mem} |"
            )
        out.append("")

    # Use the first resolved variant's slug for the worked examples — a real,
    # deployable endpoint slug (also listed in the Variants table above).
    example_slug = variants[0].public_endpoint_slug if variants else fam.base_model_slug

    out += [
        "Call an action with `POST /api/v1/{slug}/{action}` — the request envelope is "
        '`{"items": [...], "params": {...}}` and a success returns `{"results": [...]}`. '
        "See the [HTTP API](../api.md) page for the base URL, error shape, and full "
        "contract.",
        "",
    ]

    for a in fam.action_schemas:
        out += [f"### `{a.name}`", ""]
        out += ["**Call it**", ""]
        try:
            body = dg.example_request(a.request_schema)
        except Exception as exc:  # noqa: BLE001 - never let one schema break the build
            log.warning("example body for %s.%s failed: %s", example_slug, a.name, exc)
            body = {"items": [{}]}
        out += [dg.curl_snippet(SERVE_BASE_URL, example_slug, a.name, body), ""]
        out += [f"**Request** — `{a.request_schema.__name__}`", ""]
        out += [dg.render_schema_md(a.request_schema), ""]
        out += [f"**Response** — `{a.response_schema.__name__}`", ""]
        out += [dg.render_schema_md(a.response_schema), ""]
    return "\n".join(out)


# README sections that are dropped from the rendered per-model page (they remain
# in the repo README for GitHub browsers). Each is either a flat duplicate of a
# generated block (API & schema / Sources & license), a duplicate of MODEL.md, or
# contributor-only QA ceremony. Matched case-insensitively on the heading text; the
# heading and its whole body (through the next same-or-higher heading) are removed.
# See .planning/final-review/readme-section-curation.md.
README_DENY_SECTIONS = {
    "actions",
    "actions & endpoints",
    "actions / endpoints",
    "endpoints",
    "model variants",
    "resource requirements",
    "license",
    "references",
    "references & citations",
    "performance & benchmarks",
    "implementation notes",
    "implementation verification",
}


def _prose(
    title: str,
    md: str | None,
    base_dir: str,
    deny_sections: set[str] | None = None,
) -> str:
    if not md:
        return ""
    return (
        f"## {title}\n\n" + dg.embed(md, base_dir, MODEL_PAGE_MAP, deny_sections) + "\n"
    )


def _license_line(lic: dict[str, Any]) -> str:
    line = f"**License:** {lic.get('type', '—')}"
    if lic.get("url"):
        line += f" ([text]({lic['url']}))"
    if lic.get("notes"):
        line += f" — {lic['notes']}"
    return line


# An arXiv identifier: new-style ``2301.12345`` or old-style ``math/0211159``.
# Guard the arXiv link so a DOI mistakenly parked in the ``arxiv`` field can't
# render as a dead arxiv.org/abs/<doi> link.
_ARXIV_ID = re.compile(r"\d{4}\.\d{4,5}|\w+/\d+")


def _paper_line(p: dict[str, Any]) -> str:
    links = []
    if p.get("doi"):
        links.append(f"[DOI](https://doi.org/{p['doi']})")
    arxiv = str(p.get("arxiv") or "").strip()
    if arxiv and _ARXIV_ID.fullmatch(arxiv):
        links.append(f"[arXiv](https://arxiv.org/abs/{arxiv})")
    suffix = f" — {p['venue']}" if p.get("venue") else ""
    linktxt = (" · " + " ".join(links)) if links else ""
    return f"- *{str(p.get('title', '')).strip()}*{suffix}{linktxt}"


def _sources(src: dict[str, Any], readme: str | None = None) -> str:
    # The README's hand-written ``References & Citations`` section is dropped from
    # the page (see README_DENY_SECTIONS), so lift its BibTeX here — it is the one
    # part of that section humans want and the generated block otherwise lacks.
    bibtex = dg.extract_bibtex(readme) if readme else []
    if not src and not bibtex:
        return ""
    out = ["## Sources & license", ""]
    lic = src.get("license") or {}
    if lic:
        out += [_license_line(lic), ""]
    papers = src.get("primary_papers") or []
    if papers:
        out += ["**Papers**", "", *[_paper_line(p) for p in papers], ""]
    repos = [r for r in (src.get("source_repos") or []) if r.get("url")]
    if repos:
        out += ["**Source repositories**", ""]
        out += [f"- {r.get('type', 'repo')}: <{r['url']}>" for r in repos]
        out.append("")
    if bibtex:
        out += ["**Cite**", ""]
        for entry in bibtex:
            out += ["```bibtex", entry, "```", ""]
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #


def _model_page(name: str, known: set[str]) -> tuple[str, str] | None:
    try:
        cfg = importlib.import_module(f"models.{name}.config")
        fam = cfg.MODEL_FAMILY
    except Exception as exc:  # noqa: BLE001
        log.warning("skipping %s: cannot import config (%s)", name, exc)
        return None
    d = MODELS_DIR / name
    src = _load_yaml(d / "sources.yaml")
    cmp = _load_yaml(d / "comparison.yaml")
    readme = _read(d / "README.md")

    title = fam.display_name or name
    parts = [f"# {title}", ""]
    if readme:
        tag = _one_liner(readme)
        if tag:
            parts += [f"*{tag}*", ""]
    parts += [_badges(fam, src), ""]
    for block in (
        _at_a_glance(cmp, known),
        _api(fam),
        _prose("Usage", readme, f"models/{name}", README_DENY_SECTIONS),
        _prose("Architecture & training", _read(d / "MODEL.md"), f"models/{name}"),
        _prose("Biology", _read(d / "BIOLOGY.md"), f"models/{name}"),
        _sources(src, readme),
    ):
        if block:
            parts += [block, ""]
    return title, "\n".join(parts)


def _catalog_row(name: str) -> str | None:
    try:
        fam = importlib.import_module(f"models.{name}.config").MODEL_FAMILY
    except Exception:  # noqa: BLE001
        return None
    src = _load_yaml(MODELS_DIR / name / "sources.yaml")
    lic = (src.get("license") or {}).get("type") or "—"
    mol = ", ".join(src.get("molecule_types") or []) or "—"
    tasks = ", ".join(src.get("tasks") or []) or "—"
    actions = ", ".join(f"`{a.name}`" for a in fam.action_schemas)
    variants = ", ".join(f"`{v.public_endpoint_slug}`" for v in fam.resolved_variants)
    disp = fam.display_name or name
    return f"| [{disp}]({name}.md) | {mol} | {tasks} | {actions} | {variants} | {lic} |"


def _discover() -> list[str]:
    return sorted(
        p.name
        for p in MODELS_DIR.iterdir()
        if p.is_dir() and p.name not in SKIP and (p / "config.py").exists()
    )


# HTTP status per stable error `code`, sourced from the decorator's ERROR_MAP
# (models/commons/core/decorator.py). Kept as a small literal here so the docs
# build never has to import the decorator (which pulls in modal).
_ERROR_HTTP: dict[str, int] = {
    "user.error": 400,
    "user.validation": 400,
    "user.unsupported_option": 400,
    "user.resource_not_found": 404,
    "system.model_execution": 500,
    "system.error": 500,
}

# Display order for the typed-error table: user-facing branch first, then system.
_ERROR_ORDER = [
    "UserError",
    "ValidationError400",
    "UnsupportedOptionError",
    "ResourceNotFoundError",
    "ServerError",
    "ModelExecutionError",
]


def _docstring_summary(cls: type) -> str:
    """First non-empty line of a class docstring, collapsed to one line."""
    for line in (cls.__doc__ or "").strip().split("\n"):
        s = line.strip()
        if s:
            return s
    return ""


def _errors_page() -> str:
    """Generate the Errors reference page from the typed-error hierarchy."""
    from models.commons.core import error as errmod

    out = [
        "# Errors",
        "",
        "Every failed request returns a structured JSON body with the same shape, and "
        "the HTTP status equals the body's `status_code`. Agents branch on the stable, "
        "machine-readable `code` (a dotted `<domain>.<reason>` string) rather than "
        "parsing prose.",
        "",
        "```json",
        "{",
        '  "detail": "A human-readable message.",',
        '  "errors": [],',
        '  "status_code": 400,',
        '  "code": "user.validation"',
        "}",
        "```",
        "",
        "## Typed errors",
        "",
        "These are the codes a caller can rely on. User-branch errors carry the "
        "message verbatim (a caller mistake); system-branch errors are sanitized "
        "before they reach you.",
        "",
        "| Error | `code` | HTTP | Meaning |",
        "|-------|--------|------|---------|",
    ]
    for cls_name in _ERROR_ORDER:
        cls = getattr(errmod, cls_name, None)
        if cls is None:
            continue
        code = getattr(cls, "code", None) or "—"
        status = _ERROR_HTTP.get(code, "—")
        meaning = dg._esc(_docstring_summary(cls))
        out.append(f"| `{cls_name}` | `{code}` | {status} | {meaning} |")
    out += [
        "",
        "## Other responses",
        "",
        "- **`422` — schema validation.** A malformed body (missing/extra field, wrong "
        "type) is rejected before the model runs. `code` is `null`; per-field details "
        "are listed under `errors`.",
        "- **`5xx` — unexpected failure.** Any error not mapped above returns a "
        "sanitized `500` with `code` `null` (or the raised `code` when available); "
        "filesystem paths and tokens are stripped from the message.",
        "- **Gateway transport.** The gateway itself returns `404` when the target "
        "model is not deployed, `503` when the model backend is unreachable, and `504` "
        "when model execution times out.",
        "",
    ]
    return "\n".join(out)


def _mirror_root(src_name: str, dest: str) -> None:
    md = _read(REPO / src_name)
    if md is None:
        log.warning("root doc %s missing", src_name)
        return
    with mkdocs_gen_files.open(dest, "w") as f:
        f.write(dg.rewrite_links(md, "", ROOT_PAGE_MAP))


def main() -> None:
    names = _discover()
    known = set(names)  # slugs that have a sibling page (for Alternatives links)
    titles: dict[str, str] = {}
    for name in names:
        page = _model_page(name, known)
        if not page:
            continue
        titles[name], body = page
        with mkdocs_gen_files.open(f"models/{name}.md", "w") as f:
            f.write(body)

    # Catalog index
    rows = [r for r in (_catalog_row(n) for n in names if n in titles) if r]
    catalog = [
        "# Model catalog",
        "",
        f"{len(rows)} models, each with a uniform layout, the same action verbs, and a "
        "machine-readable knowledge graph. Pick a model below for its API schema, "
        "when-to-use guidance, architecture, and license.",
        "",
        "| Model | Molecules | Tasks | Actions | Variants (endpoint slugs) | License |",
        "|-------|-----------|-------|---------|---------------------------|---------|",
        *rows,
        "",
    ]
    with mkdocs_gen_files.open("models/index.md", "w") as f:
        f.write("\n".join(catalog))

    # literate-nav summary for the Models section
    summary = ["- [Catalog](index.md)"]
    for name in names:
        if name in titles:
            summary.append(f"- [{titles[name]}]({name}.md)")
    with mkdocs_gen_files.open("models/SUMMARY.md", "w") as f:
        f.write("\n".join(summary) + "\n")
    # literate-nav consumes SUMMARY.md to build the Models section, but MkDocs
    # would otherwise also render it as a standalone "SUMMARY" page (and index it
    # for search). `exclude_docs` can't catch it — literate-nav marks it
    # NOT_IN_NAV before MkDocs re-applies exclusions — so mark the generated file
    # EXCLUDED directly: literate-nav still reads its contents for the nav, but
    # it is no longer built as a page.
    editor = mkdocs_gen_files.FilesEditor.current()
    summary_file = editor.files.get_file_from_path("models/SUMMARY.md")
    if summary_file is not None:
        summary_file.inclusion = InclusionLevel.EXCLUDED

    # Errors reference (generated from the typed-error hierarchy)
    with mkdocs_gen_files.open("errors.md", "w") as f:
        f.write(_errors_page())

    # Top-level prose mirrored from the single-source root Markdown
    _mirror_root("PHILOSOPHY.md", "philosophy.md")
    _mirror_root("CONTRIBUTING.md", "contributing.md")
    _mirror_root("FUTURE_WORK.md", "future-work.md")

    log.info("generated docs for %d models", len(titles))


main()
