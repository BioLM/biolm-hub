from typing import Union

import modal

from models.commons.core.decorator import modal_endpoint
from models.commons.core.error import ValidationError400
from models.commons.core.logging import get_logger
from models.commons.data.validator import (
    aa_extended,
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
from models.commons.util.environment import parse_variant
from models.igbert.config import MODEL_FAMILY
from models.igbert.download import get_model_dir, get_model_id
from models.igbert.schema import (
    IgBertEncodeIncludeOptions,
    IgBertEncodeRequest,
    IgBertEncodeResponse,
    IgBertEncodeResponseResult,
    IgBertGenerateRequest,
    IgBertGenerateResponse,
    IgBertGenerateResponseResult,
    IgBertLogProbRequest,
    IgBertLogProbResponse,
    IgBertLogProbResponseResult,
    IgBertModelTypes,
    IgBertParams,
)

logger = get_logger(__name__)

variant_config = parse_variant(
    env_var_name="MODEL_TYPE",
    allowed_values=IgBertModelTypes,
    default=IgBertModelTypes.PAIRED,
)
model_type = variant_config["MODEL_TYPE"]


# Build Modal container image
image = modal.Image.from_registry("pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime")
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=IgBertParams.base_model_slug,
    weights_version=IgBertParams.weights_version,
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
    secrets=[cloudflare_r2_secret],
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class IgBertModel(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")
    model_type: str = model_type

    @modal.enter(snap=True)
    def setup_model(self):
        """Load model directly on GPU for GPU memory snapshot with deterministic behavior."""
        import torch
        from transformers import BertForMaskedLM, BertTokenizer

        logger.info("Loading IgBERT model directly on GPU for GPU memory snapshot...")

        # Set deterministic behavior for consistent results
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.torch = torch
        self.device = get_torch_device()
        self.model_dir = get_model_dir(self.model_type)
        self.model_id = get_model_id(self.model_type)

        logger.info(
            "Loading IgBert model '%s' directly on %s from: %s",
            self.model_id,
            self.device,
            self.model_dir,
        )

        # Load tokenizer and model directly on GPU
        self.tokenizer = BertTokenizer.from_pretrained(
            self.model_dir, do_lower_case=False
        )
        self.model = BertForMaskedLM.from_pretrained(self.model_dir)
        self.model.eval()

        # Move model to GPU
        self.model.to(device=self.device, non_blocking=False)

        self.canonical_aa_ids = sorted(
            self.tokenizer.convert_tokens_to_ids(list(aa_extended))
        )

        logger.info(
            "IgBert model '%s' loaded directly on %s for GPU memory snapshot!",
            self.model_id,
            self.device,
        )

    def _pre_process_payload(
        self, payload: Union[IgBertEncodeRequest, IgBertLogProbRequest]
    ) -> list[str]:
        if any(item._kind != self.model_type for item in payload.items):
            request_kind = payload.items[0]._kind
            raise ValidationError400(
                f"Mismatch detected: expected '{self.model_type}' but got '{request_kind}' in request."
            )

        if self.model_type == IgBertModelTypes.PAIRED:
            # item.heavy_chain & item.light_chain are guaranteed non-None by schema
            input_sequences = [
                " ".join(item.heavy_chain) + " [SEP] " + " ".join(item.light_chain)
                for item in payload.items
            ]
        else:
            # item.sequence is guaranteed non-None by schema
            input_sequences = [" ".join(item.sequence) for item in payload.items]

        return input_sequences

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(self, payload: IgBertEncodeRequest) -> IgBertEncodeResponse:
        """
        Performs encoding using the IgBert model.

        Parameters:
        - payload (IgBertEncodeRequest): The request object containing sequences and parameters.

        Returns:
        - IgBertEncodeResponse: The response containing encoding results.
        """

        input_sequences = self._pre_process_payload(payload)

        try:
            results = self._encode_forward(
                input_sequences=input_sequences, include=payload.params.include
            )
        except Exception as e:
            logger.error("Model call failed with error [%s]", e, exc_info=True)
            raise

        return results

    def _encode_forward(
        self, input_sequences: list[str], include: list[IgBertEncodeIncludeOptions]
    ) -> IgBertEncodeResponse:
        tokens = self.tokenizer.batch_encode_plus(
            input_sequences,
            add_special_tokens=True,
            padding="longest",
            return_tensors="pt",
            return_special_tokens_mask=True,
        ).to(self.device)

        need_hidden_states = (
            IgBertEncodeIncludeOptions.RESIDUE in include
            or IgBertEncodeIncludeOptions.MEAN in include
        )

        with self.torch.no_grad():
            outputs = self.model(
                input_ids=tokens["input_ids"],
                attention_mask=tokens["attention_mask"],
                output_hidden_states=need_hidden_states,
            )

        all_logits = (
            outputs.logits if (IgBertEncodeIncludeOptions.LOGITS in include) else None
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

            if IgBertEncodeIncludeOptions.MEAN in include:
                result["embeddings"] = sequence_embeddings[idx].cpu().tolist()

            if IgBertEncodeIncludeOptions.RESIDUE in include:
                result["residue_embeddings"] = residue_embeddings[idx].cpu().tolist()

            if IgBertEncodeIncludeOptions.LOGITS in include and all_logits is not None:
                result["logits"] = all_logits[idx].cpu().tolist()

            results_list.append(IgBertEncodeResponseResult.model_validate(result))

        return IgBertEncodeResponse(results=results_list)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def generate(self, payload: IgBertGenerateRequest) -> IgBertGenerateResponse:
        """
        Restore missing residues: `'*'` -> `[MASK]`. We pick the top prediction
        at each [MASK] position to fill.
        """

        if any(item._kind != self.model_type for item in payload.items):
            request_kind = payload.items[0]._kind
            raise ValidationError400(
                f"Mismatch detected: expected '{self.model_type}' but got '{request_kind}' in request."
            )

        # 1) Build the masked input for each item
        masked_input_texts = []
        for item in payload.items:
            if item._kind == IgBertModelTypes.PAIRED:
                heavy_masked_str = " ".join(
                    c if c != "*" else self.tokenizer.mask_token
                    for c in item.heavy_chain
                )
                light_masked_str = " ".join(
                    c if c != "*" else self.tokenizer.mask_token
                    for c in item.light_chain
                )
                input_text = heavy_masked_str + " [SEP] " + light_masked_str

            else:  # Unpaired
                seq_masked_str = " ".join(
                    c if c != "*" else self.tokenizer.mask_token for c in item.sequence
                )
                input_text = seq_masked_str

            masked_input_texts.append(input_text)

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
            outputs = self.model(tokens["input_ids"])
            # shape: [batch_size, seq_len, vocab_size]
            all_logits = outputs.logits

        # 4) For each item in the batch, fill in the [MASK] tokens from the 20 canonical AAs
        results = []
        for idx, item in enumerate(payload.items):
            input_ids_i = tokens["input_ids"][idx]  # shape [seq_len]
            token_list = self.tokenizer.convert_ids_to_tokens(input_ids_i)

            # Find all [MASK] positions for this item
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

                # Replace the [MASK] token with our predicted residue
                token_list[mp] = predicted_token

            # 5) Remove special tokens [CLS], [SEP], [PAD] using special_tokens_mask
            special_mask_i = tokens["special_tokens_mask"][idx]
            filtered_tokens = [
                tok
                for (tok, is_special) in zip(token_list, special_mask_i, strict=False)
                if is_special == 0
            ]
            # ALSO remove the literal "[SEP]" tokens that came from our input text:
            filtered_tokens = [t for t in filtered_tokens if t != "[SEP]"]

            # 6) Re-split heavy & light by their original length
            if item._kind == IgBertModelTypes.PAIRED:
                num_heavy = len(item.heavy_chain)
                num_light = len(item.light_chain)
                heavy_tokens = filtered_tokens[:num_heavy]
                light_tokens = filtered_tokens[num_heavy : num_heavy + num_light]

                filled_heavy = "".join(heavy_tokens)
                filled_light = "".join(light_tokens)
                results.append(
                    IgBertGenerateResponseResult(
                        heavy_chain=filled_heavy, light_chain=filled_light
                    )
                )
            else:
                filled_seq = "".join(filtered_tokens)
                results.append(IgBertGenerateResponseResult(sequence=filled_seq))

        return IgBertGenerateResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def log_prob(self, payload: IgBertLogProbRequest) -> IgBertLogProbResponse:
        """
        Compute the log probability of each input sequence by:
          1. Converting the input to either "heavy + [SEP] + light" (paired) or "sequence" (unpaired).
          2. Running a single forward pass on the entire batch via BertForMaskedLM.
          3. Applying log_softmax over the vocab dimension.
          4. Summing the log-prob for the correct token at each position,
             EXCLUDING special tokens from the final sum.
        """
        input_sequences = self._pre_process_payload(payload)

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
        # ignoring special tokens like [CLS], [SEP], [PAD].
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

            results_list.append(IgBertLogProbResponseResult(log_prob=sequence_log_prob))

        return IgBertLogProbResponse(results=results_list)


if __name__ == "__main__":
    """
    Usage:
        MODEL_TYPE="paired" python models/igbert/app.py

        # Force deploy to the target Modal environment:
        MODEL_TYPE="paired" python models/igbert/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        IgBertModel,
        description=f"Run and optionally deploy the {IgBertParams.display_name} {model_type} Modal app.",
    )
