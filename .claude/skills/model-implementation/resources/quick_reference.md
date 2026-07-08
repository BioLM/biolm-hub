# Quick Reference

A cheat-sheet for implementing a model. Start by copying `models/dummy/` — it is the canonical,
working template.

## File creation order

Create files in dependency order (later files import earlier ones):

1. `schema.py` — request/response Pydantic models (the action contracts)
2. `config.py` — `MODEL_FAMILY` (`ModelFamily`): variants, action schemas, `modal_class_name`, resources
3. `download.py` — weight acquisition (only if the model has weights)
4. `app.py` — the Modal app + the action methods
5. `test.py` — the `TestSuite` (integration + deployment cases); `fixture.py` if generating fixtures
6. `LICENSE` — the upstream license text, copied verbatim from the source repo (every model dir ships one; it must match `sources.yaml`). No upstream LICENSE file (license only a HF card metadata tag)? Record the SPDX id + canonical text/URL + a note — don't block. See `investigation/GUIDE.md §1.1`.
7. `__init__.py` — empty marker

Then the knowledge graph (`sources.yaml`, `comparison.yaml`, `README.md`, `MODEL.md`, `BIOLOGY.md`)
via the `model-knowledge-base` skill.

## Essential commands

```bash
make check                                  # style + mypy + schema-doc check + CI-script tests + unit — MANDATORY before push (CI's `checks` job)
make docs                                   # mkdocs build --strict — separate CI job; the generated model page must build
python -m tooling.gen_model_catalog         # regenerate models/README.md catalog after adding/renaming a model — else test_readme_catalog_is_fresh fails make check
make test-unit                              # fast unit tests only (no Modal/R2)

# Local deploy + tests (need a Modal account) — REQUIRED before the PR if you have creds:
MODAL_ENVIRONMENT=biolm-hub-dev python models/<model>/fixture.py   # record golden input + output FIRST
MODAL_ENVIRONMENT=biolm-hub-dev python -m pytest models/<model>/test.py -m integration
MODAL_ENVIRONMENT=biolm-hub-dev bh deploy <model> --force          # dev deploy + at least one live call

# Credential-less contributors: skip the above and state in the PR that deploy is unverified.
# Either way the full integration/deployment matrix re-runs in CI once a maintainer applies
# `deploy-approved` (see validation/GUIDE.md §3.5).
```

## Standard imports (from `models/dummy/app.py`)

```python
import modal

from models.commons.core.decorator import modal_endpoint
from models.commons.core.logging import get_logger
from models.commons.modal.source import setup_source_layer
from models.commons.model.base import ModelMixinSnap   # or ModelMixin (non-snapshot)
from models.commons.model.config import biolm_model_class
from models.commons.util.config import common_requirements, runtime_secrets

logger = get_logger(__name__)
```

- Use `ModelMixinSnap` + `enable_memory_snapshot=True` for GPU models that benefit from snapshotting;
  `ModelMixin` otherwise.
- Mark the class with `@biolm_model_class` and each action with `@modal.method()` +
  `@modal_endpoint(app_name=app_name)`.
- Mount secrets with `@app.cls(secrets=runtime_secrets(), ...)`. `runtime_secrets()` returns
  `[cloudflare_r2_secret]` normally, or `[]` under `BIOLM_SKIP_MODAL_SECRETS` so a credential-less
  deploy can still start — never hard-code `secrets=[cloudflare_r2_secret]`.
- GPU / snapshot models also pass `experimental_options={"enable_gpu_snapshot": True}` on `@app.cls`
  (see `models/dummy/app.py`); CPU / no-weights models omit it.
- There is **no** billing or redis layer in this repo — never import a billing mixin or a redis/cache secret carried over from another codebase.

## GPU / resource tiers (Modal)

Pick the smallest tier that fits the model's weights + activations in memory.

| Tier (`ModalGPU`) | VRAM | Use for |
|------|------|---------|
| `None` (CPU) | — | tokenizers, small classical/algorithmic tools, utilities, and **tiny neural LMs** (see note) |
| `T4` | 16 GB | small models (≲ 650M params); the smallest GPU tier |
| `L4` | 24 GB | small–mid models; newer/cheaper than T4 with more VRAM (**heavily used**) |
| `A10G` | 24 GB | mid-size models (~1–3B) |
| `L40S` | 48 GB | mid–large models / longer sequences |
| `A100-40GB` (`a100`) | 40 GB | large models |
| `A100-80GB` (`a100-80gb`) | 80 GB | large models (≥7B) or big batches |
| `H100` | 80 GB | largest/fastest — when you need more throughput than an A100 |
| `H200` | 141 GB | very large models / very long context |
| `B200` | 180 GB | the largest models |

Full enum: `models/commons/model/schema.py::ModalGPU` (`T4`, `L4`, `A10G`, `L40S`, `A100_40GB`,
`A100_80GB`, `H100`, `H200`, `B200`). Set `gpu=None` in the resource spec for CPU.

> **Tiny neural LMs (~tens of M params, e.g. a 14M-param BERT/RoBERTa):** a GPU is often not worth it.
> CPU (`gpu=None`) or `T4` both work — prefer CPU for genuinely tiny, latency-tolerant models; use
> `T4` if you want the shared GPU snapshot + seed pattern of a torch model. Either is defensible; start
> at the cheaper tier and bump on need.

Rough VRAM rule of thumb: `params × bytes_per_param (2 for fp16) × ~1.3 overhead`. Set the tier in
`config.py`'s resource spec; start small and bump only if you hit OOM.
