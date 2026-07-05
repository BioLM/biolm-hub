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
from models.igt5.config import MODEL_FAMILY, model_id_mapping
from models.igt5.download import get_model_dir
from models.igt5.schema import (
    IgT5EncodeIncludeOptions,
    IgT5EncodeRequest,
    IgT5EncodeResponse,
    IgT5EncodeResponseResult,
    IgT5ModelTypes,
    IgT5Params,
)

logger = get_logger(__name__)

variant_config = parse_variant(
    env_var_name="MODEL_TYPE",
    allowed_values=IgT5ModelTypes,
    default=IgT5ModelTypes.PAIRED,
)
model_type = variant_config["MODEL_TYPE"]


# Build Modal container image
image = modal.Image.from_registry("pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime")
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=IgT5Params.base_model_slug,
    weights_version=IgT5Params.weights_version,
    variant_config=variant_config,
    # huggingface_hub needed in the download layer for the r2_then_hf fallback
    # when the R2 cache is empty (self-population).
    extra_pip_packages=["huggingface_hub==0.26.0"],
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        "transformers==4.48.1",
        "sentencepiece==0.2.0",
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
class IgT5Model(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")
    model_type: str = model_type

    @modal.enter(snap=True)
    def setup_model(self) -> None:
        """Load model directly on GPU for GPU memory snapshot with deterministic behavior."""
        import torch
        from transformers import T5EncoderModel, T5Tokenizer

        logger.info("Loading IgT5 model directly on GPU for GPU memory snapshot...")

        # Set deterministic behavior for consistent results
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.torch = torch
        self.device = get_torch_device()
        self.model_dir = get_model_dir(model_type)
        self.model_id = model_id_mapping[IgT5ModelTypes(self.model_type)]

        logger.info(
            "Loading IgT5 model '%s' directly on %s from: %s",
            self.model_id,
            self.device,
            self.model_dir,
        )

        # Load tokenizer and model directly on GPU
        self.tokenizer = T5Tokenizer.from_pretrained(
            self.model_dir, do_lower_case=False
        )
        self.model = T5EncoderModel.from_pretrained(self.model_dir)
        self.model.eval()

        # Move model to GPU
        self.model.to(device=self.device, non_blocking=False)

        logger.info(
            "IgT5 model '%s' loaded directly on %s for GPU memory snapshot!",
            self.model_id,
            self.device,
        )

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(self, payload: IgT5EncodeRequest) -> IgT5EncodeResponse:
        """
        Performs encoding using the IgT5 model.

        Parameters:
        - payload (IgT5EncodeRequest): The request object containing sequences and parameters.

        Returns:
        - IgT5EncodeResponse: The response containing encoding results.
        """
        request_kind = payload.items[0]._kind  # Only check the first one

        if any(item._kind != self.model_type for item in payload.items):
            raise ValidationError400(
                f"Mismatch detected: expected '{self.model_type}' but got '{request_kind}' in request."
            )

        input_sequences: list[str]
        if self.model_type == IgT5ModelTypes.PAIRED:
            input_sequences = []
            for item in payload.items:
                # Guaranteed non-None for paired items by
                # IgT5EncodeRequestItem.validate_and_infer_type (the _kind check
                # above already confirms every item matches this variant).
                assert item.heavy_chain is not None and item.light_chain is not None
                input_sequences.append(
                    f"{' '.join(item.heavy_chain)} </s> {' '.join(item.light_chain)}"
                )
        else:
            input_sequences = []
            for item in payload.items:
                # Guaranteed non-None for unpaired items; see comment above.
                assert item.sequence is not None
                input_sequences.append(" ".join(item.sequence))

        # Run encoding process
        try:
            results = self._encode_forward(
                input_sequences=input_sequences, include=payload.params.include
            )
        except Exception as e:
            logger.error("Model call failed with error [%s]", e, exc_info=True)
            raise

        return results

    def _encode_forward(
        self, input_sequences: list[str], include: list[IgT5EncodeIncludeOptions]
    ) -> IgT5EncodeResponse:
        import torch

        tokens = self.tokenizer.batch_encode_plus(
            input_sequences,
            add_special_tokens=True,
            padding="longest",
            return_tensors="pt",
            return_special_tokens_mask=True,
        ).to(self.device)

        with torch.no_grad():
            output = self.model(
                input_ids=tokens["input_ids"], attention_mask=tokens["attention_mask"]
            )

        residue_embeddings = output.last_hidden_state

        residue_embeddings[tokens["special_tokens_mask"] == 1] = 0
        sequence_embeddings_sum = residue_embeddings.sum(1)

        # average embedding by dividing sum by sequence lengths
        sequence_lengths = torch.sum(tokens["special_tokens_mask"] == 0, dim=1)
        sequence_embeddings = sequence_embeddings_sum / sequence_lengths.unsqueeze(1)

        sequence_embeddings = sequence_embeddings.detach().cpu()
        residue_embeddings = residue_embeddings.detach().cpu()

        results_list = []
        for idx, _seqs in enumerate(input_sequences):
            result = {}

            if IgT5EncodeIncludeOptions.MEAN in include:
                result["embeddings"] = sequence_embeddings[idx].tolist()

            if IgT5EncodeIncludeOptions.RESIDUE in include:
                # Slice off special and pad tokens so each item's per-residue
                # matrix has its own true sequence length rather than the batch-max
                # padded length. special_tokens_mask == 0 selects the real residues
                # only (same basis as the mean-pool divisor above). residue_embeddings
                # is already on CPU here, so bring the mask to CPU to index it.
                keep = tokens["special_tokens_mask"][idx].detach().cpu() == 0
                result["residue_embeddings"] = residue_embeddings[idx][keep].tolist()

            results_list.append(IgT5EncodeResponseResult.model_validate(result))

        return IgT5EncodeResponse(results=results_list)


if __name__ == "__main__":
    """
    Usage:
        MODEL_TYPE="paired" python models/igt5/app.py

        # Force deploy to "biolm-hub-dev" or "biolm-hub" environment:
        MODEL_TYPE="paired" python models/igt5/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        IgT5Model,
        description=f"Run and optionally deploy the {IgT5Params.display_name} {model_type} Modal app.",
    )
