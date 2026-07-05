import modal

from models.commons.core.decorator import modal_endpoint
from models.commons.core.logging import get_logger
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.base import ModelMixinSnap
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    common_requirements,
    runtime_secrets,
)
from models.commons.util.device import get_torch_device
from models.commons.util.environment import parse_variant
from models.progen2.config import MODEL_FAMILY
from models.progen2.download import get_model_dir
from models.progen2.schema import (
    ProGen2GenerateRequest,
    ProGen2GenerateResponse,
    ProGen2GenerateResponseGenerated,
    ProGen2ModelTypes,
    ProGen2Params,
)

logger = get_logger(__name__)

variant_config = parse_variant(
    env_var_name="MODEL_TYPE",
    allowed_values=ProGen2ModelTypes,
    default=ProGen2ModelTypes.MEDIUM,
)
model_type = variant_config["MODEL_TYPE"]


# Build Modal container image
image = modal.Image.from_registry("pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime")
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=ProGen2Params.base_model_slug,
    weights_version=ProGen2Params.weights_version,
    sub_path="checkpoints",
    variant_config=variant_config,
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        "tokenizers==0.15.0",
        "transformers==4.36.2",
        "safetensors==0.5.3",
    )
)
# Finally, add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)


# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config(**variant_config)
logger.info("App name: %s", app_name)
app = modal.App(app_name, image=image)


@app.cls(
    image=image,
    secrets=runtime_secrets(),
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class ProGen2Model(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")
    model_type: str = model_type

    @modal.enter(snap=True)
    def setup_model(self) -> None:
        """Load model directly on GPU for GPU memory snapshot."""
        import torch

        from models.progen2.external.sample_utils import (  # type: ignore[attr-defined]  # vendored external module, excluded from mypy
            create_model,
            create_tokenizer_custom,
        )

        logger.info("Loading ProGen2 model directly on GPU for GPU memory snapshot...")

        self.torch = torch

        # Get device and setup for GPU inference
        self.device = get_torch_device()

        self.model_dir = get_model_dir()

        checkpoint_path = self.model_dir / f"progen2_{self.model_type}"
        tokenizer_path = self.model_dir / "tokenizer.json"
        torch.hub.set_dir(self.model_dir)

        logger.info(
            "Loading ProGen2 model '%s' directly on %s from: %s",
            self.model_type,
            self.device,
            self.model_dir,
        )

        # Load model directly on GPU
        self.model = create_model(ckpt=checkpoint_path, fp16=False)
        self.model = self.model.eval()

        # Move model to GPU with deterministic behavior
        self.model = self.model.to(device=self.device, non_blocking=False)

        # Load tokenizer
        self.tokenizer = create_tokenizer_custom(file=tokenizer_path)
        self.max_sequence_len = ProGen2Params.max_sequence_len

        logger.info(
            "ProGen2 model '%s' loaded directly on %s for GPU memory snapshot!",
            self.model_type,
            self.device,
        )

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def generate(self, payload: ProGen2GenerateRequest) -> ProGen2GenerateResponse:
        """
        From ProGen2 paper:
            "All samples are provided to the model with a 1 or 2 character token
            concatenated at the N-terminal and C-terminal side of the sequence.
            Each sequence is then provided as-is and flipped."

            - N-Terminal: Beginning of the protein sequence, with an amine group (-NH2)
            - C-Terminal: End of the protein sequence, with a carboxyl group (-COOH)
        """
        import random
        import time

        import numpy as np

        from models.progen2.external.likelihood_utils import (  # type: ignore[attr-defined]  # vendored external module, excluded from mypy
            run_likelihood,
        )
        from models.progen2.external.sample_utils import (  # type: ignore[attr-defined]  # vendored external module, excluded from mypy
            run_sample,
        )

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

        # Parse payload params
        temp = payload.params.temperature
        top_p = payload.params.top_p
        max_length = payload.params.max_length
        num_return_sequences = payload.params.num_samples

        results = []
        for item in payload.items:
            # Pydantic enforces only 1 item, so this for loop should only run once
            context = item.context
            context = f"1{context}"  # Add N-Terminal token to context

            # Note: run_sample() deals with setting torch.no_grad(),
            #       and moving tensors to device and back
            try:
                generated_sequences = run_sample(
                    device=self.device,
                    model=self.model,
                    temp=temp,
                    top_p=top_p,
                    max_length=max_length,
                    num_return_sequences=num_return_sequences,
                    context=context,
                    tokenizer=self.tokenizer,
                )
            except Exception:
                logger.error("Model call failed", exc_info=True)
                raise

            try:
                likelihoods = [
                    run_likelihood(
                        context=f"1{sequence}2",  # Add N- and C-Terminal tokens to context
                        model=self.model,
                        tokenizer=self.tokenizer,
                        device=self.device,
                    )
                    for sequence in generated_sequences
                ]
            except Exception:
                logger.error("Likelihood computation failed", exc_info=True)
                raise

            result = [
                ProGen2GenerateResponseGenerated.model_validate(
                    {
                        "sequence": sequence,
                        "ll_sum": likelihoods[idx]["ll_sum"],
                        "ll_mean": likelihoods[idx]["ll_mean"],
                    }
                )
                for idx, sequence in enumerate(generated_sequences)
            ]
            results.append(result)

        return ProGen2GenerateResponse(results=results)


if __name__ == "__main__":
    """
    Usage:
        MODEL_TYPE="medium" python models/progen2/app.py

        # Force deploy to "biolm-hub-dev" or "biolm-hub" environment:
        MODEL_TYPE="medium" python models/progen2/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        ProGen2Model,
        description=f"Run and optionally deploy the {ProGen2Params.display_name} {model_type} Modal app.",
    )
