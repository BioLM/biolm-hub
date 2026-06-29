import importlib
import os
from typing import TYPE_CHECKING

import modal

from models.commons.core.decorator import modal_endpoint
from models.commons.core.error import ValidationError400
from models.commons.core.logging import get_logger
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.base import ModelMixin
from models.commons.model.config import biolm_model_class
from models.commons.storage.downloads import build_hf_snapshot_path
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
)
from models.commons.util.device import get_torch_device
from models.commons.util.environment import parse_variant
from models.e1.config import E1_HF_REPO_MAP, E1_HF_REVISION_MAP, MODEL_FAMILY
from models.e1.download import get_model_dir, get_model_id
from models.e1.schema import (
    E1EncodeIncludeOptions,
    E1EncodeRequest,
    E1EncodeResponse,
    E1EncodeResponseResult,
    E1ModelSizes,
    E1Params,
    E1PredictLogProbRequest,
    E1PredictLogProbResponse,
    E1PredictLogProbResponseResult,
    E1PredictRequest,
    E1PredictResponse,
    E1PredictResponseResult,
    LayerEmbedding,
    LayerPerTokenEmbeddings,
)

logger = get_logger(__name__)

if TYPE_CHECKING:
    from transformers.modeling_outputs import MaskedLMOutput


variant_config = parse_variant(
    env_var_name="MODEL_SIZE",
    allowed_values=E1ModelSizes,
    default=E1ModelSizes.SIZE_150M,
)
model_size = variant_config["MODEL_SIZE"]


# Build Modal container image
image = modal.Image.from_registry("pytorch/pytorch:2.6.0-cuda11.8-cudnn9-runtime")
# Setup download layer with model weights
# Note: huggingface_hub needed in download layer for HF fallback when R2 cache is empty
image = setup_download_layer(
    image,
    base_model_slug=E1Params.base_model_slug,
    params_version=E1Params.params_version,
    variant_config=variant_config,
    extra_pip_packages=["huggingface_hub==0.26.0"],  # Pin for download layer
)
# Add dependencies and packages
image = (
    image.apt_install(
        "procps", "build-essential"
    )  # procps for uptime, build-essential for torch.compile
    .uv_pip_install(common_requirements)
    .uv_pip_install("transformers==4.47.1")
    .uv_pip_install("einops==0.8.0")  # Required by E1 model
    .uv_pip_install("networkx==3.4.2")  # Required by E1 for attention pooling
    .uv_pip_install("tokenizers==0.21.0")  # Required for E1 tokenizer
    .uv_pip_install("huggingface_hub==0.26.0")  # Pin to match download layer
)
# Finally, add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)


# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config(**variant_config)
logger.info("App name: %s", app_name)
app = modal.App(app_name, image=image)


# NOTE: We do not use Modal GPU memory snapshots for this model (disabled entirely).
# Reason: GPU snapshots cause segmentation faults (SIGSEGV) when restoring.


@app.cls(
    image=image,
    secrets=[cloudflare_r2_secret],
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class E1Model(ModelMixin):
    app_username: str = modal.parameter(default="default_user")
    model_size: E1ModelSizes = model_size
    model_id: str = get_model_id(model_size)

    """
    E1Model class offers these methods:
     - encode() => computes embeddings (with optional context sequences)
     - predict() => per-token logits for masked tokens
     - log_prob() => total log-prob of an unmasked sequence
    """

    @modal.enter()
    def setup_model(self):
        """
        Loads the E1 model from local weights into memory.
        """

        import torch
        import torch._dynamo

        # Disable torch.compile/dynamo entirely - flex_attention compilation fails on
        # PyTorch 2.6.0 with sympy Relational errors. Disabling is cleaner than suppress_errors
        # as it skips compilation attempts entirely rather than catching failures.
        # This makes torch.compile() a no-op, using eager mode from the start.
        torch._dynamo.config.disable = True

        # Set deterministic behavior for consistent results across CPU/GPU loading
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.torch = torch

        self.model_dir = get_model_dir(self.model_size)
        self.device = get_torch_device()

        # Set the Huggingface Hub cache dir
        os.environ["HF_HUB_CACHE"] = str(self.model_dir)
        logger.info("HF_HUB_CACHE is set to: %s", os.environ["HF_HUB_CACHE"])

        # Force reload of the huggingface_hub.constants module, so that HF_HUB_CACHE is properly set
        import huggingface_hub.constants

        importlib.reload(huggingface_hub.constants)

        import json
        from pathlib import Path

        from transformers import AutoModelForMaskedLM

        # Get HF repo and revision from config (single source of truth)
        hf_model_name = E1_HF_REPO_MAP[self.model_size]
        hf_revision = E1_HF_REVISION_MAP[self.model_size]

        # Build local snapshot path (model already downloaded by download layer)
        snapshot_path = build_hf_snapshot_path(
            self.model_dir, hf_model_name, hf_revision
        )

        # Patch config.json to add auto_map if missing (required for trust_remote_code)
        # The HF repo's config.json is missing auto_map, which prevents transformers
        # from finding the custom E1Config/E1ForMaskedLM classes in modeling_e1.py
        config_path = Path(snapshot_path) / "config.json"
        with open(config_path) as f:
            config_data = json.load(f)
        if "auto_map" not in config_data:
            config_data["auto_map"] = {
                "AutoConfig": "modeling_e1.E1Config",
                "AutoModel": "modeling_e1.E1Model",
                "AutoModelForMaskedLM": "modeling_e1.E1ForMaskedLM",
            }
            with open(config_path, "w") as f:
                json.dump(config_data, f, indent=2)
            logger.info("Patched config.json with auto_map for trust_remote_code")

        # Select dtype based on GPU: T4 (150m) uses float16 (native), L4 (300m/600m) uses bfloat16
        if self.device.type == "cuda":
            # T4 (Turing) lacks native bfloat16; L4 (Ada Lovelace) has native bfloat16
            use_bfloat16 = self.model_size != E1ModelSizes.SIZE_150M
            model_dtype = torch.bfloat16 if use_bfloat16 else torch.float16
        else:
            model_dtype = torch.float32

        logger.info(
            "Loading E1 model from snapshot: %s on %s with %s...",
            snapshot_path,
            self.device,
            model_dtype,
        )
        self.model = AutoModelForMaskedLM.from_pretrained(
            snapshot_path,
            trust_remote_code=True,
            local_files_only=True,
            torch_dtype=model_dtype,
        )
        self.model = self.model.to(self.device)
        self.model.eval()

        logger.info(
            "E1 model '%s' loaded successfully on %s", self.model_id, self.device
        )

        # Import aa_unambiguous after other imports are done
        from models.commons.data.validator import aa_unambiguous

        # Build a map from each canonical AA to its index in the E1 tokenizer
        # so we can slice out just those 20 columns from the logits.
        self.vocab_tokens = list(aa_unambiguous)  # ["A","C","D","E","F", ... ,"Y"]
        self.canonical_idxs = []
        tokenizer = self.model.prep_tokens.tokenizer
        for aa in self.vocab_tokens:
            # E1 tokenizer always contains the 20 canonical AAs; fallback to 0
            # is defensive but should never trigger in practice
            idx = tokenizer.token_to_id(aa)
            self.canonical_idxs.append(idx if idx is not None else 0)

    def _build_multi_sequence_input(
        self, sequence: str, context_sequences: list[str] | None
    ) -> str:
        """
        Build E1's multi-sequence input format.

        E1 expects comma-separated sequences where:
        - Earlier sequences are context/homologs
        - The last sequence is the query to score/embed

        Args:
            sequence: The query sequence
            context_sequences: Optional list of context sequences (homologs)

        Returns:
            Formatted string for E1 input (e.g., "HOMOLOG1,HOMOLOG2,QUERY")
        """
        if context_sequences:
            # Prepend context sequences, query is last
            all_sequences = context_sequences + [sequence]
            return ",".join(all_sequences)
        else:
            return sequence

    def _get_query_token_positions(
        self, sequence: str, context_sequences: list[str] | None
    ) -> tuple[int, int]:
        """
        Calculate the token positions for the query sequence in E1's output.

        E1's tokenization format for each sequence is: <bos> 1 SEQUENCE 2 <eos>
        For multi-sequence input, these are concatenated.

        Args:
            sequence: The query sequence
            context_sequences: Optional list of context sequences

        Returns:
            Tuple of (start_position, end_position) for the query's amino acid tokens
        """
        if context_sequences:
            # Each context sequence adds: <bos>(1) + 1(1) + SEQ(len) + 2(1) + <eos>(1) = len + 4
            context_token_count = sum(len(s) + 4 for s in context_sequences)
            # Query starts after context tokens + its own <bos> and "1"
            query_start = context_token_count + 2  # Skip <bos> and "1"
        else:
            # Single sequence: positions are 2 to 2+len (skip <bos> and "1")
            query_start = 2

        query_end = query_start + len(sequence)
        return query_start, query_end

    def _forward_pass(self, input_strings: list[str]) -> "MaskedLMOutput":
        """
        Single batched forward pass over the input list of formatted sequence strings.
        Returns a MaskedLMOutput object with .logits, .hidden_states, etc.
        """
        batch = self.model.prep_tokens.get_batch_kwargs(
            input_strings, device=self.device
        )
        with self.torch.no_grad():
            batch_out = self.model(**batch, output_hidden_states=True)
        return batch_out

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(self, payload: E1EncodeRequest) -> E1EncodeResponse:  # noqa: C901
        # FIXME(noqa: C901): Refactor to reduce complexity below the linter's threshold.

        """
        Encode sequences with E1, possibly across multiple layers.

        E1 supports retrieval-augmented encoding where context sequences (homologs)
        can be provided to improve embeddings.

        We return the following fields in E1EncodeResponseResult,
        depending on what is in payload.params.include:
          - embeddings: [{layer: <int>, embedding: [d_embed]}, ...]
          - per_token_embeddings: [{layer: <int>, embedding: [[d_embed]]}, ...]
          - logits: [[20], ...], restricted to canonical AAs only.
          - vocab_tokens: ["A", "C", ...]
          - context_sequence_count: Number of context sequences used

        User may specify multiple repr_layers (e.g. [-1, 0, 5])
        and negative indices are converted accordingly.
        """
        include_options = payload.params.include
        requested_layers = payload.params.repr_layers

        # Build input strings with multi-sequence format
        input_strings = []
        query_positions = []
        for item in payload.items:
            input_str = self._build_multi_sequence_input(
                item.sequence, item.context_sequences
            )
            input_strings.append(input_str)
            query_positions.append(
                self._get_query_token_positions(item.sequence, item.context_sequences)
            )

        batch_out = self._forward_pass(input_strings)
        # batch_out.logits: shape [B, L_total, vocab_size]
        # batch_out.hidden_states: tuple of tensors (one per layer + embedding layer)
        # Each tensor has shape [B, L_total, d_embed]. Layer counts:
        # - E1-150M/300M: 21 outputs (20 transformer layers + embedding)
        # - E1-600M: 31 outputs (30 transformer layers + embedding)

        results = []
        for i, item in enumerate(payload.items):
            # Prepare the response object
            encode_res = E1EncodeResponseResult()

            # Get query positions for this item
            query_start, query_end = query_positions[i]

            if (
                E1EncodeIncludeOptions.MEAN in include_options
                or E1EncodeIncludeOptions.PER_TOKEN in include_options
            ) and batch_out.hidden_states is not None:
                n_layers = len(batch_out.hidden_states)

                # Validate that all requested layers are in range before processing
                if not all(
                    -n_layers <= lyr <= n_layers - 1 for lyr in requested_layers
                ):
                    raise ValidationError400(
                        f"Requested representation layers are out of bounds. Ensure the "
                        f"layer indices are between -{n_layers} and {n_layers - 1}."
                    )

                # Convert user repr_layers to positive indices
                layers_to_use = []
                for lyr in requested_layers:
                    pos_lyr = (lyr + n_layers) if lyr < 0 else lyr
                    layers_to_use.append(pos_lyr)

                # embeddings
                if E1EncodeIncludeOptions.MEAN in include_options:
                    embedding_list = []
                    for lyr_idx in layers_to_use:
                        layer_emb = batch_out.hidden_states[lyr_idx][
                            i
                        ]  # [L_total, d_embed]
                        # Extract only query positions
                        query_emb = layer_emb[
                            query_start:query_end
                        ]  # [L_query, d_embed]
                        mean_vec = query_emb.mean(dim=0).cpu().tolist()
                        embedding_list.append(
                            LayerEmbedding(layer=lyr_idx, embedding=mean_vec)
                        )
                    encode_res.embeddings = embedding_list

                # per_token_embeddings
                if E1EncodeIncludeOptions.PER_TOKEN in include_options:
                    per_token_list = []
                    for lyr_idx in layers_to_use:
                        layer_emb = batch_out.hidden_states[lyr_idx][
                            i
                        ]  # [L_total, d_embed]
                        # Extract only query positions
                        query_emb = layer_emb[
                            query_start:query_end
                        ]  # [L_query, d_embed]
                        emb_2d = query_emb.cpu().tolist()
                        per_token_list.append(
                            LayerPerTokenEmbeddings(layer=lyr_idx, embeddings=emb_2d)
                        )
                    encode_res.per_token_embeddings = per_token_list

            if (
                E1EncodeIncludeOptions.LOGITS in include_options
                and batch_out.logits is not None
            ):
                # seq_logits_full: shape [L_total, vocab_size]
                seq_logits_full = batch_out.logits[i]
                # Extract only query positions and canonical AAs
                seq_logits_canonical = seq_logits_full[
                    query_start:query_end, self.canonical_idxs
                ]
                encode_res.logits = seq_logits_canonical.cpu().tolist()
                encode_res.vocab_tokens = self.vocab_tokens

            # Include context sequence count if context was provided
            if item.context_sequences:
                encode_res.context_sequence_count = len(item.context_sequences)

            results.append(encode_res)

        return E1EncodeResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict(self, payload: E1PredictRequest) -> E1PredictResponse:
        """
        Predict per-token logits for sequences containing '?' (mask) tokens.

        E1 uses '?' as the mask token (different from ESMC's <mask>).

        Returns only 20-dim logits for the canonical amino acids, ignoring the rest
        of the tokenizer's vocabulary. The vocab_tokens field matches those
        same 20 characters, in the same order.
        """

        # Build input strings with multi-sequence format
        input_strings = []
        query_positions = []
        for item in payload.items:
            input_str = self._build_multi_sequence_input(
                item.sequence, item.context_sequences
            )
            input_strings.append(input_str)
            query_positions.append(
                self._get_query_token_positions(item.sequence, item.context_sequences)
            )

        batch_out = self._forward_pass(input_strings)

        results = []
        for i, item in enumerate(payload.items):
            query_start, query_end = query_positions[i]
            seq_logits_full = batch_out.logits[i]  # [L_total, vocab_size]
            # Extract only query positions and canonical AAs
            seq_logits_canonical = (
                seq_logits_full[query_start:query_end, self.canonical_idxs]
                .cpu()
                .tolist()
            )

            # E1's mask token '?' is preserved as-is in the input sequence,
            # so we return original sequence tokens without detokenization
            results.append(
                E1PredictResponseResult(
                    logits=seq_logits_canonical,
                    sequence_tokens=list(item.sequence),
                    vocab_tokens=self.vocab_tokens,
                )
            )

        return E1PredictResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def log_prob(self, payload: E1PredictLogProbRequest) -> E1PredictLogProbResponse:
        """
        Computes the total log-prob of an unmasked sequence under E1.
        Sums over the canonical 20 amino acids only, ignoring positions with
        non-canonical residues.

        When context_sequences are provided, the model conditions on them
        using block-causal attention, which typically improves fitness predictions.

        Steps:
          1) Build multi-sequence input (context + query)
          2) Forward pass => logits
          3) For each residue position in the query:
             - Gather logits for just the 20 canonical tokens
             - Compute log-softmax over those 20
             - Add the log-prob of the actual residue
          4) Return the sum of log-probs.
        """
        # Build input strings with multi-sequence format
        input_strings = []
        query_positions = []
        for item in payload.items:
            input_str = self._build_multi_sequence_input(
                item.sequence, item.context_sequences
            )
            input_strings.append(input_str)
            query_positions.append(
                self._get_query_token_positions(item.sequence, item.context_sequences)
            )

        # Batched forward pass for all sequences
        batch_out = self._forward_pass(input_strings)  # [B, L_total, vocab_size]

        all_log_probs = []
        for i, item in enumerate(payload.items):
            query_start, query_end = query_positions[i]
            logits_full = batch_out.logits[i]  # shape [L_total, vocab_size]

            log_prob_sum = 0.0
            for pos, aa in enumerate(item.sequence):
                token_pos = query_start + pos
                c_logits = logits_full[token_pos, self.canonical_idxs]  # shape [20]
                c_log_probs = c_logits.log_softmax(dim=-1)
                # Find the index of this amino acid in our canonical list
                aa_idx = self.vocab_tokens.index(aa)
                log_prob_sum += float(c_log_probs[aa_idx])

            all_log_probs.append(log_prob_sum)

        # Convert to structured response
        results = [E1PredictLogProbResponseResult(log_prob=lp) for lp in all_log_probs]
        return E1PredictLogProbResponse(results=results)


if __name__ == "__main__":
    """
    Usage:
        MODEL_SIZE="150m" python models/e1/app.py
        MODEL_SIZE="300m" python models/e1/app.py
        MODEL_SIZE="600m" python models/e1/app.py

        # Force deploy to the configured Modal environment:
        MODEL_SIZE="150m" python models/e1/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        E1Model,
        description=f"Run and optionally deploy the {E1Params.display_name} {model_size} Modal app.",
    )
