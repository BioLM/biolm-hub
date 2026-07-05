# `commons` — the shared framework

Everything a model needs that *isn't* the science. The whole catalog's uniformity comes from here: one
base class, one config shape, one schema base, one logging setup, one error taxonomy, one weight-
acquisition path, one testing harness. **Changes here ripple to every model — change with care.**

## Subpackages

| Package | What it provides |
|---------|------------------|
| `core/` | Structured `logging` (`get_logger`), the typed `error` taxonomy (user vs system errors with stable `code`s), the response-`caching` layer, and shared `decorator`s. |
| `model/` | `config.py` — `ModelFamily`/`ResolvedVariant` (the authoritative per-model definition: variants, action→schema map, resource specs). `base.py` + the `@biolm_model_class` decorator (the container base). `pydantic.py` — the strict base request/response models. `schema.py` — `ModelActions` (the closed verb set). `tag.py` — `ModelTags`. |
| `modal/` | Modal image assembly: `source.py` (the source layer; also bakes the credential-less flag into the image), `downloader.py` (the build-time download layer), `deployment.py` (deploy helpers). |
| `storage/` | Weight acquisition + R2 caching — the trickiest part. Models call an `r2_then_*` wrapper from `download_helpers.py`; underneath sit the `acquisition` strategy engine and the `r2_utils`/`r2`/`r2_http` atomic-cache primitives. See [`storage/DOWNLOAD_MODEL_WEIGHTS_README.md`](storage/DOWNLOAD_MODEL_WEIGHTS_README.md). |
| `util/` | `config.py` (secrets, env flags like `BIOLM_SKIP_MODAL_SECRETS`/`BIOLM_CACHE_ENABLED`, R2 bucket layout), `environment.py` (Modal env resolution), `device.py`. |
| `testing/` | The harness: `config.py` (`TestSuite`, `ActionTestCase`), `fixture.py` (`FixtureGenerator` — golden generation), `comparator.py`/`multientity_comparator.py` (`DictComparator` — golden matching with tolerances), `runner.py`, `shared_assets.py` (shared test inputs). |

## The contracts every model relies on

- **Logging:** `from models.commons.core.logging import get_logger` — never `print()` (lint rejects it outside CLI/scripts/tests), never log full sequences or secrets.
- **Errors:** raise a typed *user* error for a caller's mistake (surfaced verbatim with a stable `code`); let *system* errors propagate (they're sanitized). Never raise a bare `ValueError` for bad input.
- **Schemas:** subclass the `pydantic.py` bases; every field carries a `Field(description=...)`; reuse shared field names (see [`tooling/field_glossary.yaml`](../../tooling/field_glossary.yaml)).
- **Weights:** implement `download.py` with an `r2_then_hf` / `r2_then_library` / `r2_then_urls` / `r2_then_archive` wrapper so weights self-populate the public bucket.

See [`CONTRIBUTING.md`](../../CONTRIBUTING.md) and [`PHILOSOPHY.md`](../../PHILOSOPHY.md) for the why.
