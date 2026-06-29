# Global Review — CLI (`bm`)

**Scope:** `cli/` — `main.py`, `setup.py`, `cache.py`, `serve.py`, `deploy.py`, `r2.py`, `kb.py`.
Dimension: UX, strictly-read-only `bm r2`, error handling, cross-command consistency, help text,
internal leakage, and the W10 Definition-of-Done.

## Summary

The CLI is in good overall shape. The W10 spine is real and well-executed: `bm setup` is genuinely
network-free and gives clear, actionable guidance; `bm cache` correctly models caching as a deploy-time
env flag; `bm serve` gates its heavy web deps behind a `[serve]` extra; and **`bm r2` has been
deliberately reduced to read-only** — W10 (`277ad2f`) stripped the upload/sync/delete commands and the
`download` command explicitly rejects `r2://` destinations with a clear message. That DoD item is met.

However, two launch-gating problems exist:

1. **`bm kb matrix` is dead** — it imports `models.scripts.generate_comparison_matrix`, a module that
   has *never* existed in this repo. The command crashes with `ModuleNotFoundError` on first use, and
   `test_kb.py` openly admits `matrix_cmd` is untested, so nothing caught it.
2. **The internal repo name "BioLM-Modal" is printed in the CLI's front-door help text** (the module
   docstring, the help blurb, and the root callback). The public package is `biolm-models` / CLI `bm`;
   "BioLM-Modal" is the internal repo's identity and the rubric lists `biolm-modal` as a 🔴 leak.

Beyond those: the hand-maintained `bm help` table duplicates Typer's auto-help and has already drifted
(the `kb` subcommands render under the wrong panel); `bm kb missing` points users at a non-existent
`kb_acquire.py` and surfaces an internal curation workflow that external users can't act on; `bm r2 cat`
has a latent UTF-8 chunk-boundary decode bug; and `deploy.py` is the lone module using raw `print()`
instead of the Rich `console` everything else uses. None of the read-only guarantees are violated.

---

## 🔴 Must-fix before launch

### 1. `bm kb matrix` imports a module that does not exist — command is dead
**Category:** correctness / broken public contract
**Location:** `cli/kb.py:360`
**Detail:** `matrix_cmd` does
`from models.scripts.generate_comparison_matrix import main as generate_main`, but there is no
`models/scripts/` directory anywhere in the repo (and it has never been committed — confirmed via
`git log --all`). Running `bm kb matrix` raises `ModuleNotFoundError: No module named 'models.scripts'`.
The command is advertised in `bm help` ("kb matrix → Generate MODEL_COMPARISON_MATRIX.md") and in the
command's own docstring/examples, so an external user following the docs hits an immediate crash. The
gap is invisible because `cli/test_kb.py:9` explicitly states `matrix_cmd` is *not* tested. `"scripts"`
is even in `kb.py`'s `SKIP_DIRS`, hinting the generator was expected to live under `models/scripts/` but
was never ported.
**Fix:** Either port the comparison-matrix generator into the repo (e.g. `models/scripts/` or
`tooling/`) and add a smoke test that actually invokes `matrix_cmd`, or remove `bm kb matrix` (and its
`bm help` row + docstring) until the generator ships. Whichever path, add a test that imports/executes
the command so a missing dependency fails CI.

### 2. Internal repo name "BioLM-Modal" leaked in user-facing CLI strings
**Category:** internal leakage / branding consistency
**Location:** `cli/main.py:16`, `cli/main.py:18`, `cli/main.py:47`
**Detail:** The module docstring (`BioLM-Modal Command Line Interface` / `…working with BioLM-Modal
models and infrastructure.`) and the root callback docstring (`BioLM-Modal is a platform for serving
BioLM models on Modal.`) name the product **BioLM-Modal** — the internal repo's identity. The rubric
classifies a `biolm-modal` internal-reference leak as 🔴, and model-level reviewers have treated the
same token as a launch blocker (e.g. `deepviscosity.md`). The public package/CLI is `biolm-models` /
`bm`, so this is both an internal-reference leak and a naming inconsistency, and it appears in the most
visible place possible — the CLI's `--help`/front door. (If the team formally adopts "BioLM-Modal" as a
public product name, downgrade to 🟠; as-is it contradicts the public package name.)
**Fix:** Replace with the public name, e.g. "BioLM Models CLI (`bm`)" / "command-line tools for
deploying and running BioLM models on Modal." Grep the CLI for any remaining `BioLM-Modal`.

---

## 🟠 Should-fix

### 3. `bm help` is a hand-maintained duplicate that has already drifted (kb subcommands in the wrong panel)
**Category:** consistency / 10x-simplicity / help text
**Location:** `cli/main.py:66-130` (bug at `cli/main.py:108-112`)
**Detail:** `display_cli_help` re-implements, by hand, a command table that Typer already generates from
the registered commands (`bm --help`, plus `no_args_is_help=True`). It will inevitably drift from the
real command set — and it already has: the five `kb …` rows at lines 108-112 are appended to
`commands_table` (the top-level "Commands" panel) *after* the `storage_table` is built, so `bm help`
renders `kb status`, `kb validate`, `kb sources`, `kb matrix`, `kb missing` jammed under "Commands"
alongside the six real top-level commands, with **no dedicated knowledge-base panel** — asymmetric with
the "Storage (read-only)" panel and misleading (they look like top-level commands). The table also omits
`cache status` and never shows options, so it under-documents the real surface.
**Fix:** Prefer deleting the custom `bm help`/`display_cli_help` and relying on Typer's auto-generated
help (rich-formatted, always in sync). If a curated landing page is desired, at minimum give `kb` its
own panel (mirroring Storage) by adding those rows to a dedicated `kb_table`, and add a test that the
panels match the registered command set.

### 4. `bm kb missing` references a non-existent `kb_acquire.py` and exposes an internal curation workflow
**Category:** internal leakage / dead reference / OSS-readiness
**Location:** `cli/kb.py:436` (and the workflow framing throughout `missing_cmd` / `_format_missing_report`)
**Detail:** The generated report instructs users to "Download PDF and run `kb_acquire.py --models
{slug}`", but `kb_acquire.py` exists nowhere in the repo (grep-confirmed) — it's internal acquisition
tooling that wasn't ported, so the instruction is dead. More broadly, the whole "papers missing from R2
/ Paywall — institutional access, SharedIt link, or author request / No Paper" report is an internal
PDF-curation process: external users have **read-only** access to the public bucket and cannot upload
PDFs, so the command's core action is not actionable for them.
**Fix:** Decide whether `bm kb missing` is contributor-facing. If kept, remove the `kb_acquire.py`
instruction (or port the script) and reword to a generic "this paper is not yet mirrored" status without
the internal acquisition-strategy language. If it's internal-only tooling, move it out of the shipped
`bm` surface (e.g. into `tooling/` not mounted on the public CLI).

### 5. `bm r2 cat` decodes each 1 MB chunk independently — corrupts multi-byte UTF-8 at chunk boundaries
**Category:** correctness
**Location:** `cli/r2.py:366-382` (`_stream_file_content`, line 372-373)
**Detail:** The stream loop does `text = chunk.decode("utf-8")` per 1 MB chunk. A multi-byte UTF-8
sequence that straddles a 1 MB boundary will fail to decode, raising `UnicodeDecodeError`, which the
code then misreports as "File contains binary data, cannot display as text" — i.e. a valid UTF-8 file
larger than 1 MB with non-ASCII content can be wrongly rejected. Today's documented use (small JSON test
fixtures) stays under the threshold, but the command is explicitly advertised for streaming/`less`, so
this is a latent correctness bug.
**Fix:** Use an incremental decoder:
`dec = codecs.getincrementaldecoder("utf-8")()`; write `dec.decode(chunk)` per chunk and
`dec.decode(b"", final=True)` at the end; only treat a true `UnicodeDecodeError` as binary.

### 6. `deploy.py` uses raw `print()` everywhere while the rest of the CLI uses Rich `console.print()`
**Category:** consistency / readability
**Location:** `cli/deploy.py` (≈30 `print(...)` calls, e.g. lines 42, 96, 132, 164, 205) vs. the Rich
`console` it imports but only uses in the `deploy_cmd` wrapper (lines 289, 292)
**Detail:** Every other CLI module renders through a Rich `Console`. `deploy.py` constructs
`console = Console()` but then prints almost all of its output with the builtin `print()`, so deploy
output is unstyled, Rich markup wouldn't render, and stream/TTY handling differs from the rest of the
suite. (It's not a lint error — `cli/**` is exempt from T20 in `pyproject.toml:153` — but it's a real
consistency/UX gap and makes the module read as ported-but-not-harmonized.) This is the kind of
plumbing difference the repo's uniformity north-star wants gone.
**Fix:** Route deploy output through `console.print` (the module already has `console`), or, if plain
stdout is intentional for subprocess-output passthrough, keep `print` only for the captured
child-process stdout/stderr and use `console.print` for the CLI's own status lines.

---

## 🟡 Nits

### 7. Hardcoded version string will drift from `pyproject.toml`
**Category:** maintainability
**Location:** `cli/main.py:31-34`
**Detail:** `print_version` prints `"BioLM CLI version 0.1.0"`; `pyproject.toml:3` independently declares
`version = "0.1.0"`. They match today but are two sources of truth.
**Fix:** `from importlib.metadata import version` and print `version("biolm-models")`.

### 8. `main.py` module docstring is placed after the imports — it's a dead string, not `__doc__`
**Category:** readability
**Location:** `cli/main.py:15-19`
**Detail:** The triple-quoted "BioLM-Modal Command Line Interface…" block sits below the import
statements, so it is a no-op expression, not the module docstring (`cli.main.__doc__` is `None`).
**Fix:** Move it above the imports (and fix the name per finding #2), or delete it.

### 9. `bm r2 cat` prints Rich markup through builtin `print` — user sees literal `[red]…[/red]`
**Category:** UX polish
**Location:** `cli/r2.py:378-379`
**Detail:** The binary-data error is emitted with `print("[red]Error: …[/red]", file=sys.stderr)`.
`print` doesn't interpret Rich markup, so the literal brackets are shown. (The other error prints in
`cat` correctly use plain text — only this one carries markup.)
**Fix:** Drop the markup (plain `print(..., file=sys.stderr)`) or route through `console.print`/a stderr
console.

### 10. `bm r2 download-outputs` uses a required `--model` option where peers use a positional argument
**Category:** consistency
**Location:** `cli/r2.py:579-583`
**Detail:** `download-outputs --model rf3` takes the model as a *required option*, whereas `kb sources
<model>`, `kb status <model>`, and `deploy <models>` take it positionally. Required options read as a
small UX inconsistency.
**Fix:** Make `model` a positional `typer.Argument`, matching the other model-scoped commands.

### 11. `deploy.py` optional params typed as non-optional
**Category:** typing / readability
**Location:** `cli/deploy.py:191` (`deploy_model(..., variant_spec: str = None)`); also untyped helpers
(`get_model_family`, `_get_variants_to_deploy`, `_deploy_variants`, `_print_deployment_summary`)
**Detail:** `variant_spec: str = None` should be `Optional[str]`; several helpers have no type hints,
unlike the rest of the typed CLI.
**Fix:** Annotate `Optional[str]` and add hints to the helpers for consistency with the codebase.

### 12. `bm r2 du` hand-rolls pagination instead of using a paginator like `ls`/`download`
**Category:** consistency / duplication
**Location:** `cli/r2.py:500-533`
**Detail:** `du` loops on `response["IsTruncated"]`/`NextContinuationToken` manually, whereas
`list_r2_objects` and `download_from_r2` use `get_paginator("list_objects_v2")`. Same operation, two
styles.
**Fix:** Use the paginator here too for one consistent listing pattern.

### 13. `bm kb missing --output` example targets a non-existent dir and won't create parents
**Category:** docs / minor correctness
**Location:** `cli/kb.py:483` (example) and `cli/kb.py:490` (`Path(output).write_text(report)`)
**Detail:** The example `bm kb missing --output models/scripts/MISSING_R2_PAPERS.md` writes into
`models/scripts/`, which doesn't exist; `Path.write_text` does not create parent directories, so it
raises `FileNotFoundError`. (Ties into findings #1/#4 — the `models/scripts/` path is vestigial.)
**Fix:** `Path(output).parent.mkdir(parents=True, exist_ok=True)` before writing, and update the example
to a directory that exists.

### 14. `bm serve` reports a missing extra via `typer.BadParameter`
**Category:** error-handling semantics
**Location:** `cli/serve.py:42-46`
**Detail:** A missing web extra is surfaced as `typer.BadParameter(...)`, which Typer renders as
"Invalid value: …" — semantically it's a missing optional dependency, not a bad CLI argument.
**Fix:** Use `console.print` of the install hint + `raise typer.Exit(1)` (or `typer.echo(..., err=True)`),
keeping the helpful `pip install "biolm-models[serve]"` message.

---

## Definition-of-Done audit (W10)

From `.planning/03_WORKSTREAMS.md` (W10, "CLI ergonomics"):

- **`bm setup` detects Modal + R2 config and gives clear guidance, network-free, exits non-zero when a
  required prereq is missing** — **met.** `setup.py` checks Modal (env vars or `~/.modal.toml`) and R2
  local creds without any network call, prints actionable panels, and `raise typer.Exit(1)` when Modal
  is unconfigured.
- **Keep `bm deploy` (variants); add `bm serve`; add `bm cache` controls (off by default)** — **met.**
  `deploy` supports multi-model + `--variant`; `serve` launches the local catalog; `cache` reports the
  deploy-time flag and defaults OFF.
- **Keep `bm r2` read-oriented for external users** — **met.** W10 removed upload/sync/delete; only
  `ls`/`download`/`cat`/`du`/`download-outputs` remain, `download` rejects `r2://` destinations, and the
  help labels Storage "(read-only)". (Note: the read-only guarantee is by *omission* at the command
  surface — the shared `get_r2_client()` is still a read/write boto3 client; that's acceptable given no
  write command is exposed.)
- **Three-command quickstart (`git clone → bm setup → bm deploy esm2 → inference`)** — **partially
  verifiable here:** `setup` and `deploy` are wired and `setup` even prints "Try: bm deploy esm2".
  Full quickstart depends on live Modal deploy (out of static scope).
- **Help / docs accurate** — **not fully met:** `bm kb matrix` is broken (finding #1) and `bm help`
  drifts (finding #3); the front-door help leaks "BioLM-Modal" (finding #2).

## Verification

Adversarial re-check of the six HIGH-severity findings against the actual code (read + executed):

1. **`bm kb matrix` imports a non-existent module — REAL.** `cli/kb.py:360` does
   `from models.scripts.generate_comparison_matrix import main`; `models/scripts/` exists nowhere
   (`ls`/`find` empty, `git log --all` empty) and `./.venv/bin/python -c "from models.scripts...import main"`
   → `ModuleNotFoundError`. Import is inside the command body, so it crashes on first use; `"scripts"` is in
   `kb.py:25` SKIP_DIRS and `cli/test_kb.py:9` says matrix_cmd is untested.

2. **"BioLM-Modal" internal name in `cli/main.py` — REAL (with a rendering nuance).** The token is
   verifiably present at `main.py:16,18` (a module-level string literal — note: NOT a true docstring, since
   imports precede it) and `main.py:47` (the `@app.callback` docstring), shipping in public-bound source the
   project explicitly wants scrubbed. Nuance: `bm --help` actually renders the `typer.Typer(help=...)` text at
   `main.py:25` ("BioLM command-line tools…"), so the callback docstring at :47 is overridden and the :16/:18
   string never renders — the finding's "surfaces in the --help front door" mechanism is overstated, but the
   source-level internal-name leak is genuine.

3. **`bm help` hand-maintained + kb rows in wrong panel — REAL.** `main.py:108-112` append the five `kb …`
   rows to `commands_table` (the top-level "Commands" panel), not a dedicated KB panel; reproduced the Rich
   render and confirmed kb subcommands appear jammed under "Commands" alongside the six top-level commands,
   asymmetric with the "Storage (read-only)" panel. Also confirmed `cache status` exists (`cli/cache.py:70`)
   but is omitted from the hand-rolled table — drift is real.

4. **`bm kb missing` references non-existent `kb_acquire.py` — REAL.** `cli/kb.py:436` emits
   "run `kb_acquire.py --models {slug}`"; grep finds `kb_acquire` only at that one line — the tool was never
   ported, so the instruction is dead. The report is also an internal PDF-curation workflow not actionable for
   read-only external users.

5. **`bm r2 cat` decodes each 1MB chunk independently — REAL.** `cli/r2.py:372-373` decodes
   `chunk.decode("utf-8")` per 1MB chunk from a boto3 `StreamingBody` (`r2.py:450-451`), which yields arbitrary
   byte boundaries; a multi-byte UTF-8 sequence straddling a boundary raises `UnicodeDecodeError`, caught and
   misreported as "binary data". Latent (fixtures are small) but the docstring advertises `| less` streaming.

6. **`deploy.py` uses raw `print()` while the rest uses Rich `console.print()` — REAL.** Confirmed 27 `print(`
   vs 2 `console.print(` calls despite `console = Console()` at `deploy.py:31`; exempted from T20 via
   `pyproject.toml` `cli/** = ["T20"]`. A genuine consistency/UX gap (not a functional bug; the print calls use
   plain emoji text, so no Rich markup is actually dropped in those calls).
