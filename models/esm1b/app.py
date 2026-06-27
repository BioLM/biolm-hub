import modal

from models.commons.core.decorator import modal_endpoint
from models.commons.core.error import ValidationError400
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
from models.esm1b.config import MODEL_FAMILY
from models.esm1b.download import get_model_dir
from models.esm1b.schema import (
    ESM1bEncodeRequest,
    ESM1bEncodeResponse,
    ESM1bEncodeResponseResult,
    ESM1bLogProbRequest,
    ESM1bLogProbResponse,
    ESM1bLogProbResponseResult,
    ESM1bParams,
    ESM1bPredictRequest,
    ESM1bPredictResponse,
    ESM1bPredictResponseResult,
)

logger = get_logger(__name__)

# Build Modal container image
image = modal.Image.from_registry("pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime")
# Setup download layer with model weights
# Note: huggingface_hub needed in download layer for HF fallback when R2 cache is empty
image = setup_download_layer(
    image,
    base_model_slug=ESM1bParams.base_model_slug,
    params_version=ESM1bParams.params_version,
    variant_config={},  # No variants for ESM-1b
    extra_pip_packages=["huggingface_hub==0.26.0"],
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        "transformers==4.36.2",
        "safetensors==0.5.3",
        "huggingface_hub==0.26.0",  # Pin to match download layer
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
class ESM1bModel(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def setup_model(self):
        """Load model directly on GPU for GPU memory snapshot with deterministic behavior."""
        import torch
        from transformers import EsmForMaskedLM, EsmTokenizer

        logger.info("Loading ESM-1b model directly on GPU for GPU memory snapshot...")

        # Set deterministic behavior for consistent results
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.torch = torch
        self.device = get_torch_device()
        self.model_dir = get_model_dir()

        logger.info("Loading ESM-1b model from: %s", self.model_dir)

        # Load tokenizer
        self.tokenizer = EsmTokenizer.from_pretrained(self.model_dir)

        # Load model with language modeling head for logits
        self.model = EsmForMaskedLM.from_pretrained(
            self.model_dir, output_attentions=True, output_hidden_states=True
        )
        self.model.to(self.device)
        self.model.eval()

        # Model attributes
        self.num_layers = self.model.config.num_hidden_layers
        self.max_sequence_len = ESM1bParams.max_sequence_len

        # Tokens per batch for batching
        self.toks_per_batch = 4096

        # Get amino acid vocabulary tokens (standard 20 amino acids)
        # ESM tokenizer vocab: special tokens + standard AAs
        self.vocab_tokens = [
            tok
            for tok in self.tokenizer.get_vocab().keys()
            if len(tok) == 1 and tok.isupper()
        ]

        logger.info(
            "ESM-1b model loaded directly on %s for GPU memory snapshot!", self.device
        )

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(self, payload: ESM1bEncodeRequest) -> ESM1bEncodeResponse:
        """
        Performs encoding using the ESM-1b model.

        Parameters:
        - payload (ESM1bEncodeRequest): The request object containing sequences and parameters.

        Returns:
        - ESM1bEncodeResponse: The response containing encoding results.
        """
        sequences = [item.sequence for item in payload.items]
        repr_layers = payload.params.repr_layers
        include = [option.value for option in payload.params.include]

        try:
            results = self._encode_forward_pass(
                sequences=sequences,
                repr_layers=repr_layers,
                include=include,
            )
        except Exception as e:
            logger.error("Model call failed with error [%s]", e, exc_info=True)
            raise e

        return ESM1bEncodeResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict(self, payload: ESM1bPredictRequest) -> ESM1bPredictResponse:
        """
        Performs prediction using the ESM-1b model for masked sequences.

        Parameters:
        - payload (ESM1bPredictRequest): The request object containing sequences with masks.

        Returns:
        - ESM1bPredictResponse: The response containing prediction results.
        """
        sequences = [item.sequence for item in payload.items]

        try:
            results = self._predict_forward_pass(sequences=sequences)
        except Exception as e:
            logger.error("Model call failed with error [%s]", e, exc_info=True)
            raise e

        return ESM1bPredictResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def log_prob(self, payload: ESM1bLogProbRequest) -> ESM1bLogProbResponse:
        """
        Computes the total log-probability of an unmasked sequence under ESM-1b.

        This method performs the following steps:
          1) Call _encode_forward_pass() with include=["logits"] to get per-token logits.
          2) For each sequence, compute log-softmax over the logits at each token position.
          3) For each position corresponding to a canonical residue, add the log-probability.
          4) Return a list of total log-probabilities (one per sequence).
        """
        sequences = [item.sequence for item in payload.items]

        # Get logits from encode forward pass
        encode_results = self._encode_forward_pass(
            sequences=sequences,
            repr_layers=[-1],
            include=["logits"],
        )

        canonical_map = {aa: idx for idx, aa in enumerate(self.vocab_tokens)}

        log_prob_sums = []
        for seq, result in zip(sequences, encode_results, strict=False):
            # result.logits is a list-of-lists: shape [L, vocab_size]
            logits_tensor = self.torch.tensor(result.logits)
            # Compute log-softmax along the vocabulary dimension
            log_probs = self.torch.nn.functional.log_softmax(logits_tensor, dim=-1)

            total_log_prob = 0.0
            for pos in range(logits_tensor.shape[0]):
                aa = seq[pos]
                if aa not in canonical_map:
                    continue
                idx = canonical_map[aa]
                total_log_prob += float(log_probs[pos, idx])
            log_prob_sums.append(total_log_prob)

        results = [ESM1bLogProbResponseResult(log_prob=lp) for lp in log_prob_sums]
        return ESM1bLogProbResponse(results=results)

    def _encode_forward_pass(  # noqa: C901
        self,
        sequences: list[str],
        repr_layers: list[int],
        include: list[str],
    ) -> list[ESM1bEncodeResponseResult]:
        """
        Perform inference on a list of sequences using the ESM-1b model.

        Parameters:
        - sequences (List[str]): A list of amino acid sequences to process.
        - repr_layers (List[int]): List of layer indices to extract representations from.
        - include (List[str]): List of output types to include.
        """
        # Validate and normalize layer indices
        if not all(-(self.num_layers + 1) <= i <= self.num_layers for i in repr_layers):
            raise ValidationError400(
                f"Requested representation layers are out of bounds. Ensure the "
                f"layer indices are between -{self.num_layers + 1} and {self.num_layers}."
            )
        # Convert negative indices to positive
        repr_layers_pos = [
            (i + self.num_layers + 1) % (self.num_layers + 1) for i in repr_layers
        ]

        # Check what outputs we need
        need_attentions = "attentions" in include
        need_logits = "logits" in include

        # Tokenize sequences
        encoded = self.tokenizer(
            sequences,
            padding=True,
            truncation=True,
            max_length=self.max_sequence_len + 2,  # +2 for BOS/EOS
            return_tensors="pt",
        )

        input_ids = encoded["input_ids"].to(self.device)
        attention_mask = encoded["attention_mask"].to(self.device)

        with self.torch.no_grad():
            outputs = self.model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                output_hidden_states=True,
                output_attentions=need_attentions,
            )

        # Extract hidden states for requested layers
        # hidden_states is tuple of (num_layers + 1) tensors, each (batch, seq_len, hidden_dim)
        hidden_states = outputs.hidden_states

        # Get logits if needed (shape: batch, seq_len, vocab_size)
        logits = outputs.logits.cpu() if need_logits else None

        # Get attentions if needed
        attentions = None
        if need_attentions:
            # attentions is tuple of num_layers tensors, each (batch, num_heads, seq_len, seq_len)
            attentions = outputs.attentions

        results = []
        for i, seq in enumerate(sequences):
            result_dict = {"sequence_index": i}

            # Get actual sequence length (excluding padding)
            seq_len = len(seq)

            # Extract embeddings for requested layers
            if "per_token" in include:
                result_dict["per_token_embeddings"] = [
                    {
                        "layer": layer_idx,
                        "embeddings": hidden_states[layer_idx][i, 1 : seq_len + 1]
                        .clone()
                        .cpu()
                        .tolist(),
                    }
                    for layer_idx in repr_layers_pos
                ]

            if "mean" in include:
                result_dict["embeddings"] = [
                    {
                        "layer": layer_idx,
                        "embedding": hidden_states[layer_idx][i, 1 : seq_len + 1]
                        .mean(dim=0)
                        .clone()
                        .cpu()
                        .tolist(),
                    }
                    for layer_idx in repr_layers_pos
                ]

            if "bos" in include:
                result_dict["bos_embeddings"] = [
                    {
                        "layer": layer_idx,
                        "embedding": hidden_states[layer_idx][i, 0]
                        .clone()
                        .cpu()
                        .tolist(),
                    }
                    for layer_idx in repr_layers_pos
                ]

            if need_attentions and attentions is not None:
                # Stack attention from all layers: (layers, heads, seq, seq)
                attn_stack = self.torch.stack([attn[i] for attn in attentions], dim=0)
                # Average attention across layers and heads, return for sequence positions
                avg_attentions = (
                    attn_stack.mean(dim=(0, 1))[1 : seq_len + 1, 1 : seq_len + 1]
                    .clone()
                    .cpu()
                    .tolist()
                )
                result_dict["attentions"] = avg_attentions

            if need_logits and logits is not None:
                # Get logits for sequence positions (excluding BOS/EOS)
                # Filter to only canonical amino acid vocab
                vocab_indices = [
                    self.tokenizer.convert_tokens_to_ids(tok)
                    for tok in self.vocab_tokens
                ]
                seq_logits = (
                    logits[i, 1 : seq_len + 1, vocab_indices].clone().cpu().tolist()
                )
                result_dict["logits"] = seq_logits
                result_dict["vocab_tokens"] = self.vocab_tokens

            result = ESM1bEncodeResponseResult.model_validate(result_dict)
            results.append(result)

        return results

    def _predict_forward_pass(
        self,
        sequences: list[str],
    ) -> list[ESM1bPredictResponseResult]:
        """
        Perform prediction on sequences with <mask> tokens.

        Parameters:
        - sequences (List[str]): List of amino acid sequences containing <mask> tokens.

        Returns:
        - List[ESM1bPredictResponseResult]: The list of prediction results.
        """
        # Tokenize sequences
        encoded = self.tokenizer(
            sequences,
            padding=True,
            truncation=True,
            max_length=self.max_sequence_len + 2,
            return_tensors="pt",
        )

        input_ids = encoded["input_ids"].to(self.device)
        attention_mask = encoded["attention_mask"].to(self.device)

        with self.torch.no_grad():
            outputs = self.model(
                input_ids=input_ids,
                attention_mask=attention_mask,
            )

        # Get logits (shape: batch, seq_len, vocab_size)
        logits = outputs.logits.cpu()

        # Get vocab indices for canonical amino acids
        vocab_indices = [
            self.tokenizer.convert_tokens_to_ids(tok) for tok in self.vocab_tokens
        ]

        results = []
        for i, _seq in enumerate(sequences):
            # Get actual tokenized length (excluding padding, BOS, EOS)
            actual_tokens = (input_ids[i] != self.tokenizer.pad_token_id).sum().item()
            seq_len = actual_tokens - 2  # Remove BOS and EOS

            # Get logits for sequence positions (excluding BOS/EOS)
            # Filter to canonical amino acids
            seq_logits = logits[i, 1 : seq_len + 1, vocab_indices].clone().tolist()

            # Get sequence tokens from tokenizer for accurate representation
            tokens = self.tokenizer.convert_ids_to_tokens(input_ids[i, 1 : seq_len + 1])
            sequence_tokens = tokens

            result = ESM1bPredictResponseResult(
                logits=seq_logits,
                sequence_tokens=sequence_tokens,
                vocab_tokens=self.vocab_tokens,
            )
            results.append(result)

        return results


if __name__ == "__main__":
    """
    Usage:
        python models/esm1b/app.py

        # Force deploy to "qa" or "main" environment:
        python models/esm1b/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        ESM1bModel,
        description=f"Run and optionally deploy the {ESM1bParams.display_name} Modal app.",
    )
