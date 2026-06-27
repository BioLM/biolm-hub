import os
import random
import tempfile

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
from models.commons.util.environment import parse_variant
from models.immunebuilder.config import MODEL_FAMILY
from models.immunebuilder.download import get_model_dir
from models.immunebuilder.schema import (
    ImmuneBuilderModelTypes,
    ImmuneBuilderParams,
    ImmuneBuilderPredictRequest,
    ImmuneBuilderPredictRequestItem,
    ImmuneBuilderPredictResponse,
    ImmuneBuilderPredictResponseResult,
)

variant_config = parse_variant(
    env_var_name="MODEL_TYPE",
    allowed_values=ImmuneBuilderModelTypes,
    default=ImmuneBuilderModelTypes.TCRBUILDER2,
    # var_is_required=True,
)
model_type = variant_config["MODEL_TYPE"]


def prebuild_immunebuilder_models():
    """
    Pre-download ImmuneBuilder models during the build phase to avoid download
    during memory snapshot creation.
    """
    import time

    from ImmuneBuilder import ABodyBuilder2, NanoBodyBuilder2, TCRBuilder2

    model_dir = get_model_dir(model_type)

    print(f"🔄 Pre-building ImmuneBuilder model '{model_type}' during build phase...")
    print(f"📂 Model directory: {model_dir}")
    print(f"🎯 Loading ONLY {model_type} model (not all variants!)")
    print(f"🕒 Start time: {time.strftime('%H:%M:%S')}")

    start_time = time.time()

    # Ensure the model directory exists
    model_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Initialize the specific model based on enum (no string fallback needed)
        print(f"🔍 Initializing {model_type} model...")

        if model_type == ImmuneBuilderModelTypes.NANOBODYBUILDER2:
            print("⏳ Initializing NanoBodyBuilder2...")
            model = NanoBodyBuilder2(weights_dir=model_dir)
        elif model_type == ImmuneBuilderModelTypes.ABODYBUILDER2:
            print("⏳ Initializing ABodyBuilder2...")
            model = ABodyBuilder2(weights_dir=model_dir)
        elif model_type == ImmuneBuilderModelTypes.TCRBUILDER2PLUS:
            print("⏳ Initializing TCRBuilder2Plus...")
            model = TCRBuilder2(weights_dir=model_dir)
        elif model_type == ImmuneBuilderModelTypes.TCRBUILDER2:
            print("⏳ Initializing TCRBuilder2...")
            model = TCRBuilder2(
                weights_dir=model_dir, use_TCRBuilder2_PLUS_weights=False
            )
        else:
            # This should not happen with proper enum validation
            raise ValueError(
                f"Unknown model type: {model_type}. "
                f"Available types: {list(ImmuneBuilderModelTypes)}"
            )

        end_time = time.time()
        duration = end_time - start_time
        print(
            f"✅ Successfully pre-built ImmuneBuilder model '{model_type}' in {duration:.2f}s"
        )
        print(f"🕒 End time: {time.strftime('%H:%M:%S')}")

        # Check if weights were loaded from R2 or downloaded from library remote
        if model_dir.exists() and any(model_dir.iterdir()):
            print("🚀 Model weights loaded from R2 cache!")
        else:
            print("🌐 Model weights downloaded from ImmuneBuilder library remote")

        # Clean up the model object to free memory
        del model

    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        print(f"⚠️ Error during model pre-build after {duration:.2f}s: {e}")
        print("💡 Model will be downloaded during runtime instead")
        # Don't fail the build, just log the issue


# Build Modal container image
image = modal.Image.micromamba(python_version="3.12")
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=ImmuneBuilderParams.base_model_slug,
    params_version=ImmuneBuilderParams.params_version,
    variant_config=variant_config,
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .micromamba_install("openmm=8.4.0", "pdbfixer=1.10", channels=["conda-forge"])
    .apt_install("git", "wget")
    .micromamba_install("biopython", channels=["conda-forge"])
    .micromamba_install("hmmer=3.3.2", channels=["conda-forge", "bioconda"])
    # Install ANARCI for antibody numbering (PyPI package includes pre-built
    # germline data — avoids flaky IMGT server fetches during source build)
    .uv_pip_install("anarci==2026.2.13.2")
    .uv_pip_install("ImmuneBuilder==1.2")
    .apt_install("libopenblas-dev")
    .run_function(prebuild_immunebuilder_models)
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
class ImmuneBuilderModel(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")
    model_type: str = model_type

    def _load_model_by_type(self, weights_dir):
        """Load the appropriate model based on model_type.

        Args:
            weights_dir: Required path to model weights directory.
                         This ensures we always use R2 cached weights when available.
        """
        import time

        from ImmuneBuilder import ABodyBuilder2, NanoBodyBuilder2, TCRBuilder2

        if weights_dir is None:
            raise ValueError("weights_dir is required for _load_model_by_type()")

        print(f"🎯 Loading {self.model_type} with weights_dir: {weights_dir}")

        # Check if we're using R2 cache or library remote
        if weights_dir.exists() and any(weights_dir.glob(f"{self.model_type}/*")):
            print(f"🚀 Using R2 cached weights from: {weights_dir}/{self.model_type}/")
            source = "R2 cache"
        else:
            print("🌐 No R2 cache found, will download from library remote")
            source = "library remote"

        load_start = time.time()

        if self.model_type == ImmuneBuilderModelTypes.NANOBODYBUILDER2:
            model = NanoBodyBuilder2(weights_dir=weights_dir)
        elif self.model_type == ImmuneBuilderModelTypes.ABODYBUILDER2:
            model = ABodyBuilder2(weights_dir=weights_dir)
        elif self.model_type == ImmuneBuilderModelTypes.TCRBUILDER2PLUS:
            model = TCRBuilder2(weights_dir=weights_dir)
        elif self.model_type == ImmuneBuilderModelTypes.TCRBUILDER2:
            model = TCRBuilder2(
                weights_dir=weights_dir, use_TCRBuilder2_PLUS_weights=False
            )
        else:
            raise ValueError(f"Invalid ImmuneBuilder Model Type: {self.model_type}")

        load_duration = time.time() - load_start
        print(f"✅ Model loaded from {source} in {load_duration:.2f}s")
        return model

    @modal.enter(snap=True)
    def setup_model(self):
        """Load model directly on GPU for GPU memory snapshot with deterministic behavior."""
        import time

        import torch

        print(
            "🚀 Loading ImmuneBuilder model directly on GPU for GPU memory snapshot..."
        )
        print(f"🕒 Load start time: {time.strftime('%H:%M:%S')}")

        load_start_time = time.time()

        # Set deterministic behavior for consistent results
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.torch = torch
        self.model_dir = get_model_dir(self.model_type)

        # Get device and setup for GPU inference
        self.device = get_torch_device()

        print(
            f"⏳ Loading ImmuneBuilder model '{self.model_type}' directly on GPU from: {self.model_dir}"
        )

        # Load model - ImmuneBuilder models handle device loading internally
        # and will download models automatically if they don't exist
        try:
            print(f"🔍 Attempting to load model from: {self.model_dir}")

            # Check if we have R2 cached weights
            if self.model_dir.exists() and any(self.model_dir.iterdir()):
                print("🚀 Found R2 cached weights - loading from cache")
            else:
                print("🌐 No R2 cache found - will download from ImmuneBuilder library")

            model_load_start = time.time()
            self.model = self._load_model_by_type(self.model_dir)
            model_load_duration = time.time() - model_load_start

            print(f"⏱️ Model loading took {model_load_duration:.2f}s")

        except Exception as e:
            print(f"❌ Error loading model: {e}")
            print(
                "🔧 Attempting to resolve by allowing ImmuneBuilder to download models..."
            )

            # Since weights_dir is now required, we can't retry without it
            print(f"❌ Failed to load model from {self.model_dir}: {e}")
            raise e

        load_end_time = time.time()
        total_duration = load_end_time - load_start_time
        print(
            f"✅ ImmuneBuilder model '{self.model_type}' loaded directly on {self.device} for GPU memory snapshot!"
        )
        print(f"🕒 Total load time: {total_duration:.2f}s")
        print(f"🕒 Load end time: {time.strftime('%H:%M:%S')}")

    def _pre_process_payload(
        self, payload: ImmuneBuilderPredictRequest
    ) -> list[ImmuneBuilderPredictRequestItem]:
        for item in payload.items:
            if item._kind == self.model_type:
                continue  # Valid case
            if (
                item._kind == ImmuneBuilderModelTypes.TCRBUILDER2
                and hasattr(item, "_kind2")
                and item._kind2 == ImmuneBuilderModelTypes.TCRBUILDER2PLUS
                and self.model_type == ImmuneBuilderModelTypes.TCRBUILDER2PLUS
            ):
                continue  # Exception case

            # Create error message that handles missing _kind2
            kind2_str = f" and '{item._kind2}'" if hasattr(item, "_kind2") else ""
            raise ValueError(
                f"Mismatch detected: expected '{self.model_type}' but got '{item._kind}'{kind2_str} in request"
            )

        return payload.items

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict(
        self, payload: ImmuneBuilderPredictRequest
    ) -> ImmuneBuilderPredictResponse:
        """
        Performs structure prediction using the ImmuneBuilder models.

        Parameters:
        - payload (ImmuneBuilderPredictRequest): The request object containing sequences and parameters.

        Returns:
        - ImmuneBuilderPredictResponse: The response containing pdb predictions results.
        """
        inputs = self._pre_process_payload(payload)

        # Set seed for reproducibility
        self.seed_everything(payload.params.seed)

        results = []
        try:
            for input in inputs:
                with tempfile.NamedTemporaryFile(
                    mode="w+", suffix=".pdb", delete=False
                ) as tmp_file:
                    output_file = tmp_file.name

                try:
                    result_obj = self.model.predict(input.model_dump(exclude_none=True))
                    result_obj.save(output_file)
                    with open(output_file) as f:
                        pdb_str = f.read()
                        results.append(ImmuneBuilderPredictResponseResult(pdb=pdb_str))

                finally:
                    if os.path.exists(output_file):
                        os.remove(output_file)

        except Exception as e:
            print(f"Model call failed with error [{e}]")
            raise e

        return ImmuneBuilderPredictResponse(results=results)

    def seed_everything(self, seed: int = 42, deterministic: bool = True):

        import numpy as np
        import torch

        """Set seed for reproducibility across random, NumPy, and torch.

        Args:
            seed (int): Seed value.
            deterministic (bool): If True, sets flags for deterministic behavior.
        """
        # Python & NumPy
        random.seed(seed)
        np.random.seed(seed)

        # Torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)  # for multi-GPU

        # Torch determinism
        torch.backends.cudnn.deterministic = deterministic
        torch.backends.cudnn.benchmark = not deterministic

        # OS-level (hash-based randomness in Python)
        os.environ["PYTHONHASHSEED"] = str(seed)

        print(f"🔒 Seeding everything with seed {seed}. Deterministic: {deterministic}")


if __name__ == "__main__":
    """
    Usage:
        MODEL_TYPE="abodybuilder2" python models/immunebuilder/app.py

        # Force deploy to "qa" or "main" environment:
        MODEL_TYPE="abodybuilder2" python models/immunebuilder/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        ImmuneBuilderModel,
        description=f"Run and optionally deploy the {ImmuneBuilderParams.display_name} {model_type} Modal app.",
    )
