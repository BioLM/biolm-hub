import modal

from models.commons.core.decorator import modal_endpoint
from models.commons.core.logging import get_logger
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.base import ModelMixinSnap
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
)
from models.commons.util.device import get_torch_device
from models.commons.util.environment import parse_variant
from models.evo.config import EVO_VARIANT_TO_MODEL_NAME, MODEL_FAMILY, get_build_gpu
from models.evo.schema import (
    EvoGenerateRequest,
    EvoGenerateResponse,
    EvoGenerateResponseResult,
    EvoLogProbRequest,
    EvoLogProbResponse,
    EvoLogProbResponseResult,
    EvoModelVariants,
    EvoParams,
)

logger = get_logger(__name__)

variant_config = parse_variant(
    env_var_name="MODEL_VARIANT",
    allowed_values=EvoModelVariants,
    default=EvoModelVariants.EVO_1_5_8K_BASE,
)
model_variant = variant_config["MODEL_VARIANT"]


# Build Modal container image
# Pinned: flash-attn ABI requires matching Python version
image = modal.Image.from_registry("pytorch/pytorch:2.2.0-cuda11.8-cudnn8-devel")
build_gpu = get_build_gpu(model_variant)
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)  # Critical for computing container uptime
    # NOTE: Pre-install all dependencies if download layer might depend upon it
    .apt_install("git")  # Needed for flash-attn
    .pip_install(
        "torch==2.2.0",
        "safetensors==0.4.5",
        "flash-attn==2.5.5",  # Install flash-attn early to avoid recompilation
        "stripedhyena==0.2.2",
        "einops==0.8.1",
        "triton==2.2.0",
        "huggingface_hub==0.33.4",
        "evo-model==0.4",  # Install evo-model after flash-attn is already installed
        gpu=build_gpu,
        extra_options="--no-build-isolation",  # flash-attn's build imports torch; use env where torch is installed
    )
)
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=EvoParams.base_model_slug,
    weights_version=EvoParams.weights_version,
    variant_config=variant_config,
)
# Finally, add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)


# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config(**variant_config)
logger.info("App name: %s", app_name)
app = modal.App(app_name, image=image)


@app.cls(
    image=image,
    secrets=[cloudflare_r2_secret],
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class EvoModel(ModelMixinSnap):
    """
    Loads the selected Evo model variant and implements:
      - log_prob() => total log-prob
      - generate() => sequence sampling
    """

    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def setup_model(self) -> None:
        """
        Load Evo model directly on GPU for GPU memory snapshot.
        """
        from evo import Evo
        from evo.generation import generate
        from evo.scoring import score_sequences

        from models.commons.storage.downloads import setup_hf_cache_env
        from models.evo.download import get_model_dir

        self.score_sequences = score_sequences  # for log_prob
        self.generate_fn = generate  # for generate

        model_name = EVO_VARIANT_TO_MODEL_NAME[EvoModelVariants(model_variant)]
        # Point the HF cache at the R2-restored weights so Evo loads them locally
        # instead of re-downloading from HuggingFace on every cold start.
        setup_hf_cache_env(get_model_dir(model_variant))
        logger.info("[Evo] Loading Evo model '%s' ...", model_name)
        self.device = get_torch_device()
        evo_obj = Evo(model_name, device=self.device)

        self.model = evo_obj.model  # The StripedHyena model
        self.tokenizer = evo_obj.tokenizer  # CharLevelTokenizer
        self.model.eval()

        # Disable gradient
        import torch

        self.torch = torch
        torch.set_grad_enabled(False)

        logger.info("[Evo] Loaded '%s' on %s.", model_name, self.device)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def log_prob(self, payload: EvoLogProbRequest) -> EvoLogProbResponse:
        """
        Sums the log probability of each DNA sequence.
        This calls evo.scoring.score_sequences(...), which:
          1) tokenize
          2) forward pass
          3) gather log-probs at each token
          4) sum or average over positions
        """
        sequences = [item.sequence for item in payload.items]

        # The function `score_sequences()` returns a float per sequence
        scores = self.score_sequences(
            seqs=sequences,
            model=self.model,
            tokenizer=self.tokenizer,
            reduce_method="sum",  # or "mean"
            device=self.device,
        )

        results = [EvoLogProbResponseResult(log_prob=lp) for lp in scores]
        return EvoLogProbResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def generate(self, payload: EvoGenerateRequest) -> EvoGenerateResponse:
        """
        Generate new DNA sequences from a prompt using
        evo.generation.generate(...). We return both the sequence
        and an average score from the sampling.
        """
        import random
        import time

        import numpy as np

        # Set random seed for diversity (CRITICAL: must be BEFORE any sampling)
        if payload.params.seed is None:
            seed = int(time.time_ns() % (2**32))  # Time-based entropy
        else:
            seed = payload.params.seed  # User-provided for reproducibility

        # Apply seed to ALL RNG sources
        random.seed(seed)
        np.random.seed(seed)
        self.torch.manual_seed(seed)
        if self.torch.cuda.is_available():
            self.torch.cuda.manual_seed_all(seed)

        results = []
        # extract common sampling parameters from payload.params
        params = payload.params

        for item in payload.items:
            generate_result = self.generate_fn(
                prompt_seqs=[item.prompt],
                model=self.model,
                tokenizer=self.tokenizer,
                n_tokens=params.max_new_tokens,
                temperature=params.temperature,
                top_k=params.top_k,
                top_p=params.top_p,
                prepend_bos=params.prepend_bos,
                cached_generation=True,
                device=self.device,
                verbose=False,
            )

            seqs, scores = generate_result

            generated_seq = seqs[0]
            score = scores[0]

            results.append(
                EvoGenerateResponseResult(
                    generated=generated_seq,
                    score=score,
                )
            )

        return EvoGenerateResponse(results=results)


if __name__ == "__main__":
    """
    Usage:
        MODEL_VARIANT="v1.5-8k" python models/evo/app.py

        # Force deploy to "biolm-models-dev" or "biolm-models":
        MODEL_VARIANT="v1.5-8k" python models/evo/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        EvoModel,
        description=f"Run and optionally deploy the {EvoParams.display_name} {model_variant} Modal app.",
    )
