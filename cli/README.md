# `bh` — the biolm-hub CLI

`bh` is the single entry point for working with the catalog: check your setup, deploy models to your
own Modal workspace, browse the public weight bucket, and run a local catalog web app. It's a
[Typer](https://typer.tiangolo.com/) app; run `bh` (or `bh help`) for the command tree, and
`bh <command> --help` for any command's flags.

## Commands

| Command | What it does | Module |
|---------|--------------|--------|
| `bh setup` | Check your Modal auth (required) and R2 config (optional) and tell you exactly what to fix. | `setup.py` |
| `bh deploy <model>…` | Deploy a model to your Modal workspace. Deploys the **default variant** by default; `--all-variants` for the whole family, `--variant KEY=value` for one. `--all` deploys the whole catalog (see below). Auto-detects credential-less mode when the workspace has no `cloudflare-r2` secret. | `deploy.py` |
| `bh serve` | Launch the local catalog web app + HTTP API (`http://127.0.0.1:8000`). Needs the `serve` extra. | `serve.py` |
| `bh cache …` | Inspect/manage the optional response cache. | `cache.py` |
| `bh r2 …` | Browse and manage the public R2 bucket (`ls`, `cat`, `du`, `download`, …). | `r2.py` |
| `bh kb …` | Work with the machine-readable knowledge graph (`sources`, `validate`, …). | `kb.py` |

## Deploying the whole catalog (`bh deploy --all`)

`bh deploy --all` deploys every model in one go. `--all` is mutually exclusive with a positional
`MODEL` argument.

- **By default it deploys only the DEFAULT (cheapest) variant of each model.** A prominent notice
  says so both before deploying and in the final summary, and prints the exact command to deploy
  everything: `bh deploy --all --all-variants`.
- `--all --all-variants` deploys **every** variant of every model instead.

Before deploying, it prints a preflight summary (model/variant counts and a CPU-vs-GPU breakdown by
tier) and prompts `Continue? [y/N]` (skip with `--yes`/`-y`). Deploys run with bounded parallelism
and **continue on error** — one model failing doesn't abort the rest; the final table shows
✓ deployed / ✗ failed (with reason) / ⤼ skipped, and the command exits non-zero if anything failed.

| Flag | Effect (with `--all`) |
|------|-----------------------|
| `--all-variants` | Deploy every variant of every model (default: cheapest variant only). |
| `--dry-run` | Print the full model → variant → GPU plan and exit; deploys nothing, no prompt. |
| `--cpu-only` | Only deploy models whose selected variant runs on CPU. |
| `--only a,b,c` | Restrict to these model slugs (comma-separated; unknown names error). |
| `--exclude x,y` | Skip these model slugs. |
| `--skip-deployed` | Query Modal and skip apps already deployed in the target environment. |
| `--max-concurrency N` | Max models to deploy in parallel (default 4). |
| `--yes` / `-y` | Skip the confirmation prompt. |
| `--env` / `-e` | Modal environment to target (defaults to your active profile). |

```bash
bh deploy --all                 # default (cheapest) variant of every model
bh deploy --all --all-variants  # EVERY variant of every model
bh deploy --all --dry-run       # preview the plan, deploy nothing
bh deploy --all --cpu-only --skip-deployed -y
```

## Notes

- **Deploys bill your own Modal account** and deployed endpoints are **unauthenticated** — don't
  expose them without your own access control.
- `bh deploy` spawns each model's `app.py` in a clean subprocess so the Modal app registers in
  isolation. The credential-less probe (`_maybe_enable_credential_less`) lives here in the CLI —
  which is authenticated — because it must *not* run at `app.py` import time (importing a model has to
  stay auth-free so CI, unit tests, and docs generation work with no Modal token).
- `bh serve` reuses the gateway routing logic in-process for a local app; the *deployed* gateway
  (`gateway/`) is a separate, optional thing.

`bh` is defined by `main.py`, which mounts each command from its own module. See the top-level
[`README.md`](../README.md) and [`CONTRIBUTING.md`](../CONTRIBUTING.md) for the full picture, and the
[docs site](https://biolm.github.io/biolm-hub/) for the rendered per-model schemas and knowledge graph.
