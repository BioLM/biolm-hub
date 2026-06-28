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
6. `__init__.py` — empty marker

Then the knowledge graph (`sources.yaml`, `comparison.yaml`, `README.md`, `MODEL.md`, `BIOLOGY.md`)
via the `model-knowledge-base` skill.

## Essential commands

```bash
make check                                  # style + mypy + unit — MANDATORY before push (what CI runs)
make test-unit                              # fast unit tests only (no Modal/R2)

# Optional local deploy + tests (need a Modal account):
MODAL_ENVIRONMENT=biolm-models-dev python models/<model>/fixture.py   # generate fixtures FIRST
MODAL_ENVIRONMENT=biolm-models-dev python -m pytest models/<model>/test.py -m integration
MODAL_ENVIRONMENT=biolm-models-dev bm deploy <model> --force          # deploy a variant

# The full deploy + integration/deployment matrix is maintainer-gated in CI
# (a maintainer applies the `deploy-approved` label) — you do not need to run it.
```

## Standard imports (from `models/dummy/app.py`)

```python
import modal

from models.commons.core.decorator import modal_endpoint
from models.commons.core.logging import get_logger
from models.commons.modal.source import setup_source_layer
from models.commons.model.base import ModelMixinSnap   # or ModelMixin (non-snapshot)
from models.commons.model.config import biolm_model_class
from models.commons.util.config import cloudflare_r2_secret, common_requirements

logger = get_logger(__name__)
```

- Use `ModelMixinSnap` + `enable_memory_snapshot=True` for GPU models that benefit from snapshotting;
  `ModelMixin` otherwise.
- Mark the class with `@biolm_model_class` and each action with `@modal.method()` +
  `@modal_endpoint(app_name=app_name)`.
- There is **no** billing/redis layer — never import `models.commons.billing` or `redis_url_secret`.

## GPU / resource tiers (Modal)

Pick the smallest tier that fits the model's weights + activations in memory.

| Tier | VRAM | Use for |
|------|------|---------|
| CPU | — | tokenizers, small classical/ML models, utilities |
| `T4` | 16 GB | small models (≤650M params) |
| `A10G` | 24 GB | mid-size models (~1–3B) |
| `A100-40GB` | 40 GB | large models / longer sequences |
| `A100-80GB` | 80 GB | the largest models (≥7B) or big batches |

Rough VRAM rule of thumb: `params × bytes_per_param (2 for fp16) × ~1.3 overhead`. Set the tier in
`config.py`'s resource spec; start small and bump only if you hit OOM.
