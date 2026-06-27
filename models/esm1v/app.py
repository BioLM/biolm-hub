import modal

from models.commons.billing.mixin import BillingMixinSnap
from models.commons.core.decorator import modal_endpoint
from models.commons.data.validator import aa_unambiguous
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
    redis_url_secret,
)
from models.commons.util.device import get_torch_device
from models.commons.util.environment import parse_variant
from models.esm1v.config import MODEL_FAMILY
from models.esm1v.download import get_model_dir
from models.esm1v.schema import (
    ESM1vModelNumbers,
    ESM1vParams,
    ESM1vPredictRequest,
    ESM1vPredictResponse,
    ESM1vPredictResponseLabel,
)

# Define the set of unambiguous amino acids
aa_unambiguous_list = list(aa_unambiguous)
n_aa_unambiguous = len(aa_unambiguous_list)


variant_config = parse_variant(
    env_var_name="MODEL_NUMBER",
    allowed_values=ESM1vModelNumbers,
    default=ESM1vModelNumbers.ALL,
)
model_number = variant_config["MODEL_NUMBER"]


# Build Modal container image
image = modal.Image.from_registry("pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime")
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=ESM1vParams.base_model_slug,
    params_version=ESM1vParams.params_version,
    variant_config=variant_config,
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        "transformers==4.36.2",
        "safetensors==0.5.3",
    )
)
# Finally, add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)


# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config(**variant_config)
print(f"App name: {app_name}")
app = modal.App(app_name, image=image)


@app.cls(
    image=image,
    secrets=[cloudflare_r2_secret, redis_url_secret],
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class ESM1vModel(BillingMixinSnap):
    app_username: str = modal.parameter(default="default_user")
    model_number: str = model_number

    @modal.enter(snap=True)
    def setup_model(self):
        """Load model(s) directly on GPU for GPU memory snapshot with deterministic behavior."""
        import torch
        from transformers import EsmForMaskedLM, EsmTokenizer, pipeline

        print("🚀 Loading ESM1v model(s) directly on GPU for GPU memory snapshot...")

        # Set deterministic behavior for consistent results
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.torch = torch

        # Get device and setup for GPU inference
        self.device = get_torch_device()

        self.model_dir = get_model_dir(self.model_number)
        self.fill_masker_pipelines = {}

        if self.model_number == "all":
            model_dirs = [d for d in self.model_dir.iterdir() if d.is_dir()]
        else:
            model_dirs = [self.model_dir]

        for model_dir in model_dirs:
            model_name = model_dir.name
            print(
                f"⏳ Loading ESM1v model '{model_name}' directly on {self.device} from: {model_dir}"
            )
            try:
                tokenizer = EsmTokenizer.from_pretrained(model_dir)
                model = EsmForMaskedLM.from_pretrained(model_dir)
                model = model.to(self.device)
                model.eval()

                model_num = model_name.split("_")[-1]
                model_name_key = f"esm1v-n{model_num}"

                # Create pipeline directly on GPU
                fill_masker_pipeline = pipeline(
                    "fill-mask", model=model, tokenizer=tokenizer, device=self.device
                )
                fill_masker_pipeline.model.eval()
                self.fill_masker_pipelines[model_name_key] = fill_masker_pipeline

                print(f"✅ Loaded ESM1v model '{model_name}' directly on {self.device}")
            except Exception as e:
                print(f"❌ Failed to load model '{model_name}': {e}")
                raise e

        print(
            f"✅ ESM1v model(s) loaded directly on {self.device} for GPU memory snapshot!"
        )

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict(self, payload: ESM1vPredictRequest) -> ESM1vPredictResponse:
        """
        Performs prediction using the ESM1v model(s).

        Parameters:
        - payload (ESM1vPredictRequest): The request object containing sequences.

        Returns:
        - ESM1vPredictResponse: The response containing prediction results.
        """
        sequences = [item.sequence for item in payload.items]

        results = []
        for idx, sequence in enumerate(sequences):
            result = {}
            for model_name, fill_masker_pipeline in self.fill_masker_pipelines.items():
                print(f"Predicting for sequence {idx+1} with model {model_name}")

                try:
                    resp = fill_masker_pipeline(
                        sequence, targets=aa_unambiguous_list, top_k=n_aa_unambiguous
                    )
                except Exception as e:
                    print(
                        f"Model call failed for sequence {idx+1} with model {model_name}"
                    )
                    raise e

                resp_sorted = sorted(resp, key=lambda x: x["score"], reverse=True)
                result[model_name] = [
                    ESM1vPredictResponseLabel.model_validate(label)
                    for label in resp_sorted
                ]

            results.append(result)

        if self.model_number == "all":
            return ESM1vPredictResponse(results=results)
        else:
            model_name_key = f"esm1v-{self.model_number}"
            # For models esm1v-n1 to esm1v-n5, the schema is slightly different
            results_ = [result.get(model_name_key, []) for result in results]
            return ESM1vPredictResponse(results=results_)


if __name__ == "__main__":
    """
    Usage:
        MODEL_NUMBER="all" python models/esm1v/app.py

        # Force deploy to "qa" or "main" environment:
        MODEL_NUMBER="all" python models/esm1v/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        ESM1vModel,
        description=f"Run and optionally deploy the {ESM1vParams.display_name} {model_number} Modal app.",
    )
