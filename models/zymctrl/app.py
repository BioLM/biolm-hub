import math

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
from models.zymctrl.config import MODEL_FAMILY
from models.zymctrl.download import get_model_dir
from models.zymctrl.schema import (
    ZymCTRLEncodeRequest,
    ZymCTRLEncodeResponse,
    ZymCTRLEncodeResponseResult,
    ZymCTRLGenerateRequest,
    ZymCTRLGenerateResponse,
    ZymCTRLGenerateResponseGenerated,
    ZymCTRLParams,
    ZymCTRLPoolingType,
)

logger = get_logger(__name__)

# Special tokens used during training (matching paper format)
# Training format: <control tag><sep><start><ENZYME SEQUENCE><end><|endoftext|>
SEPARATOR = "<sep>"
START_TOKEN = "<start>"
END_TOKEN = "<end>"
EOS_TOKEN = "<|endoftext|>"
SPECIAL_TOKENS = [START_TOKEN, END_TOKEN, EOS_TOKEN, "<pad>", " "]


# Build Modal container image
image = modal.Image.from_registry("pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime")
# Setup download layer with model weights (R2 primary, HuggingFace fallback).
# huggingface_hub must be in the download layer so the HF fallback works at
# image-build time when R2 is cold (see commons/storage/acquisition.py).
image = setup_download_layer(
    image,
    base_model_slug=ZymCTRLParams.base_model_slug,
    weights_version=ZymCTRLParams.weights_version,
    extra_pip_packages=["huggingface_hub==0.26.0"],
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        "transformers==4.48.1",
        "safetensors==0.5.3",
        "huggingface_hub==0.26.0",
    )
)
# Add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)


# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config()
logger.info("App name: %s", app_name)
app = modal.App(app_name, image=image)


def remove_special_tokens(sequence: str) -> str:
    """Remove special tokens from generated sequence."""
    # Split by separator and take the sequence part (after EC number)
    if SEPARATOR in sequence:
        parts = sequence.split(SEPARATOR)
        if len(parts) > 1:
            sequence = parts[1]

    # Remove special tokens
    for token in SPECIAL_TOKENS:
        sequence = sequence.replace(token, "")

    return sequence.strip()


def calculate_sequence_perplexity(
    input_ids,
    model,
    device,
    sequence_start_idx: int,
    stop_token_ids: set | None = None,
) -> float:
    """Calculate perplexity for the generated amino acid sequence only.

    Following the ZymCTRL paper, perplexity is computed on the amino acid tokens,
    excluding the EC number and control tokens (<sep>, <start>). This provides
    values comparable to the paper's perplexity threshold (~1.5 for good sequences).

    Args:
        input_ids: Full tokenized sequence including EC and control tokens
        model: The language model
        device: Torch device
        sequence_start_idx: Index where the amino acid sequence starts (after <start>)
        stop_token_ids: Set of token IDs that terminate the amino-acid region
            (<end>, EOS, PAD). Positions at and after the first occurrence are
            excluded from the loss so that padding and control tokens do not
            distort the mean.

    Returns:
        Perplexity of the amino acid sequence portion only
    """
    import torch

    with torch.no_grad():
        input_ids = input_ids.to(device)

        # Get logits for the full sequence
        outputs = model(input_ids)
        logits = outputs.logits  # [1, seq_len, vocab_size]

        # Compute loss only on the amino acid portion (after <start> token)
        # For causal LM, logits[i] predicts token[i+1]
        # So to score tokens from sequence_start_idx onwards, we use logits from (sequence_start_idx-1)
        if sequence_start_idx > 0:
            shift_logits = logits[:, sequence_start_idx - 1 : -1, :]
            shift_labels = input_ids[:, sequence_start_idx:]
        else:
            shift_logits = logits[:, :-1, :]
            shift_labels = input_ids[:, 1:]

        # Mask out stop tokens (<end>, EOS, PAD) and everything after the first
        # occurrence, so only amino-acid positions contribute to the mean loss.
        if stop_token_ids:
            labels = shift_labels.clone()
            for b in range(labels.shape[0]):
                for t in range(labels.shape[1]):
                    if labels[b, t].item() in stop_token_ids:
                        labels[b, t:] = -100
                        break
            shift_labels = labels

        loss_fct = torch.nn.CrossEntropyLoss(reduction="mean", ignore_index=-100)
        loss = loss_fct(
            shift_logits.reshape(-1, shift_logits.size(-1)),
            shift_labels.reshape(-1),
        )

        return math.exp(loss.item())


@app.cls(
    image=image,
    secrets=[cloudflare_r2_secret],
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class ZymCTRLModel(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def setup_model(self):
        """Load model directly on GPU for GPU memory snapshot."""
        import torch
        from transformers import AutoTokenizer, GPT2LMHeadModel

        logger.info("Loading ZymCTRL model directly on GPU for GPU memory snapshot...")

        self.torch = torch

        # Get device and setup for GPU inference
        self.device = get_torch_device()

        # Get model directory from download layer
        self.model_dir = get_model_dir()
        logger.info("Loading ZymCTRL model from: %s", self.model_dir)

        # Load tokenizer and model from local path
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_dir)

        # Set padding token if not already set (needed for batch encoding)
        # ZymCTRL vocab has <pad> at ID 0
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = "<pad>"

        self.model = GPT2LMHeadModel.from_pretrained(self.model_dir)
        self.model.eval()
        self.model.to(device=self.device)

        # Store model config for reference
        self.num_layers = self.model.config.n_layer  # 36 layers
        self.hidden_size = self.model.config.n_embd  # 1280

        self.max_sequence_len = ZymCTRLParams.max_sequence_len

        logger.info(
            "ZymCTRL model loaded on %s! (layers=%s, hidden_size=%s)",
            self.device,
            self.num_layers,
            self.hidden_size,
        )

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def generate(self, payload: ZymCTRLGenerateRequest) -> ZymCTRLGenerateResponse:
        """
        Generate enzyme sequences conditioned on EC numbers.

        The model generates sequences in the format:
            <ec_number><sep><start><sequence><end><|endoftext|>

        Generated sequences are cleaned and perplexity is computed for quality ranking.
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

        # Parse parameters
        temperature = payload.params.temperature
        top_k = payload.params.top_k
        repetition_penalty = payload.params.repetition_penalty
        num_samples = payload.params.num_samples
        max_length = payload.params.max_length

        all_results = []

        for item in payload.items:
            ec_number = item.ec_number

            # Build prompt matching training format: <ec_number><sep><start>
            # The model will then generate: <sequence><end><|endoftext|>
            prompt = f"{ec_number}{SEPARATOR}{START_TOKEN}"
            input_ids = self.tokenizer.encode(prompt, return_tensors="pt").to(
                self.device
            )
            prompt_length = input_ids.shape[1]

            # Generate sequences
            with self.torch.no_grad():
                outputs = self.model.generate(
                    input_ids,
                    top_k=top_k,
                    temperature=temperature,
                    repetition_penalty=repetition_penalty,
                    max_length=max_length,
                    eos_token_id=self.tokenizer.eos_token_id,
                    pad_token_id=self.tokenizer.pad_token_id or 0,
                    do_sample=True,
                    num_return_sequences=num_samples,
                )

            # Token IDs that terminate the amino-acid region; computed once per item.
            stop_token_ids = {
                self.tokenizer.convert_tokens_to_ids(END_TOKEN),
                self.tokenizer.eos_token_id,
                self.tokenizer.pad_token_id or 0,
            }

            # Process each generated sequence
            results = []
            for output in outputs:
                # Calculate perplexity on amino acid tokens only (after prompt),
                # masking <end>/EOS/PAD so they don't dilute the mean loss.
                perplexity = calculate_sequence_perplexity(
                    output.unsqueeze(0),
                    self.model,
                    self.device,
                    sequence_start_idx=prompt_length,
                    stop_token_ids=stop_token_ids,
                )

                # Decode and clean sequence
                decoded = self.tokenizer.decode(output)
                sequence = remove_special_tokens(decoded)

                results.append(
                    ZymCTRLGenerateResponseGenerated(
                        sequence=sequence,
                        perplexity=perplexity,
                    )
                )

            # Sort by perplexity (lower is better)
            results.sort(key=lambda x: x.perplexity)
            all_results.append(results)

        return ZymCTRLGenerateResponse(results=all_results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(self, payload: ZymCTRLEncodeRequest) -> ZymCTRLEncodeResponse:
        """
        Extract embeddings from enzyme sequences.

        Embeddings are extracted from the model's hidden states. If an EC number
        is provided, it is prepended as context (matching the training format).
        """
        pooling = payload.params.pooling
        layer_idx = payload.params.layer

        # Normalize layer index to positive
        if layer_idx < 0:
            layer_idx = self.num_layers + layer_idx + 1

        # Prepare sequences with proper training format boundary tokens
        # Training format: <ec_number><sep><start><sequence><end>
        sequences_to_encode = []
        for item in payload.items:
            if item.ec_number:
                # Full format with EC context: <ec><sep><start><sequence><end>
                seq = f"{item.ec_number}{SEPARATOR}{START_TOKEN}{item.sequence}{END_TOKEN}"
            else:
                # Without EC: <start><sequence><end>
                seq = f"{START_TOKEN}{item.sequence}{END_TOKEN}"
            sequences_to_encode.append(seq)

        # Tokenize all sequences
        tokens = self.tokenizer(
            sequences_to_encode,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=self.max_sequence_len,
            return_attention_mask=True,
        )

        input_ids = tokens["input_ids"].to(self.device)
        attention_mask = tokens["attention_mask"].to(self.device)

        # Forward pass with hidden states
        with self.torch.no_grad():
            outputs = self.model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                output_hidden_states=True,
            )

        # Extract hidden states from specified layer
        # hidden_states is a tuple: (embedding_output, layer_1, ..., layer_n)
        hidden_states = outputs.hidden_states[layer_idx]  # [batch, seq_len, hidden]

        results = []
        for i in range(len(sequences_to_encode)):
            # Get valid token positions (non-padding)
            valid_mask = attention_mask[i].bool()
            valid_hidden = hidden_states[i][valid_mask]  # [valid_len, hidden]

            result_dict = {"sequence_index": i}

            if pooling == ZymCTRLPoolingType.MEAN:
                # Mean pooling over valid positions
                embedding = valid_hidden.mean(dim=0).cpu().tolist()
                result_dict["embedding"] = embedding

            elif pooling == ZymCTRLPoolingType.LAST:
                # Last token embedding
                embedding = valid_hidden[-1].cpu().tolist()
                result_dict["embedding"] = embedding

            elif pooling == ZymCTRLPoolingType.PER_TOKEN:
                # All per-token embeddings
                per_token = valid_hidden.cpu().tolist()
                result_dict["per_token_embeddings"] = per_token

            results.append(ZymCTRLEncodeResponseResult.model_validate(result_dict))

        return ZymCTRLEncodeResponse(results=results)


if __name__ == "__main__":
    """
    Usage:
        python models/zymctrl/app.py

        # Optionally deploy after running:
        python models/zymctrl/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        ZymCTRLModel,
        description=f"Run and optionally deploy the {ZymCTRLParams.display_name} Modal app.",
    )
