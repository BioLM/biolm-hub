# Phase 2: Implementation

## Purpose
Write all model files in dependency order, following the patterns from `models/dummy/` and any reference model identified in Phase 1.

## File Creation Order

1. `schema.py` — request/response models
2. `config.py` — ModelFamily configuration
3. `download.py` — weight acquisition (if the model has external weights)
4. `app.py` — Modal application
5. `test.py` — test suite
6. `fixture.py` — golden-fixture generator (only if `test.py` uses golden output files)
7. `__init__.py` — empty package marker

---

## 2.1 `schema.py`

```python
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import RequestModel, ResponseModel, EnhancedStringEnum
from models.commons.data.validator import validate_aa_extended  # pick appropriate validator
from pydantic import Field, BeforeValidator
from typing import Annotated


class MyModelParams(ModelParams):
    weights_version = "v1"
    display_name = "My Model"
    base_model_slug = "my-model"
    log_identifier = "MY_MODEL"
    batch_size: int = 32
    max_sequence_len: int = 1024


# Only if multi-variant:
class MyModelSize(EnhancedStringEnum):
    SIZE_8M = "8m"
    SIZE_650M = "650m"


class MyModelRequest(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_extended),
        Field(
            min_length=1,
            max_length=MyModelParams.max_sequence_len,
            description="Protein sequence in single-letter amino acid code.",
        ),
    ]


class MyModelResponse(ResponseModel):
    embedding: list[float] = Field(description="Per-sequence embedding vector.")
```

**Requirements:**
- Use `RequestModel` (strict) for inputs, `ResponseModel` (lenient) for outputs
- Apply validators via `BeforeValidator`; import from `models.commons.data.validator`
- All `Field` constraints must match `ModelParams` limits
- Include `description=` on all fields

**Validator selection:**

| Input | Validator |
|-------|-----------|
| Protein (20 AA + ambiguous X, B, Z) | `validate_aa_extended` |
| Protein (20 AA only) | `validate_aa_unambiguous` |
| DNA | `validate_dna_unambiguous` |
| SMILES | `validate_smiles` (or `validate_smiles_with_rdkit`) |
| RNA | *no ready-made `validate_*` function* — see the RNA note below |

> **RNA note:** there is no `validate_rna_unambiguous`. `models.commons.data.validator` exports an
> `rna_unambiguous` charset constant (`"ACUG"`); validate RNA by checking membership against it
> inside your own validator, e.g. `all(r in rna_unambiguous for r in seq.upper())` — see
> `models/chai1/schema.py`. (Adding a `validate_rna_unambiguous` helper to commons would be a
> separate commons change — out of scope during model implementation.)

---

## 2.2 `config.py`

```python
from models.commons.model.config import ActionSchemaMap, ModelFamily, biolm_model_class  # noqa: F401
from models.commons.model.schema import ModalGPU, ModalResourceSpec, ModelActions
from models.commons.model.tag import (
    Architecture, InputModality, InputMolecule, ModelTags, OutputModality, Task,
)
from models.my_model.schema import MyModelParams, MyModelRequest, MyModelResponse


# Single variant
RESOURCE_SPEC = ModalResourceSpec(
    gpu=ModalGPU.T4,
    memory=8192,
    cpu=4.0,
    timeout=600,
)

MODEL_FAMILY = ModelFamily(
    base_model_slug=MyModelParams.base_model_slug,
    display_name=MyModelParams.display_name,
    modal_class_name="MyModelImplementation",  # must match the class name in app.py
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.PROTEIN],
        task=[Task.REPRESENTATION_LEARNING],
        output_modality=[OutputModality.EMBEDDING],
        architecture=[Architecture.TRANSFORMER],
    ),
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.ENCODE,
            request_schema=MyModelRequest,
            response_schema=MyModelResponse,
        ),
    ],
    variant_axes={},                           # {} = single variant
    resource_function=lambda cfg: RESOURCE_SPEC,
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
```

**Multi-variant example:**
```python
# variant_axes defines all combinations
variant_axes={"MODEL_SIZE": ["8m", "650m"]},

# resource_function picks spec per variant
resource_function=lambda cfg: (
    RESOURCE_SPEC_8M if cfg.get("MODEL_SIZE") == "8m" else RESOURCE_SPEC_650M
),

# naming_function: returns (modal_app_name, public_api_slug)
naming_function=lambda base_slug, cfg: (
    f"{base_slug}-{cfg['MODEL_SIZE']}",
    f"{base_slug}-{cfg['MODEL_SIZE']}",
),
```

**Requirements:**
- `modal_class_name` must exactly match the `@biolm_model_class`-decorated class name in `app.py`
- `action_schemas` is a list of `ActionSchemaMap(name=..., request_schema=..., response_schema=...)`
- `naming_function` takes `(base_slug: str, cfg: dict)` and returns `tuple[str, str]`
- Include complete `ModelTags` — used for catalog discovery

---

## 2.3 `download.py` (if model has external weights)

**Self-containment principle:** R2 is the fast cache; HuggingFace / URL / library is the guaranteed
fallback. If R2 and containers are wiped, `download.py` alone must restore everything. Use the
canonical `r2_then_*` wrappers — they build the R2-primary + source-fallback for you. Do **not**
hand-roll `AcquisitionConfig`.

```python
from pathlib import Path
from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import extract_model_variant, r2_then_hf
from models.commons.storage.downloads import get_model_dir_util
from models.my_model.schema import MyModelParams

logger = get_logger(__name__)


def get_model_dir(model_variant: str) -> Path:
    """Path helper — used by app.py to locate the weights."""
    return get_model_dir_util(
        base_model_slug=MyModelParams.base_model_slug,
        weights_version=MyModelParams.weights_version,
        model_variant=model_variant,
    )


def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """Called by setup_download_layer at build time. Returns Path; raises on failure."""
    model_size = extract_model_variant(variant_config, "MODEL_SIZE")

    # R2 cache first; on a miss, download from HuggingFace and cache back to R2.
    result = r2_then_hf(
        base_model_slug=base_model_slug,
        weights_version=weights_version,
        model_variant=model_size,
        sub_path=sub_path,
        hf_repo_id="org/model-name",
        hf_revision="abc123...def",  # 40-char commit hash — NEVER "main"
    )
    if not result.success:
        raise RuntimeError(f"Download failed: {result.error_message}")

    # actual_model_path is the resolved HF snapshot dir (handled for you).
    return result.actual_model_path or result.target_dir
```

**Pick the wrapper for the model's source** (all in `models.commons.storage.download_helpers`):

| Source | Wrapper | Notes |
|--------|---------|-------|
| HuggingFace Hub | `r2_then_hf(..., hf_repo_id=, hf_revision=)` | pin a 40-char `hf_revision`, never `"main"` |
| A library that fetches its own weights (e.g. fair-esm) | `r2_then_library(..., library_name=, init_fn=)` | `init_fn(target_dir)` triggers the download |
| Direct URLs (GitHub releases, custom hosts) | `r2_then_urls(..., urls=[...])` | non-HF hosted weights |
| A tar/zip archive | `r2_then_archive(..., url=, ...)` | downloads + extracts |

Each returns an `AcquisitionResult` (`.success`, `.actual_model_path`, `.target_dir`,
`.error_message`, `.files_downloaded`). On a cache miss it fetches from the source **and caches it
back to R2** at the same path, so the next cold start is fast.

> **Build-time gotcha:** if the fallback imports a library or `huggingface_hub` at build time, add it
> to `setup_download_layer(..., extra_pip_packages=[...])` in `app.py`, or the image build fails with
> `ModuleNotFound`.

**Anti-patterns:**
```python
model_size = os.environ.get("MODEL_SIZE")   # WRONG — use extract_model_variant(variant_config, ...)
hf_revision = "main"                         # WRONG — pin a 40-char commit hash
return str(result.target_dir)                # WRONG — return a Path, not str
primary = AcquisitionConfig(...)             # WRONG — use the r2_then_* wrappers, don't hand-roll
```

---

## 2.4 `app.py`

```python
import modal

from models.commons.core.decorator import modal_endpoint
from models.commons.core.error import UserError
from models.commons.core.logging import get_logger
from models.commons.modal.downloader import setup_download_layer  # omit if no weights
from models.commons.modal.source import setup_source_layer
from models.commons.model.base import ModelMixinSnap  # or ModelMixin (no snapshots)
from models.commons.model.config import biolm_model_class
from models.commons.util.config import cloudflare_r2_secret, common_requirements
from models.my_model.config import MODEL_FAMILY
from models.my_model.download import MyModelParams  # only if has download.py
from models.my_model.schema import MyModelRequest, MyModelResponse

logger = get_logger(__name__)

# --- Image build ---
# Pin ALL versions exactly.
base_image = modal.Image.from_registry(
    "pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime",
    add_python="3.12",
).pip_install(
    "transformers==4.48.1",
    "safetensors==0.5.3",
)

# If model has weights:
image = setup_download_layer(
    base_image,
    base_model_slug=MyModelParams.base_model_slug,
    weights_version=MyModelParams.weights_version,
    variant_config={"MODEL_SIZE": "650m"},   # or parse from env for multi-variant
)
image = image.uv_pip_install(common_requirements)
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)

# --- App config ---
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config()   # single variant
# Multi-variant: MODEL_FAMILY.get_app_config(MODEL_SIZE=os.environ["MODEL_SIZE"])
app = modal.App(app_name, image=image)


# --- Model class (with memory snapshot) ---
@app.cls(
    image=image,
    secrets=[cloudflare_r2_secret],
    enable_memory_snapshot=True,
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class MyModelImplementation(ModelMixinSnap):
    @modal.enter(snap=True)
    def load_model_cpu(self):
        """Load weights to CPU — captured in snapshot."""
        logger.info("Loading %s to CPU...", MODEL_FAMILY.display_name)
        # load weights here
        logger.info("%s ready for snapshot.", MODEL_FAMILY.display_name)

    @modal.enter(snap=False)
    def move_to_gpu(self):
        """Move to GPU, set seeds — runs after snapshot restore."""
        import random

        import numpy as np
        import torch

        torch.manual_seed(42)
        np.random.seed(42)
        random.seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        self.model.to("cuda")

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(self, payload: MyModelRequest) -> MyModelResponse:
        import torch

        try:
            with torch.no_grad():
                output = self.model(payload.sequence)
            return MyModelResponse(embedding=output.tolist())
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            raise UserError("GPU out of memory. Try a shorter sequence.")


# --- Without memory snapshots ---
# class MyModelImplementation(ModelMixin):
#     @modal.enter()
#     def load_model(self):
#         ...


if __name__ == "__main__":
    from models.commons.modal.deployment import run_or_deploy_modal_app
    run_or_deploy_modal_app(
        app,
        MyModelImplementation,
        description=f"Run and optionally deploy {MODEL_FAMILY.display_name}.",
    )
```

**Image layer order:** download layer → pip install → `common_requirements` → source layer.

**Anti-patterns:**
```python
from other_repo.mixins import CachingMixin              # WRONG — no billing/caching mixin here; use ModelMixin/ModelMixinSnap from models.commons.model.base
print("loading model")                                  # WRONG — use logger
raise ValueError("bad sequence")                        # WRONG — use UserError
```

---

## 2.5 `test.py`

```python
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.my_model.config import MODEL_FAMILY
from models.my_model.schema import MyModelRequest


def _validate_encode(actual_output: dict, _expected_output: dict = None) -> None:
    """Custom validator — use when golden fixtures aren't needed."""
    assert "embedding" in actual_output
    assert len(actual_output["embedding"]) == 1280


test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},     # {} = all variants (or single variant)
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    # Option A: programmatic input with custom validator
                    input_fixture=MyModelRequest(sequence="MKTLLLTLVVVTIVCLDLGAVS"),
                    validator=_validate_encode,
                    # Option B: golden output file (stored in R2 test-data/)
                    # input_fixture="encode_input.json",
                    # expected_output_fixture="encode_expected_output.json",
                    # tolerances={"rel_tol": 1e-4},
                ),
            ],
        )
    ],
)

# Generate both test types — ALWAYS call both
test_encode_integration = generate_tests_from_suite(test_suite, test_type="integration")
test_encode_deployment = generate_tests_from_suite(test_suite, test_type="deployment")
```

**Shared test assets:** Prefer importing standard sequences from `models.commons.testing.shared_assets` (e.g., `STANDARD_PROTEIN`) rather than hardcoding sequences. Large shared inputs live in R2 under `test-data/shared/<category>/` and can be referenced with a `"shared/..."` path prefix.

**Golden outputs:** If using golden output files, generate them with `python models/MODEL/fixture.py` before running tests. Never regenerate goldens just to make a test green — only regenerate when an output change is intentional.

---

## 2.6 `fixture.py` (golden generation)

Write `fixture.py` **only if** `test.py` compares against golden output files (i.e. uses
`input_filename_template` + `expected_output_fixture`). If `test.py` validates entirely with a custom
`validator=`, you don't need one. **Copy the template at `models/dummy/fixture.py`** and adapt it —
`models/esm2/fixture.py` is a fuller multi-fixture example.

```python
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.my_model.config import MODEL_FAMILY
from models.my_model.schema import MyModelRequest

# Self-contained input: inlined (or imported from shared_assets), never read from R2 at
# module scope — so `pytest --collect-only` works with no Modal/R2 credentials.
ENCODE_INPUT = "encode_input.json"
ENCODE_OUTPUT = "encode_expected_output.json"   # multi-variant: "{variant.name}_encode_expected_output.json"


def _build_fixture_generation_suite() -> TestSuite:
    request = MyModelRequest.model_validate({"items": [{"sequence": "MKTLLLTLVVVTIVCLDLGAVS"}]})
    return TestSuite(
        model_family=MODEL_FAMILY,
        r2_fixture_subdir="models",
        variant_test_mappings=[
            VariantTestMapping(
                variant_config={},   # {} = all/single variant; {"MODEL_SIZE": "3b"} targets one
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.ENCODE,
                        input_fixture=request,
                        input_filename_template=ENCODE_INPUT,
                        expected_output_fixture=ENCODE_OUTPUT,
                    ),
                ],
            )
        ],
    )


def generate() -> None:
    FixtureGenerator(_build_fixture_generation_suite()).generate()


if __name__ == "__main__":
    generate()
```

**What `generate()` does** (`FixtureGenerator` in `models.commons.testing.fixture`): for each
variant that matches a mapping, it (1) writes each programmatic `input_fixture` to R2 at
`test-data/models/<slug>/<input_filename_template>`, (2) spins up the model's Modal app locally —
which **self-populates weights** via `download.py`, so you don't pre-stage anything — (3) calls each
action with the input, and (4) writes the response to `test-data/models/<slug>/<expected_output_fixture>`.
Those written files are the goldens the integration tests then load. Generation needs Modal + R2
write access, so it runs locally (or under the maintainer-gated deploy job), not in the unit-test CI.

**Requirements:**
- Inputs self-contained and lazily built (inline or `shared_assets`); no module-scope R2 reads or
  heavy imports (keeps `pytest --collect-only` Modal-free).
- Single-variant models: use plain filenames — do **not** put `{variant.name}` in the paths.
- Do not pass `remote_fn_kwargs` here; the generator always calls with `_skip_cache=True` itself.

---

## 2.7 `__init__.py`

Create empty:
```bash
touch models/<name>/__init__.py
```

---

## Code Review Checklist (before Phase 3)

- [ ] All imports organized (Core, Data, Modal, Model, Storage, Testing, Util — these are the only import groups)
- [ ] All dependency versions pinned exactly (`==X.Y.Z`)
- [ ] `ModelMixinSnap` or `ModelMixin` used (these are the only base mixins — don't import a billing/caching mixin carried over from another codebase)
- [ ] Seeds set for all sources (torch, numpy, random, CUDA) in `snap=False` enter
- [ ] `@modal.method()` + `@modal_endpoint()` on every action method
- [ ] `modal_class_name` in `config.py` matches the class name in `app.py`
- [ ] `UserError` used for bad-input paths; `ServerError` propagates for system errors
- [ ] `get_logger(__name__)` — no `print` anywhere in runtime code
- [ ] `download.py` returns `Path`, raises `RuntimeError`, uses `extract_model_variant`
- [ ] HuggingFace revision is a 40-char commit hash
- [ ] Single-variant models do NOT use `{variant.name}` template in fixture paths
- [ ] `make check` passes (style + mypy + schema-doc check + CI-script tests + unit tests)

## Gate

Before Phase 3: all files present, `make check` passes.
