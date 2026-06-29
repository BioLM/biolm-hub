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
import sys
from pathlib import Path
from typing import Any

import mkdocs_gen_files
import yaml

sys.path.insert(0, str(Path(__file__).parent))

import _docgen as dg  # noqa: E402

log = logging.getLogger("mkdocs.gen_pages")

REPO = Path(__file__).resolve().parent.parent
MODELS_DIR = REPO / "models"
SKIP = {"commons", "dummy", "__pycache__"}

# Cross-links between the top-level prose pages resolve to their in-site page;
# anything else relative becomes a GitHub blob URL.
ROOT_PAGE_MAP = {
    "PHILOSOPHY.md": "philosophy.md",
    "CONTRIBUTING.md": "contributing.md",
    "FUTURE_WORK.md": "future-work.md",
    "README.md": "index.md",
}
# Same map, but from a model page (one directory deeper). README.md is excluded:
# a model's own "see also: README.md" link should go to that model's source on
# GitHub, not the site home page (ROOT_PAGE_MAP maps README.md -> the home page).
MODEL_PAGE_MAP = {
    k: "../" + v for k, v in ROOT_PAGE_MAP.items() if k != "README.md"
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


def _at_a_glance(cmp: dict[str, Any]) -> str:
    if not cmp:
        return ""
    out = ["## At a glance", ""]
    if cmp.get("use_when"):
        out += ["**Use it when**", "", _bullets(cmp["use_when"]), ""]
    if cmp.get("strengths"):
        out += ['??? success "Strengths"', "", _indent(_bullets(cmp["strengths"])), ""]
    if cmp.get("weaknesses"):
        out += ['??? warning "Limitations"', "", _indent(_bullets(cmp["weaknesses"])), ""]
    if cmp.get("dont_use_when"):
        out += [
            '??? failure "Reach for something else when"',
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
            rows.append(
                f"| `{a.get('model','')}` | {dg._esc(str(a.get('when_better','') or ''))} "
                f"| {dg._esc(str(a.get('when_worse','') or ''))} |"
            )
        out += rows + [""]
    return "\n".join(out)


def _indent(text: str) -> str:
    return "\n".join("    " + ln if ln else "" for ln in text.split("\n"))


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
                f"{raw_mem / 1024:.0f} GB"
                if isinstance(raw_mem, int | float)
                else "—"
            )
            out.append(
                f"| {v.name or '—'} | `{v.public_endpoint_slug}` | {_gpu(spec)} "
                f"| {getattr(spec, 'cpu', '—')} | {mem} |"
            )
        out.append("")
    for a in fam.action_schemas:
        out += [f"### `{a.name}`", ""]
        out += [f"**Request** — `{a.request_schema.__name__}`", ""]
        out += [dg.render_schema_md(a.request_schema), ""]
        out += [f"**Response** — `{a.response_schema.__name__}`", ""]
        out += [dg.render_schema_md(a.response_schema), ""]
    return "\n".join(out)


def _prose(title: str, md: str | None, base_dir: str) -> str:
    if not md:
        return ""
    return f"## {title}\n\n" + dg.embed(md, base_dir, MODEL_PAGE_MAP) + "\n"


def _license_line(lic: dict[str, Any]) -> str:
    line = f"**License:** {lic.get('type', '—')}"
    if lic.get("url"):
        line += f" ([text]({lic['url']}))"
    if lic.get("notes"):
        line += f" — {lic['notes']}"
    return line


def _paper_line(p: dict[str, Any]) -> str:
    links = []
    if p.get("doi"):
        links.append(f"[DOI](https://doi.org/{p['doi']})")
    if p.get("arxiv"):
        links.append(f"[arXiv](https://arxiv.org/abs/{p['arxiv']})")
    suffix = f" — {p['venue']}" if p.get("venue") else ""
    linktxt = (" · " + " ".join(links)) if links else ""
    return f"- *{str(p.get('title', '')).strip()}*{suffix}{linktxt}"


def _sources(src: dict[str, Any]) -> str:
    if not src:
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
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #


def _model_page(name: str) -> tuple[str, str] | None:
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
        tag = _first_paragraph(readme)
        if tag:
            parts += [f"*{tag}*", ""]
    parts += [_badges(fam, src), ""]
    for block in (
        _at_a_glance(cmp),
        _api(fam),
        _prose("Usage", readme, f"models/{name}"),
        _prose("Architecture & training", _read(d / "MODEL.md"), f"models/{name}"),
        _prose("Biology", _read(d / "BIOLOGY.md"), f"models/{name}"),
        _sources(src),
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
    disp = fam.display_name or name
    return f"| [{disp}]({name}.md) | {mol} | {tasks} | {actions} | {lic} |"


def _discover() -> list[str]:
    return sorted(
        p.name
        for p in MODELS_DIR.iterdir()
        if p.is_dir() and p.name not in SKIP and (p / "config.py").exists()
    )


def _mirror_root(src_name: str, dest: str) -> None:
    md = _read(REPO / src_name)
    if md is None:
        log.warning("root doc %s missing", src_name)
        return
    with mkdocs_gen_files.open(dest, "w") as f:
        f.write(dg.rewrite_links(md, "", ROOT_PAGE_MAP))


def main() -> None:
    names = _discover()
    titles: dict[str, str] = {}
    for name in names:
        page = _model_page(name)
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
        "| Model | Molecules | Tasks | Actions | License |",
        "|-------|-----------|-------|---------|---------|",
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

    # Top-level prose mirrored from the single-source root Markdown
    _mirror_root("PHILOSOPHY.md", "philosophy.md")
    _mirror_root("CONTRIBUTING.md", "contributing.md")
    _mirror_root("FUTURE_WORK.md", "future-work.md")

    log.info("generated docs for %d models", len(titles))


main()
