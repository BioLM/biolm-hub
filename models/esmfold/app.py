import logging
from collections.abc import Generator

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
from models.esmfold.config import MODEL_FAMILY, ESMFoldResourceSpec
from models.esmfold.download import get_model_dir
from models.esmfold.schema import (
    ESMFoldParams,
    ESMFoldPredictRequest,
    ESMFoldPredictResponse,
    ESMFoldPredictResponseResult,
)

logger = get_logger(__name__)

# Build Modal container image
# Pinned: esm package mutable dataclass defaults on Python 3.12
image = modal.Image.from_registry("pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime")
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=ESMFoldParams.base_model_slug,
    params_version=ESMFoldParams.params_version,
    variant_config=None,  # this model has no variants
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .apt_install("git", "build-essential")
    .pip_install(
        "torch==2.0.1",
        "biopython==1.83",
        # Install fair-esm 2.0.1 from GitHub ZIP archive (latest version from pip is 2.0.0)
        "https://github.com/facebookresearch/esm/archive/2b369911bb5b4b0dda914521b9475cad1656b2ac.zip",
        # Openfold and its dependencies (for ESMFold and ESM-IF1)
        "git+https://github.com/aqlaboratory/openfold.git@447670c03d00534007b3f1f51ef5be9b19efaca8",
        "dllogger @ git+https://github.com/NVIDIA/dllogger.git@0540a43971f4a8a16693a9de9de73c1072020769",
        "dm-tree==0.1.8",
        "einops==0.7.0",
        "ml-collections==0.1.1",
        "modelcif==0.9",
        "omegaconf==2.3.0",
        "pytorch_lightning==2.1.3",
        "scipy==1.11.4",
        gpu=ESMFoldResourceSpec.gpu,
        extra_options="--no-build-isolation",  # openfold's setup.py imports torch; use env where torch is installed
    )
)
# Finally, add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)


# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config()
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
class ESMFoldModel(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")

    batch_size = ESMFoldParams.batch_size
    chunk_size = ESMFoldParams.max_sequence_len

    @modal.enter(snap=True)
    def setup_model(self):
        """Load model directly on GPU for GPU memory snapshot with deterministic behavior."""
        import esm
        import torch

        logger.info("Loading ESMFold model directly on GPU for GPU memory snapshot...")

        # Set deterministic behavior for consistent results
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.torch = torch
        self.device = get_torch_device()
        self.model_dir = get_model_dir()

        # Set the Torch Hub cache directory to the internal model path
        torch.hub.set_dir(self.model_dir)

        # Load the model directly on GPU
        logger.info(
            "Initiating load of ESMFold model from: %s directly on GPU...",
            self.model_dir,
        )
        self.model = esm.pretrained.esmfold_v1()
        self.model.set_chunk_size(self.chunk_size)
        self.model.eval()

        # Move model to GPU
        self.model.to(device=self.device)

        logger.info(
            "ESMFold model loaded directly on %s for GPU memory snapshot!", self.device
        )

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def fold(
        self,
        payload: ESMFoldPredictRequest,
    ) -> ESMFoldPredictResponse:
        """
        Performs prediction using the ESMFold model.

        Parameters:
        - payload (ESMFoldPredictRequest): The request object containing sequences.

        Returns:
        - ESMFoldPredictResponse: The response containing prediction results.
        """
        sequences = [item.sequence for item in payload.items]
        max_tokens_per_batch = 1024  # Adjust as needed

        batched_sequences_gen = self.create_batched_sequences(
            sequences, max_tokens_per_batch
        )

        results = []
        for headers, batch in batched_sequences_gen:
            try:
                outputs = self.model.infer(batch, num_recycles=4)
                pdbs = self.model.output_to_pdb(outputs)

                # Post-process the output for each sequence in the batch
                for idx, _header in enumerate(headers):
                    pdb = pdbs[idx]
                    # NOTE: when dealing with `outputs`, be careful about
                    # which dimension represents the batch, since different
                    # for different values
                    mean_plddt = float(outputs["mean_plddt"][idx].cpu())
                    ptm = float(outputs["ptm"][idx].cpu())

                    result = ESMFoldPredictResponseResult(
                        pdb=pdb,
                        mean_plddt=mean_plddt,
                        ptm=ptm,
                    )
                    results.append(result)

            except RuntimeError as e:
                if "CUDA out of memory" in str(e):
                    logging.error(
                        f"Failed (CUDA out of memory) on batch with sequences: {headers}."
                    )
                    empty_result = ESMFoldPredictResponseResult(
                        pdb="",
                        mean_plddt=0.0,
                        ptm=0.0,
                    )
                    results.extend([empty_result] * len(headers))
                    continue
                raise

        return ESMFoldPredictResponse(results=results)

    def create_batched_sequences(
        self, sequences: list[str], max_tokens_per_batch: int = 1024
    ) -> Generator[tuple[list[str], list[str]], None, None]:
        """Batch sequences based on the token limit."""
        batch_headers: list[str] = []
        batch_sequences: list[str] = []
        num_tokens = 0
        for idx, seq in enumerate(sequences):
            header = f"seq_{idx}"
            if (len(seq) + num_tokens > max_tokens_per_batch) and num_tokens > 0:
                yield batch_headers, batch_sequences
                batch_headers, batch_sequences, num_tokens = [], [], 0
            batch_headers.append(header)
            batch_sequences.append(seq)
            num_tokens += len(seq)

        if batch_sequences:
            yield batch_headers, batch_sequences


if __name__ == "__main__":
    """
    Usage:
        python models/esmfold/app.py

        # Force deploy to "qa" or "main" environment:
        python models/esmfold/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        ESMFoldModel,
        description=f"Run and optionally deploy the {ESMFoldParams.display_name} Modal app.",
    )
