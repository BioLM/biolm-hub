from typing import TYPE_CHECKING

import modal

from models.commons.core.decorator import modal_endpoint
from models.commons.core.error import ModelExecutionError
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
from models.dnabert2.config import MODEL_FAMILY
from models.dnabert2.schema import (
    DNABERT2EncodeRequest,
    DNABERT2EncodeResponse,
    DNABERT2EncodeResponseResult,
    DNABERT2LogProbRequest,
    DNABERT2LogProbResponse,
    DNABERT2LogProbResponseResult,
    DNABERT2Params,
)

if TYPE_CHECKING:
    import torch

logger = get_logger(__name__)

# Build Modal container image
# Pinned: PyTorch 2.6.0's triton crashes without GPU during download layer model validation
image = modal.Image.from_registry("pytorch/pytorch:2.3.1-cuda11.8-cudnn8-runtime")
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=DNABERT2Params.base_model_slug,
    weights_version=DNABERT2Params.weights_version,
    variant_config=None,  # this model has no variants
    extra_pip_packages=[
        "huggingface_hub==0.19.4",
        "transformers==4.29.2",
        "einops==0.7.0",
    ],
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .apt_install("build-essential")  # Install gcc and other build tools
    .uv_pip_install(
        "huggingface_hub==0.19.4",
        "transformers==4.29.2",
        "einops==0.7.0",
    )
    .run_commands("pip uninstall -y triton")
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
class DNABERT2Model(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def setup_model(self) -> None:
        """Load model directly on GPU for GPU memory snapshot with deterministic behavior."""
        import torch
        from transformers import AutoModelForMaskedLM, AutoTokenizer

        logger.info("Loading DNABERT2 model directly on GPU for GPU memory snapshot...")

        # Set deterministic behavior for consistent results
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.torch = torch

        # Get device and setup for GPU inference
        self.device = get_torch_device()

        # Get the path to the already-downloaded model
        from pathlib import Path

        from models.dnabert2.config import hf_pin_revision, hf_repo_id
        from models.dnabert2.download import get_model_dir

        # Get the model directory where files were downloaded during build
        model_dir = Path(get_model_dir())

        # Compute the deterministic HuggingFace snapshot path
        # HF always uses: {model_dir}/models--{repo}--{name}/snapshots/{revision}/
        cache_name = f"models--{hf_repo_id.replace('/', '--')}"
        self.snapshot_path = str(model_dir / cache_name / "snapshots" / hf_pin_revision)
        logger.info("Using HF snapshot path: %s", self.snapshot_path)
        logger.info(
            "Loading DNABERT2 model directly on %s from snapshot: %s",
            self.device,
            self.snapshot_path,
        )

        # Load model and move to GPU using the returned snapshot path
        self.model = AutoModelForMaskedLM.from_pretrained(
            self.snapshot_path, trust_remote_code=True
        )
        self.model = self.model.to(self.device)
        self.model.eval()

        # Load tokenizer using the returned snapshot path
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.snapshot_path,
            trust_remote_code=True,
        )

        logger.info(
            "DNABERT2 model loaded directly on %s for GPU memory snapshot!", self.device
        )

    def _mean_pooling(
        self,
        last_hidden_state: "torch.Tensor",
        attention_mask: "torch.Tensor",
    ) -> "torch.Tensor":
        """
        Standard mean pooling across non-padded tokens.
        last_hidden_state: [B, L, D]
        attention_mask: [B, L]
        returns: [B, D]
        """
        input_mask_expanded = (
            attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
        )
        sum_embeddings = self.torch.sum(last_hidden_state * input_mask_expanded, dim=1)
        sum_mask = self.torch.clamp(input_mask_expanded.sum(dim=1), min=1e-9)
        return sum_embeddings / sum_mask

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(self, payload: DNABERT2EncodeRequest) -> DNABERT2EncodeResponse:
        """
        Computes a single embedding vector (mean pooled) for each input DNA sequence.
        """
        sequences = [item.sequence for item in payload.items]

        tokenized = self.tokenizer(
            sequences,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=DNABERT2Params.max_token_len,
        ).to(self.device)

        with self.torch.no_grad():
            outputs = self.model.base_model(**tokenized)
            last_hidden_state = outputs[0]

        # Mean pooling (ignoring padded tokens)
        embeddings_tensor = self._mean_pooling(
            last_hidden_state, tokenized["attention_mask"]
        )
        embeddings_list = embeddings_tensor.cpu().tolist()

        results = [
            DNABERT2EncodeResponseResult(embedding=emb) for emb in embeddings_list
        ]
        return DNABERT2EncodeResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def log_prob(self, payload: DNABERT2LogProbRequest) -> DNABERT2LogProbResponse:
        """
        Computes a pseudo-likelihood log probability for each input DNA sequence
        using vectorized masking + MLM logits from AutoModelForMaskedLM.
        """
        results = []
        for item in payload.items:
            seq = item.sequence
            enc = self.tokenizer(
                seq,
                return_tensors="pt",
                add_special_tokens=True,
                truncation=True,
                max_length=DNABERT2Params.max_token_len,
            )
            # shape: [L]
            input_ids = enc["input_ids"][0]
            attention_mask = enc["attention_mask"][0]

            # Move both to the same device (GPU or CPU)
            input_ids = input_ids.to(self.device)
            attention_mask = attention_mask.to(self.device)

            # Identify non-special positions
            all_special_ids = set(self.tokenizer.all_special_ids)
            valid_positions = [
                i
                for i in range(len(input_ids))
                if input_ids[i].item() not in all_special_ids
            ]
            if not valid_positions:
                results.append(DNABERT2LogProbResponseResult(log_prob=0.0))
                continue

            # valid_positions_tensor must be on the same device as input_ids
            valid_positions_tensor = self.torch.tensor(
                valid_positions, device=self.device
            )
            num_valid = len(valid_positions)

            mask_id = self.tokenizer.mask_token_id
            if mask_id is None:
                raise ModelExecutionError("Tokenizer has no [MASK] token.")

            # Build a batch of masked sequences
            masked_input_ids = input_ids.unsqueeze(0).repeat(
                num_valid, 1
            )  # [num_valid, L]
            rows = self.torch.arange(num_valid, device=self.device)
            masked_input_ids[rows, valid_positions_tensor] = mask_id

            # Replicate the attention_mask
            batch_attention_mask = attention_mask.unsqueeze(0).repeat(num_valid, 1)

            # Forward pass => MLM logits
            with self.torch.no_grad():
                out = self.model(masked_input_ids, attention_mask=batch_attention_mask)
                logits = out.logits  # shape: [num_valid, L, vocab_size]

            # Gather logits for the masked positions
            selected_logits = logits[
                rows, valid_positions_tensor, :
            ]  # [num_valid, vocab_size]
            log_probs = self.torch.log_softmax(selected_logits, dim=-1)

            # original_tokens must match the same device
            original_tokens = input_ids[valid_positions_tensor]  # [num_valid]
            token_log_probs = log_probs[rows, original_tokens]  # [num_valid]

            sequence_log_prob = token_log_probs.sum().item()
            results.append(DNABERT2LogProbResponseResult(log_prob=sequence_log_prob))

        return DNABERT2LogProbResponse(results=results)


if __name__ == "__main__":
    """
    Usage:
        python models/dnabert2/app.py

        # Force deploy:
        python models/dnabert2/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        DNABERT2Model,
        description=f"Run and optionally deploy the {DNABERT2Params.display_name} Modal app.",
    )
