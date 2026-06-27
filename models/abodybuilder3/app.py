import os
import random

import modal

from models.abodybuilder3.config import (
    MODEL_FAMILY,
    abodybuilder3_commit_hash,
)
from models.abodybuilder3.download import get_model_dir
from models.abodybuilder3.schema import (
    AbodyBuilder3ModelTypes,
    AbodyBuilder3Params,
    AbodyBuilder3PredictRequest,
    AbodyBuilder3PredictResponse,
    AbodyBuilder3PredictResponseResult,
)
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
from models.commons.util.environment import parse_variant

variant_config = parse_variant(
    env_var_name="MODEL_TYPE",
    allowed_values=AbodyBuilder3ModelTypes,
    default=AbodyBuilder3ModelTypes.PLDDT,
)
model_type = variant_config["MODEL_TYPE"]


# Build Modal container image
image = modal.Image.micromamba(python_version="3.10")
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=AbodyBuilder3Params.base_model_slug,
    params_version=AbodyBuilder3Params.params_version,
    variant_config=variant_config,
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .apt_install(["git", "wget", "gcc", "g++", "libffi-dev"])
    # Install OpenMM via micromamba (not pip to avoid conflicts)
    .micromamba_install("openmm=8.1.1", channels=["conda-forge"])
    .micromamba_install(spec_file="models/abodybuilder3/environment_gpu.yml")
    .pip_install_from_requirements(
        requirements_txt="models/abodybuilder3/pinned-versions.txt"
    )
    # Fix conda/pip charset_normalizer conflict: micromamba installs 3.4.x with
    # compiled Cython extensions that reference symbols missing in 3.3.x's .py files.
    # Must fully purge conda's version before pip install to avoid stale .so files.
    .run_commands(
        "pip uninstall -y charset-normalizer 2>/dev/null; "
        "rm -rf /opt/conda/lib/python3.10/site-packages/charset_normalizer* ; "
        "pip install charset-normalizer==3.3.2"
    )
    .run_commands(
        f"git clone https://github.com/Exscientia/abodybuilder3.git && "
        f"cd abodybuilder3 && "
        f"git switch --detach {abodybuilder3_commit_hash}"
    )
    .workdir("./abodybuilder3")  # Needed since relative imports withing the repo
    # Remove any legacy simtk.openmm references
    .run_commands(
        "pip uninstall -y simtk.openmm || true",
    )
    # Set environment variables to suppress warnings
    .env(
        {
            "TRANSFORMERS_NO_ADVISORY_WARNINGS": "1",
            "TOKENIZERS_PARALLELISM": "false",
        }
    )
    .run_commands('pip install -e ".[dev]"')
)
# Finally, add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)


# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config(**variant_config)
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
class AbodyBuilder3Model(ModelMixinSnap):
    model_type: str = model_type
    app_username: str = modal.parameter(default="default_user")

    def _load_prott5_on_device(self, torch, device):
        """Load ProtT5 language model directly on device for GPU memory snapshot."""

        from abodybuilder3.language.model import ProtT5

        print("Loading ProtT5 language model directly on GPU...")

        with torch.no_grad():
            self.plm = ProtT5(weights_dir=f"{self.model_dir}/prott5/")
            self.plm.embedding_module = self.plm.embedding_module.to(device)

    def _load_litabb3_checkpoint(self, model_type_name, device):
        """Load LitABB3 checkpoint directly on device for GPU memory snapshot."""
        from abodybuilder3.lightning_module import LitABB3

        print(f"Loading LitABB3 {model_type_name} checkpoint directly on GPU...")
        module = LitABB3.load_from_checkpoint(
            f"{self.model_dir}/{model_type}-loss/best_second_stage.ckpt",
            map_location=device,
        )
        self.model = module.model.to(device)
        print(f"✅ LitABB3 {model_type_name} checkpoint loaded successfully on GPU")

    @modal.enter(snap=True)
    def setup_model(self):
        """Load model directly on GPU for GPU memory snapshot with deterministic behavior."""
        import torch

        print(
            "🚀 Loading AbodyBuilder3 model directly on GPU for GPU memory snapshot..."
        )

        # Set deterministic behavior for consistent results
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.torch = torch
        self.model_dir = get_model_dir()

        # Get device and setup for GPU inference
        self.device = get_torch_device()

        print(
            f"⏳ Loading AbodyBuilder3 model '{self.model_type}' directly on {self.device} from: {self.model_dir}"
        )

        # Load models directly on GPU for snapshot - only load what's needed for each model type
        if model_type == AbodyBuilder3ModelTypes.LANGUAGE:
            self._load_prott5_on_device(torch, self.device)
            self._load_litabb3_checkpoint("language", self.device)
        elif model_type == AbodyBuilder3ModelTypes.PLDDT:
            self.plm = None
            self._load_litabb3_checkpoint("plddt", self.device)
        else:
            raise ValueError(f"Unsupported model type: {model_type}")

        print(
            f"✅ AbodyBuilder3 model '{self.model_type}' loaded directly on {self.device} for GPU memory snapshot!"
        )

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def fold(
        self, payload: AbodyBuilder3PredictRequest
    ) -> AbodyBuilder3PredictResponse:
        """
        Performs structure prediction using the AbodyBuilder3 models.

        Parameters:
        - payload (AbodyBuilder3PredictRequest): The request object containing sequences and parameters.

        Returns:
        - AbodyBuilder3PredictResponse: The response containing pdb predictions results.
        """
        from abodybuilder3.utils import (
            add_atom37_to_output,
            output_to_pdb,
            string_to_input,
        )

        results = []

        self.seed_everything(payload.params.seed)

        try:
            for input in payload.items:

                heavy = input.H
                light = input.L
                ab_input = string_to_input(heavy=heavy, light=light)
                if model_type == AbodyBuilder3ModelTypes.LANGUAGE:
                    embedding = self.plm.get_embeddings(
                        [
                            heavy,
                        ],
                        [
                            light,
                        ],
                    )
                    print(f"{embedding[0].shape=}")
                    ab_input["single"] = embedding[0].unsqueeze(0)

                ab_input_batch = {
                    key: (
                        value.unsqueeze(0).to(self.device)
                        if key not in ["single", "pair"]
                        else value.to(self.device)
                    )
                    for key, value in ab_input.items()
                }
                output = self.model(ab_input_batch, ab_input_batch["aatype"])
                output = add_atom37_to_output(
                    output, ab_input["aatype"].to(self.device)
                )
                pdb_string = output_to_pdb(output, ab_input)
                result_dict = {"pdb": pdb_string}
                if payload.params.plddt:
                    result_dict["plddt"] = output["plddt"].squeeze(0).tolist()

                results.append(AbodyBuilder3PredictResponseResult(**result_dict))

        except Exception as e:
            print(f"Model call failed with error [{e}]")
            raise e

        return AbodyBuilder3PredictResponse(results=results)

    def seed_everything(self, seed: int = 42, deterministic: bool = True):

        import numpy as np
        import pytorch_lightning as pl
        import torch

        """Set seed for reproducibility across random, NumPy, torch, and PyTorch Lightning.

        Args:
            seed (int): Seed value.
            deterministic (bool): If True, sets flags for deterministic behavior.
        """
        # Python & NumPy
        random.seed(seed)
        np.random.seed(seed)

        # Torch
        torch.manual_seed(seed)
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)  # for multi-GPU

        # Torch determinism
        torch.backends.cudnn.deterministic = deterministic
        torch.backends.cudnn.benchmark = not deterministic

        # Lightning
        pl.seed_everything(seed, workers=True)

        # OS-level (hash-based randomness in Python)
        os.environ["PYTHONHASHSEED"] = str(seed)

        print(f"🔒 Seeding everything with seed {seed}. Deterministic: {deterministic}")


if __name__ == "__main__":
    """
    Usage:
        MODEL_TYPE="plddt" python models/abodybuilder3/app.py

        # Force deploy to "qa" or "main" environment:
        MODEL_TYPE="plddt" python models/abodybuilder3/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        AbodyBuilder3Model,
        description=f"Run and optionally deploy the {AbodyBuilder3Params.display_name} {model_type} Modal app.",
    )
