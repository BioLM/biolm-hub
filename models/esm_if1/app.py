import logging

import modal

from models.commons.model.base import ModelMixinSnap
from models.commons.core.decorator import modal_endpoint
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
)
from models.commons.util.device import get_torch_device
from models.esm_if1.config import MODEL_FAMILY, ESMIF1ResourceSpec
from models.esm_if1.schema import (
    ESMIF1GenerateRequest,
    ESMIF1GenerateResponse,
    ESMIF1GenerateResponseSample,
    ESMIF1Params,
)

# Build Modal container image
# Pinned: esm+openfold incompatible with Python 3.12
image = modal.Image.from_registry("pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime")
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=ESMIF1Params.base_model_slug,
    params_version=ESMIF1Params.params_version,
    variant_config=None,  # this model has no variants
    sub_path="checkpoints",
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .apt_install("git", "gcc", "g++")
    .pip_install(
        "torch==2.0.1",
        "biotite == 0.39.0",
        # Install fair-esm 2.0.1 from GitHub ZIP archive (latest version from pip is 2.0.0)
        "https://github.com/facebookresearch/esm/archive/2b369911bb5b4b0dda914521b9475cad1656b2ac.zip",
        # ESM-IF1 dependencies
        "torch_geometric == 2.4.0",
        "torch_scatter == 2.1.2",
        # Openfold and its dependencies (for ESMFold and ESM-IF1)
        "git+https://github.com/aqlaboratory/openfold.git@447670c03d00534007b3f1f51ef5be9b19efaca8",
        "dllogger@git+https://github.com/NVIDIA/dllogger.git@0540a43971f4a8a16693a9de9de73c1072020769",
        "dm-tree == 0.1.8",
        "einops == 0.7.0",
        "ml-collections == 0.1.1",
        "modelcif == 0.9",
        "omegaconf == 2.3.0",
        "pytorch_lightning == 2.1.3",
        "scipy == 1.11.4",
        gpu=ESMIF1ResourceSpec.gpu,
        extra_options="--no-build-isolation",  # openfold's setup.py imports torch; use env where torch is installed
    )
)
# Finally, add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)


# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config()
print(f"App name: {app_name}")
app = modal.App(app_name, image=image)


@app.cls(
    image=image,
    secrets=[cloudflare_r2_secret],
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class ESMIF1Model(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def setup_model(self):
        """Load model directly on GPU for GPU memory snapshot."""
        import esm
        import torch

        print("🚀 Loading ESM-IF1 model directly on GPU for GPU memory snapshot...")

        self.torch = torch
        self.device = get_torch_device()

        # Get base model dir (without checkpoints subdirectory) for torch.hub.set_dir
        from models.commons.storage.downloads import get_model_dir_util

        self.model_dir = get_model_dir_util(
            base_model_slug=ESMIF1Params.base_model_slug,
            params_version=ESMIF1Params.params_version,
        )

        # Set the Torch Hub cache directory to the internal model path
        torch.hub.set_dir(self.model_dir)

        # Load the model and alphabet directly on GPU
        print(f"⏳ Initiating load of ESMIF1 from: {self.model_dir} directly on GPU...")
        self.model, self.alphabet = esm.pretrained.esm_if1_gvp4_t16_142M_UR50()
        self.model = self.model.eval()

        # Move model to GPU
        self.model.to(device=self.device)

        print(
            f"✅ ESM-IF1 model loaded directly on {self.device} for GPU memory snapshot!"
        )

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def generate(self, payload: ESMIF1GenerateRequest) -> ESMIF1GenerateResponse:
        """
        Performs generation using the ESMIF1 model.

        Parameters:
        - payload (ESMIF1GenerateRequest): The request object containing pdbs.

        Returns:
        - ESMIF1GenerateResponse: The response containing generation results.
        """
        import random
        import time

        import numpy as np

        from models.esm_if1._sample_sequences import _sample_seq_singlechain

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

        chain = payload.params.chain
        num_samples = payload.params.num_samples
        temperature = payload.params.temperature

        multichain_backbone = payload.params.multichain_backbone
        if multichain_backbone:

            raise NotImplementedError("Multichain backbone not supported yet.")

        items = payload.items

        results: list[list[ESMIF1GenerateResponseSample]] = []
        for item in items:
            pdb_string = item.pdb

            try:
                sampled_sequences = _sample_seq_singlechain(
                    pdb_string=pdb_string,
                    chain=chain,
                    num_samples=num_samples,
                    temperature=temperature,
                    model=self.model,
                    device=self.device,
                )
                result = [
                    ESMIF1GenerateResponseSample(
                        sequence=seq["sequence"], recovery=seq["recovery"]
                    )
                    for seq in sampled_sequences
                ]
                results.append(result)

            except RuntimeError as e:
                if "CUDA out of memory" in str(e):
                    logging.error(
                        f"Failed (CUDA out of memory) on batch with sequences: {pdb_string[:500]}."
                    )
                    empty_result = [
                        ESMIF1GenerateResponseSample(sequence="", recovery=0.0)
                    ]
                    results.append(empty_result)
                    self.torch.cuda.empty_cache()
                    continue
                raise

        return ESMIF1GenerateResponse(results=results)


if __name__ == "__main__":
    """
    Usage:
        python models/esm_if1/app.py

        # Force deploy to "qa" or "main" environment:
        python models/esm_if1/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        ESMIF1Model,
        description=f"Run and optionally deploy the {ESMIF1Params.display_name} Modal app.",
    )
