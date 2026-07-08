import os
from typing import Any

import modal

from models.commons.core.decorator import modal_endpoint
from models.commons.core.error import ValidationError400
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
from models.evo2.config import (
    MODEL_FAMILY,
    evo2_github_commit_hash,
    get_build_gpu,
)
from models.evo2.download import get_model_dir
from models.evo2.schema import (
    Evo2EncodeIncludeOptions,
    Evo2EncodeRequest,
    Evo2EncodeResponse,
    Evo2EncodeResponseEmbedding,
    Evo2EncodeResponseResult,
    Evo2GenerateRequest,
    Evo2GenerateResponse,
    Evo2GenerateResponseResult,
    Evo2LogProbRequest,
    Evo2LogProbResponse,
    Evo2LogProbResponseResult,
    Evo2ModelVariants,
    Evo2Params,
)

logger = get_logger(__name__)

variant_config = parse_variant(
    env_var_name="MODEL_VARIANT",
    allowed_values=Evo2ModelVariants,
    default=Evo2ModelVariants.EVO2_1B_BASE,
)
model_variant = variant_config["MODEL_VARIANT"]

# Get the GPU string value for building CUDA extensions
build_gpu = get_build_gpu(model_variant)


# Build Modal container image
# Pinned: flash-attn+transformer-engine ABI mismatch
image = modal.Image.from_registry("pytorch/pytorch:2.4.1-cuda12.4-cudnn9-devel")
# Note: huggingface_hub needed in download layer for HF fallback when R2 cache is empty
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=Evo2Params.base_model_slug,
    weights_version=Evo2Params.weights_version,
    variant_config=variant_config,
    extra_pip_packages=["huggingface_hub==0.26.0"],
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .apt_install("git", "build-essential", "libcudnn9-dev-cuda-12")
    .pip_install(
        "torch==2.5.1",
        "flash-attn==2.7.3",  # (2.6.3 and prior do not work)
        "stripedhyena==0.2.2",
        "einops==0.8.0",
        "transformer-engine==1.13",  # <-- Add the compatible version here
        gpu=build_gpu,  # GPU needed for CUDA kernel compilation
        extra_options="--no-build-isolation",  # flash-attn's build imports torch; use env where torch is installed
    )
    .run_commands(
        "git clone --recurse-submodules https://github.com/ArcInstitute/evo2.git /tmp/evo2",
        f"cd /tmp/evo2 && git switch --detach {evo2_github_commit_hash}",
        "cd /tmp/evo2 && pip install . --no-build-isolation",
        gpu=build_gpu,  # GPU needed for potential CUDA extension compilation
    )
)
# Finally, add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)


# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config(**variant_config)
logger.info("App name: %s", app_name)
app = modal.App(app_name, image=image)


# Note: GPU snapshots are not used (transformer_engine/flash-attn prevent them).
# Instead, the CPU two-phase snapshot pattern is used: snap=True loads on CPU,
# snap=False moves the model to GPU after snapshot restore.


@app.cls(
    image=image,
    secrets=runtime_secrets(),
    enable_memory_snapshot=True,
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class Evo2Model(ModelMixinSnap):
    """
    Evo2Model class offers these endpoints:
      - encode() => computes embeddings (mean, last, etc.)
      - log_prob() => total log-prob of a DNA sequence
      - generate() => sequence generation from a prompt
    """

    model_variant: Evo2ModelVariants = Evo2ModelVariants(model_variant)

    @modal.enter(snap=True)
    def load_model(self) -> None:
        """Prepare environment for memory snapshot without loading CUDA-dependent libraries."""
        import torch

        logger.info("Loading Evo2 model on CPU for memory snapshot...")

        self.torch = torch
        self.model_dir = get_model_dir(model_variant)

        # Set Huggingface Hub cache dir
        os.environ["HF_HUB_CACHE"] = str(self.model_dir)
        logger.info("HF_HUB_CACHE is set to: %s", os.environ["HF_HUB_CACHE"])

        # Store model configuration for later initialization
        self.model_name = f"evo2_{self.model_variant.replace('-', '_')}"

        logger.info("Environment prepared for Evo2 model '%s'", self.model_variant)

    @modal.enter(snap=False)
    def setup_model(self) -> None:
        """Load model and move to GPU after snapshot restore."""
        logger.info("Loading and setting up Evo2 model after snapshot restore...")
        from evo2 import Evo2

        # Initialize model
        logger.info("Loading Evo2 model variant '%s'...", self.model_variant)
        self.model = Evo2(model_name=self.model_name)
        logger.info("Successfully initialized Evo2 model")

        # Set model to eval mode
        self.model.model.eval()
        self.torch.set_grad_enabled(False)

        # Move model to GPU
        self.device = get_torch_device()
        self.model.model.to(device=self.device, non_blocking=False)
        logger.info("Evo2 model moved to %s", self.device)

        # Determine max block index
        sd_keys = list(self.model.model.state_dict().keys())
        block_nums = sorted(
            {int(k.split(".")[1]) for k in sd_keys if k.startswith("blocks.")}
        )
        self.max_block = max(block_nums)
        logger.info(
            "Found %s total blocks (0..%s).", self.max_block + 1, self.max_block
        )

        logger.info("Evo2 model '%s' fully loaded and ready.", self.model_variant)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(self, payload: Evo2EncodeRequest) -> Evo2EncodeResponse:
        """
        Compute embeddings from user-specified layers (including negative indexing).

        For each layer -> Return 'mean' or 'last' embeddings, depending on payload.params.include.
        """
        sequences = [item.sequence for item in payload.items]
        includes = payload.params.include
        requested_layers = payload.params.embedding_layers
        mlpl = payload.params.mlp_layer  # 3 by default

        batch_size = len(sequences)
        pad_id = self.model.tokenizer.pad_id

        input_ids_list = [self.model.tokenizer.tokenize(seq) for seq in sequences]
        max_len = max(len(ids) for ids in input_ids_list)
        input_ids_tensor = self.torch.tensor(
            [ids + [pad_id] * (max_len - len(ids)) for ids in input_ids_list],
            dtype=self.torch.long,
            device=self.device,
        )

        # Resolve each requested layer index => actual block number
        # Check out-of-bounds
        actual_layer_indexes = []
        for idx in requested_layers:
            if idx < 0:
                resolved = self.max_block + idx + 1  # e.g. -1 => last block
            else:
                resolved = idx
            if resolved < 0 or resolved > self.max_block:
                raise ValidationError400(
                    f"Requested layer index {idx} resolved to {resolved}, "
                    f"which is out of bounds (0..{self.max_block}) for model {self.model_variant}."
                )
            actual_layer_indexes.append(resolved)

        # Build the layer_names to extract => e.g. blocks.24.mlp.l3
        layer_names = [
            f"blocks.{layer_idx}.mlp.l{mlpl}" for layer_idx in actual_layer_indexes
        ]

        # Forward pass: we want multiple layers => pass a list
        _, emb_dict = self.model(
            input_ids_tensor,
            return_embeddings=True,
            layer_names=layer_names,
        )

        # Build attention mask to handle padded tokens
        mask = (input_ids_tensor != pad_id).float()

        results = []
        for b in range(batch_size):
            seq_len = int(mask[b].sum().item())
            # We'll store a list of Evo2EncodeResponseEmbedding, one per layer
            layer_embeddings = []

            for i, layer_idx in enumerate(actual_layer_indexes):
                layer_key = layer_names[i]  # e.g. "blocks.24.mlp.l3"
                if layer_key not in emb_dict:
                    raise ValidationError400(
                        f"MLP sublayer index {mlpl} is not valid for model {self.model_variant}. "
                        f"Layer key '{layer_key}' was not found in the model output."
                    )
                row_emb_3d = emb_dict[layer_key][b, :seq_len, :]  # [L, hidden_dim]

                # Prepare the output record for this layer
                emb_record: dict[str, Any] = {"layer": layer_idx}

                if Evo2EncodeIncludeOptions.MEAN in includes:
                    mean_vec = row_emb_3d.mean(dim=0).cpu().tolist()
                    emb_record["mean"] = mean_vec

                if Evo2EncodeIncludeOptions.LAST in includes:
                    last_vec = row_emb_3d[-1].cpu().tolist() if seq_len > 0 else [0.0]
                    emb_record["last"] = last_vec

                layer_embeddings.append(
                    Evo2EncodeResponseEmbedding.model_validate(emb_record)
                )

            # Add to results
            results.append(Evo2EncodeResponseResult(embeddings=layer_embeddings))

        return Evo2EncodeResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def log_prob(self, payload: Evo2LogProbRequest) -> Evo2LogProbResponse:
        """
        Computes the total log-probability of each DNA sequence by summing
        over all positions. This uses the model's built-in .score_sequences()
        with 'reduce_method="sum"'.
        """
        sequences = [item.sequence for item in payload.items]

        # We'll pass them all in a single batch if it's short
        scores = self.model.score_sequences(
            seqs=sequences,
            batch_size=1,
            prepend_bos=False,
            reduce_method="sum",
            average_reverse_complement=False,
            # When True, the average of the forward and reverse complement scores is returned.
        )
        # Convert floats to the response format
        results = [Evo2LogProbResponseResult(log_prob=float(x)) for x in scores]
        return Evo2LogProbResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def generate(self, payload: Evo2GenerateRequest) -> Evo2GenerateResponse:
        """
        Generates new DNA sequences from a prompt, using the model's
        .generate() function with typical parameters (temperature, top-k, top-p).
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
        params = payload.params
        for item in payload.items:
            output = self.model.generate(
                prompt_seqs=[item.prompt],
                n_tokens=params.max_new_tokens,
                temperature=params.temperature,
                top_k=params.top_k,
                top_p=params.top_p,
                batched=False,
                cached_generation=True,
                verbose=0,
            )
            results.append(Evo2GenerateResponseResult(generated=output.sequences[0]))
        return Evo2GenerateResponse(results=results)


if __name__ == "__main__":
    """
    Usage:
        MODEL_VARIANT="1b-base" python models/evo2/app.py
        MODEL_VARIANT="7b-base" python models/evo2/app.py

        # Force deploy:
        MODEL_VARIANT="1b-base" python models/evo2/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        Evo2Model,
        description=f"Run and optionally deploy the {Evo2Params.display_name} {model_variant} Modal app.",
    )
