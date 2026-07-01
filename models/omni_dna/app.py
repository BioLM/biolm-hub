import modal

from models.commons.core.decorator import modal_endpoint
from models.commons.core.logging import get_logger
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.base import ModelMixinSnap
from models.commons.model.config import biolm_model_class
from models.commons.storage.downloads import build_hf_snapshot_path
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
)
from models.commons.util.device import get_torch_device
from models.commons.util.environment import parse_variant
from models.omni_dna.config import (
    MODEL_FAMILY,
    hf_model_name_mapping,
    hf_pin_revision_mapping,
)
from models.omni_dna.download import get_model_dir
from models.omni_dna.schema import (
    OmniDNAEncodeIncludeOptions,
    OmniDNAEncodeRequest,
    OmniDNAEncodeResponse,
    OmniDNAEncodeResponseResult,
    OmniDNALogProbRequest,
    OmniDNALogProbResponse,
    OmniDNALogProbResponseResult,
    OmniDNAModelSizes,
    OmniDNAParams,
)

logger = get_logger(__name__)

variant_config = parse_variant(
    env_var_name="MODEL_SIZE",
    allowed_values=OmniDNAModelSizes,
    default=OmniDNAModelSizes.SIZE_1B,
)
model_size = variant_config["MODEL_SIZE"]


# Build Modal container image
image = modal.Image.from_registry("pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime")
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=OmniDNAParams.base_model_slug,
    weights_version=OmniDNAParams.weights_version,
    variant_config=variant_config,
    extra_pip_packages=[
        "huggingface_hub==0.27.1",  # For downloading from HF
    ],
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        "transformers==4.47.0",
        "huggingface_hub==0.27.1",
        "safetensors==0.4.5",
        "ai2-olmo==0.6.0",
        "datasets==3.3.0",
        "tokenizers==0.21.0",
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
    secrets=[cloudflare_r2_secret],
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class OmniDNAModel(ModelMixinSnap):
    """
    The OmniDNAModel loads the chosen Omni-DNA variant from HuggingFace.
    Provides:
      - encode() => returns embedding (mean or last) for each DNA sequence
      - log_prob() => computes the total log-prob of each DNA sequence
    """

    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def setup_model(self):
        """Load model on GPU for GPU memory snapshot with deterministic behavior."""
        import torch
        from safetensors.torch import load_file
        from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

        logger.info("Loading Omni-DNA model for GPU memory snapshot...")

        # Set deterministic behavior for consistent results
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.torch = torch

        # Get device and setup for GPU inference
        self.device = get_torch_device()

        model_cache_dir = get_model_dir(model_size)

        # Build deterministic HuggingFace snapshot path
        hf_repo_id = hf_model_name_mapping[model_size]
        hf_revision = hf_pin_revision_mapping[model_size]
        snapshot_dir = build_hf_snapshot_path(model_cache_dir, hf_repo_id, hf_revision)

        logger.info(
            "Loading Omni-DNA model on %s from snapshot: %s",
            self.device,
            snapshot_dir,
        )

        # Load config and instantiate the model architecture, then load the
        # weights directly from the local .safetensors file. We avoid
        # AutoModelForCausalLM.from_pretrained here because the Omni-DNA
        # safetensors files ship without a serialized metadata header, which
        # makes transformers' from_pretrained crash reading the "format" key
        # (metadata is None -> AttributeError). load_file sidesteps that.
        config = AutoConfig.from_pretrained(snapshot_dir, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_config(
            config,
            trust_remote_code=True,
        )
        self.model.eval()

        # Load the model weights from the local .safetensors file.
        safetensors_path = snapshot_dir / "model.safetensors"
        state_dict = load_file(str(safetensors_path))
        self.model.load_state_dict(state_dict, strict=False)

        # Move model to GPU
        self.model = self.model.to(self.device, non_blocking=False)

        # Load tokenizer and ensure right-padding (required for last-token pooling and
        # log-prob shift logic — causal LMs sometimes default to left-padding)
        self.tokenizer = AutoTokenizer.from_pretrained(
            snapshot_dir,
            trust_remote_code=True,
            use_fast=True,
        )
        self.tokenizer.padding_side = "right"

        logger.info(
            "Omni-DNA model (%s) loaded on %s for GPU memory snapshot.",
            model_size,
            self.device,
        )

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(self, payload: OmniDNAEncodeRequest) -> OmniDNAEncodeResponse:
        """
        For each input sequence, computes the requested embeddings:
          - "mean": average of the non-padded token embeddings.
          - "last": embedding of the last non-padded token.
        """
        sequences = [item.sequence for item in payload.items]
        include = payload.params.include

        tokenized = self.tokenizer(
            sequences,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=OmniDNAParams.max_sequence_len,
            add_special_tokens=True,
        )
        tokenized = {k: v.to(self.device) for k, v in tokenized.items()}
        attn_mask = tokenized["attention_mask"]  # shape: [B, L]
        batch_size = attn_mask.size(0)

        with self.torch.no_grad():
            out = self.model(**tokenized, output_hidden_states=True)
        # final hidden states: shape [B, L, hidden_dim]
        hidden_states = out.hidden_states[-1]

        # Compute the "mean" embedding over non-padded tokens.
        mean_embeddings_list, last_embeddings_list = None, None

        if OmniDNAEncodeIncludeOptions.MEAN in include:
            mean_embeddings = (hidden_states * attn_mask.unsqueeze(-1)).sum(
                dim=1
            ) / attn_mask.sum(dim=1, keepdim=True)

            mean_embeddings_list = mean_embeddings.cpu().tolist()

        # Compute the "last" embedding for each sequence using the attention mask.
        if OmniDNAEncodeIncludeOptions.LAST in include:
            last_indices = attn_mask.sum(dim=1) - 1  # Last valid token index
            last_embeddings = hidden_states.gather(
                dim=1,
                index=last_indices.view(-1, 1, 1).expand(-1, 1, hidden_states.size(-1)),
            ).squeeze(1)

            last_embeddings_list = last_embeddings.cpu().tolist()

        # Build the response.
        results = []
        for i in range(batch_size):
            result_data = {}
            if mean_embeddings_list:
                result_data["mean"] = mean_embeddings_list[i]
            if last_embeddings_list:
                result_data["last"] = last_embeddings_list[i]
            results.append(OmniDNAEncodeResponseResult(**result_data))

        return OmniDNAEncodeResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def log_prob(self, payload: OmniDNALogProbRequest) -> OmniDNALogProbResponse:
        """
        Computes the total log-probability of each input DNA sequence under the model's auto-regressive
        distribution in a batched manner. We sum over *all* tokens in the BPE-tokenized sequence
        (i.e. we account for every token produced by the tokenizer).

        Steps for the batch:
          1) Collect all sequences from payload and tokenize them together (with padding, no special tokens).
          2) Move all tokenized tensors to the device.
          3) Model forward yields logits of shape [B, L, vocab_size].
          4) Compute log_softmax along the vocabulary dimension to obtain log_probs.
          5) For each sequence, for positions i in [1, L-1]:
              - The row i-1 predicts token i.
              - Gather the log probability at [i-1, token[i]].
          6) Use the attention mask (shifted by one) to zero out padded positions.
          7) Sum the gathered log probabilities per sequence.
        """
        sequences = [item.sequence for item in payload.items]

        tokenized = self.tokenizer(
            sequences,
            return_tensors="pt",
            padding=True,
            truncation=True,
            add_special_tokens=False,
        )

        tokenized = {k: v.to(self.device) for k, v in tokenized.items()}
        input_ids = tokenized["input_ids"]  # shape: [B, L]
        attention_mask = tokenized["attention_mask"]  # shape: [B, L]

        with self.torch.no_grad():
            out = self.model(**tokenized)

        logits = out.logits
        log_probs = logits.log_softmax(dim=-1)  # shape: [B, L, vocab_size]

        # For autoregressive probability:
        #    - For each sequence, predictions for token at position i come from row i-1 in log_probs.
        #    - We ignore position 0 (no preceding context).
        #    - Gather log_probs for the actual token at each position.
        tokens_to_predict = input_ids[:, 1:]  # shape: [B, L-1]
        valid_mask = attention_mask[:, 1:].float()  # shape: [B, L-1]
        predictions = log_probs[:, :-1, :]  # shape: [B, L-1, vocab_size]

        # Gather the log probability for the true token at each position.
        gathered = predictions.gather(
            dim=2, index=tokens_to_predict.unsqueeze(-1)
        ).squeeze(
            -1
        )  # shape: [B, L-1]

        # Multiply by valid_mask to zero out contributions from padded tokens, then sum per sequence.
        seq_log_probs = (gathered * valid_mask).sum(dim=1)  # shape: [B]

        results = [
            OmniDNALogProbResponseResult(log_prob=float(lp)) for lp in seq_log_probs
        ]

        return OmniDNALogProbResponse(results=results)


if __name__ == "__main__":
    """
    Usage:
        MODEL_SIZE="1b" python models/omni_dna/app.py

        # Force deploy:
        MODEL_SIZE="1b" python models/omni_dna/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        OmniDNAModel,
        description=f"Run and optionally deploy the {OmniDNAParams.display_name} {model_size} Modal app.",
    )
