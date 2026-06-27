import modal

from models.commons.core.decorator import modal_endpoint
from models.commons.core.logging import get_logger
from models.commons.data.validator import (
    aa_unambiguous,
)
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.base import ModelMixinSnap
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
)
from models.commons.util.device import get_torch_device
from models.nanobert.config import MODEL_FAMILY
from models.nanobert.download import get_model_dir
from models.nanobert.schema import (
    NanoBERTEncodeIncludeOptions,
    NanoBERTEncodeRequest,
    NanoBERTEncodeResponse,
    NanoBERTEncodeResponseResult,
    NanoBERTGenerateRequest,
    NanoBERTGenerateResponse,
    NanoBERTGenerateResponseResult,
    NanoBERTLogProbRequest,
    NanoBERTLogProbResponse,
    NanoBERTLogProbResponseResult,
    NanoBERTParams,
)

logger = get_logger(__name__)

# Build Modal container image
image = modal.Image.from_registry("pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime")
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=NanoBERTParams.base_model_slug,
    params_version=NanoBERTParams.params_version,
    variant_config=None,  # this model has no variants
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        "transformers==4.48.1",
        "safetensors==0.5.3",
        "sentencepiece==0.2.0",
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
class NanoBERTModel(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def setup_model(self):
        """Load model directly on GPU for GPU memory snapshot with deterministic behavior."""
        import torch
        from transformers import AutoModelForMaskedLM, RobertaTokenizer

        logger.info("Loading NanoBERT model directly on GPU for GPU memory snapshot...")

        # Set deterministic behavior for consistent results
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.torch = torch
        self.model_dir = get_model_dir()

        # Get device and setup for GPU inference
        self.device = get_torch_device()

        logger.info("Loading NanoBERT model directly on GPU from: %s", self.model_dir)

        # Load tokenizer
        self.tokenizer = RobertaTokenizer.from_pretrained(
            self.model_dir, return_tensors="pt"
        )

        # Load model directly on GPU
        self.model = AutoModelForMaskedLM.from_pretrained(self.model_dir)
        self.model.eval()

        # Transfer model to GPU with deterministic behavior
        self.model = self.model.to(device=self.device, non_blocking=False)

        # Convert canonical AA's to vocab IDs
        self.canonical_aa_ids = sorted(
            self.tokenizer.convert_tokens_to_ids(list(aa_unambiguous))
        )

        logger.info(
            "NanoBERT model loaded directly on %s for GPU memory snapshot!", self.device
        )

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(self, payload: NanoBERTEncodeRequest) -> NanoBERTEncodeResponse:
        """
        Performs encoding using the NanoBERT model.

        Parameters:
        - payload (NanoBERTEncodeRequest): The request object containing sequences and parameters.

        Returns:
        - NanoBERTEncodeResponse: The response containing encoding results.
        """

        input_sequences = [item.sequence for item in payload.items]

        try:
            results = self._encode_forward(
                input_sequences=input_sequences, include=payload.params.include
            )
        except Exception as e:
            logger.error("Model call failed with error [%s]", e, exc_info=True)
            raise e

        return results

    def _encode_forward(
        self, input_sequences: list[str], include: list[NanoBERTEncodeIncludeOptions]
    ) -> NanoBERTEncodeResponse:

        tokens = self.tokenizer.batch_encode_plus(
            input_sequences,
            add_special_tokens=True,
            padding="longest",
            return_tensors="pt",
            return_special_tokens_mask=True,
        ).to(self.device)

        need_hidden_states = (
            NanoBERTEncodeIncludeOptions.RESIDUE in include
            or NanoBERTEncodeIncludeOptions.MEAN in include
        )

        with self.torch.no_grad():
            outputs = self.model(
                input_ids=tokens["input_ids"],
                attention_mask=tokens["attention_mask"],
                output_hidden_states=need_hidden_states,
            )

        all_logits = (
            outputs.logits if (NanoBERTEncodeIncludeOptions.LOGITS in include) else None
        )

        if need_hidden_states:
            residue_embeddings = outputs.hidden_states[
                -1
            ]  # same as outputs.last_hidden_state
            # mask out special tokens
            residue_embeddings[tokens["special_tokens_mask"] == 1] = 0
            sequence_embeddings_sum = residue_embeddings.sum(dim=1)
            sequence_lengths = (tokens["special_tokens_mask"] == 0).sum(dim=1)
            sequence_embeddings = sequence_embeddings_sum / sequence_lengths.unsqueeze(
                1
            )
        else:
            residue_embeddings = None
            sequence_embeddings = None

        results_list = []
        for idx, _seqs in enumerate(input_sequences):
            result = {}

            if NanoBERTEncodeIncludeOptions.MEAN in include:
                result["embeddings"] = sequence_embeddings[idx].cpu().tolist()

            if NanoBERTEncodeIncludeOptions.RESIDUE in include:
                result["residue_embeddings"] = residue_embeddings[idx].cpu().tolist()

            if (
                NanoBERTEncodeIncludeOptions.LOGITS in include
                and all_logits is not None
            ):
                result["logits"] = all_logits[idx].cpu().tolist()

            results_list.append(NanoBERTEncodeResponseResult.model_validate(result))

        return NanoBERTEncodeResponse(results=results_list)

    # TODO:
    # * Implement predict() method that returns logits for each residue, INCLUDING <mask> residues
    # * See ESMC's predict() method and schemas for inspiration

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def generate(self, payload: NanoBERTGenerateRequest) -> NanoBERTGenerateResponse:
        """
        Restore missing residues: `'*'` -> `<mask>`. We pick the top prediction
        at each <mask> position to fill.
        """

        # 1) Build the masked input for each item
        masked_input_texts = []
        for item in payload.items:
            masked_str = "".join(
                c if c != "*" else self.tokenizer.mask_token for c in item.sequence
            )

            masked_input_texts.append(masked_str)

        # 2) Batch-tokenize all items at once
        tokens = self.tokenizer.batch_encode_plus(
            masked_input_texts,
            add_special_tokens=True,
            padding="longest",
            return_tensors="pt",
            return_special_tokens_mask=True,
        ).to(self.device)

        # 3) Single forward pass for the entire batch
        with self.torch.no_grad():
            outputs = self.model(
                input_ids=tokens["input_ids"], attention_mask=tokens["attention_mask"]
            )
            # shape: [batch_size, seq_len, vocab_size]
            all_logits = outputs.logits

        # 4) For each item in the batch, fill in the <mask> tokens from the 20 canonical AAs
        results = []
        for idx, _item in enumerate(payload.items):
            input_ids_i = tokens["input_ids"][idx]  # shape [seq_len]
            token_list = self.tokenizer.convert_ids_to_tokens(input_ids_i)

            # Find all <mask> positions for this item
            mask_positions = (input_ids_i == self.tokenizer.mask_token_id).nonzero(
                as_tuple=True
            )[0]
            logits_i = all_logits[idx]  # shape: [seq_len, vocab_size]

            for mp in mask_positions:
                # shape [vocab_size]
                logits_for_pos = logits_i[mp]

                # Only consider the 20 canonical AAs
                restricted_logits = self.torch.full_like(logits_for_pos, float("-inf"))
                restricted_logits[self.canonical_aa_ids] = logits_for_pos[
                    self.canonical_aa_ids
                ]

                # Argmax over the canonical set
                predicted_id = restricted_logits.argmax().item()
                predicted_token = self.tokenizer.convert_ids_to_tokens([predicted_id])[
                    0
                ]

                # Replace the <mask> token with our predicted residue
                token_list[mp] = predicted_token

            # 5) Remove special tokens <s>, <pad> using special_tokens_mask
            special_mask_i = tokens["special_tokens_mask"][idx]
            filtered_tokens = [
                tok
                for (tok, is_special) in zip(token_list, special_mask_i, strict=False)
                if is_special == 0
            ]

            results.append(
                NanoBERTGenerateResponseResult(sequence="".join(filtered_tokens))
            )

        return NanoBERTGenerateResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def log_prob(self, payload: NanoBERTLogProbRequest) -> NanoBERTLogProbResponse:
        """
        Compute the log probability of each input sequence by:
          1. Converting the input to sequences.
          2. Running a single forward pass on the entire batch via RobertaForMaskedLM.
          3. Applying log_softmax over the vocab dimension.
          4. Summing the log-prob for the correct token at each position,
             EXCLUDING special tokens from the final sum.
        """
        # 1)
        input_sequences = [item.sequence for item in payload.items]

        # 2) Tokenize in a single batch
        tokens = self.tokenizer.batch_encode_plus(
            input_sequences,
            add_special_tokens=True,
            padding="longest",
            return_tensors="pt",
            return_special_tokens_mask=True,
        ).to(self.device)

        # 3) Single forward pass (batch)
        with self.torch.no_grad():
            outputs = self.model(
                input_ids=tokens["input_ids"],
                attention_mask=tokens["attention_mask"],
            )
            # logits shape: [batch_size, seq_len, vocab_size]
            logits = outputs.logits

        # 4) Compute log_softmax over vocab dimension
        #    shape: same as logits => [batch_size, seq_len, vocab_size]
        log_probs = self.torch.nn.functional.log_softmax(logits, dim=-1)

        # We'll sum the log-prob of the correct token at each position,
        # ignoring special tokens like </s>, <s>, <pad>.
        special_mask = tokens["special_tokens_mask"]  # shape [batch_size, seq_len]

        batch_size, seq_len = tokens["input_ids"].shape
        results_list = []

        for i in range(batch_size):
            # Get correct token IDs for item i
            correct_token_ids = tokens["input_ids"][i]  # shape [seq_len]
            # Gather log_probs at each (pos, correct_token_id)
            # shape for log_probs[i]: [seq_len, vocab_size]
            item_log_probs = log_probs[i, self.torch.arange(seq_len), correct_token_ids]

            # Exclude special tokens by zeroing them out or ignoring them
            # special_mask[i] == 1 => special token
            # We'll only sum positions that have special_mask == 0
            non_special_positions = special_mask[i] == 0
            sequence_log_prob = item_log_probs[non_special_positions].sum().item()

            results_list.append(
                NanoBERTLogProbResponseResult(log_prob=sequence_log_prob)
            )

        return NanoBERTLogProbResponse(results=results_list)


if __name__ == "__main__":
    """
    Usage:
        python models/nanobert/app.py

        # Force deploy to "qa" or "main" environment:
        python models/nanobert/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        NanoBERTModel,
        description=f"Run and optionally deploy the {NanoBERTParams.display_name} Modal app.",
    )
