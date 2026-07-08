import importlib
import os
from typing import TYPE_CHECKING

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
from models.esmc.config import MODEL_FAMILY
from models.esmc.download import get_model_dir, get_model_id
from models.esmc.schema import (
    ESMCEncodeIncludeOptions,
    ESMCEncodeRequest,
    ESMCEncodeResponse,
    ESMCEncodeResponseResult,
    ESMCLogProbRequest,
    ESMCLogProbResponse,
    ESMCLogProbResponseResult,
    ESMCModelSizes,
    ESMCParams,
    ESMCPredictRequest,
    ESMCPredictResponse,
    ESMCPredictResponseResult,
    LayerEmbedding,
    LayerPerTokenEmbeddings,
)

logger = get_logger(__name__)

if TYPE_CHECKING:
    from esm.models.esmc import ESMCOutput


variant_config = parse_variant(
    env_var_name="MODEL_SIZE",
    allowed_values=ESMCModelSizes,
    default=ESMCModelSizes.SIZE_300M,
)
model_size = variant_config["MODEL_SIZE"]


# Build Modal container image
image = modal.Image.from_registry("pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime")
# Setup download layer with model weights.
# Include huggingface_hub so the r2_then_hf fallback can import it at build time
# (the download layer runs before the main dependency install below).
image = setup_download_layer(
    image,
    base_model_slug=ESMCParams.base_model_slug,
    weights_version=ESMCParams.weights_version,
    variant_config=variant_config,
    extra_pip_packages=["huggingface_hub==0.36.2"],
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .uv_pip_install("esm==3.1.3")
    .uv_pip_install("huggingface_hub==0.36.2")
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
class ESMCModel(ModelMixinSnap):
    model_size: str = model_size
    model_id: str = get_model_id(model_size)

    """
    ESMCModel class offers these methods:
     - encode() => computes embeddings
     - predict() => per-token logits for masked tokens
     - log_prob() => total log-prob of an unmasked sequence
    """

    @modal.enter(snap=True)
    def setup_model(self) -> None:
        """
        Load ESM C model directly on GPU for GPU memory snapshot.
        """
        import torch

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

        from esm.models.esmc import ESMC

        # Load the model on GPU
        logger.info(
            "Loading ESM C model from directory: %s on %s...",
            self.model_dir,
            self.device,
        )
        self.model = ESMC.from_pretrained(model_name=self.model_id, device=self.device)
        self.model.eval()

        logger.info(
            "ESM C model '%s' loaded successfully on %s", self.model_id, self.device
        )

        # Import aa_unambiguous after other imports are done
        from models.commons.data.validator import aa_unambiguous

        # Build a map from each canonical AA to its index in the ESMC tokenizer
        # so we can slice out just those 20 columns from the logits.
        # Example: if the tokenizer has "A" at vocab_index=5, "C"=23, ...
        self.vocab_tokens = list(aa_unambiguous)  # ["A","C","D","E","F", ... ,"Y"]
        self.canonical_idxs = []
        for aa in self.vocab_tokens:
            idx = self.model.tokenizer.convert_tokens_to_ids(aa)
            self.canonical_idxs.append(idx)

    def _forward_pass(self, sequences: list[str]) -> "ESMCOutput":
        """
        Single batched forward pass over the input list of sequences.
        Returns an ESMCOutput object with .sequence_logits, .hidden_states, etc.
        """
        input_ids = self.model._tokenize(sequences)
        with self.torch.no_grad():
            batch_out = self.model(input_ids)
        return batch_out

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(self, payload: ESMCEncodeRequest) -> ESMCEncodeResponse:
        """
        Encode sequences with ESM C, possibly across multiple layers.

        We return the following fields in ESMCEncodeResponseResult,
        depending on what is in payload.params.include:
          - embeddings: [{layer: <int>, embedding: [d_embed]}, ...]
          - residue_embeddings: [{layer: <int>, embedding: [[d_embed]]}, ...]
          - logits: [[20], ...], restricted to canonical AAs only.
          - vocab_tokens: ["A", "C", ...]

        User may specify multiple repr_layers (e.g. [-1, 0, 5])
        and negative indices are converted accordingly.
        """
        include_options = payload.params.include
        requested_layers = payload.params.repr_layers

        input_sequences = [item.sequence for item in payload.items]
        batch_out = self._forward_pass(input_sequences)
        # `batch_out.sequence_logits`: shape [B, L+2, vocab_size]
        # `batch_out.hidden_states`: shape [n_layers, B, L+2, d_embed]

        results = []
        for i, _ in enumerate(payload.items):
            # Prepare the response object
            encode_res = ESMCEncodeResponseResult()

            if (
                ESMCEncodeIncludeOptions.MEAN in include_options
                or ESMCEncodeIncludeOptions.PER_RESIDUE in include_options
            ) and batch_out.hidden_states is not None:
                n_layers = batch_out.hidden_states.shape[0]

                # Validate repr_layers before use; raise a typed error for any out-of-range index
                # (matches the esm2 house pattern; mirrors models/esm2/app.py:244-248).
                if not all(
                    -(n_layers) <= lyr <= n_layers - 1 for lyr in requested_layers
                ):
                    raise ValidationError400(
                        f"Requested representation layers are out of bounds. "
                        f"ESM C has {n_layers} layers; valid indices are "
                        f"-{n_layers} to {n_layers - 1}."
                    )

                # Convert user repr_layers to positive indices
                layers_to_use = [
                    (lyr + n_layers) if lyr < 0 else lyr for lyr in requested_layers
                ]

                # embeddings
                if ESMCEncodeIncludeOptions.MEAN in include_options:
                    embedding_list = []
                    for lyr_idx in layers_to_use:
                        layer_emb = batch_out.hidden_states[lyr_idx][
                            i
                        ]  # [L+2, d_embed]
                        mean_vec = (
                            layer_emb[1:-1].mean(dim=0).cpu().tolist()
                        )  # Remove BOS/EOS
                        embedding_list.append(
                            LayerEmbedding(layer=lyr_idx, embedding=mean_vec)
                        )
                    encode_res.embeddings = embedding_list

                # residue_embeddings
                if ESMCEncodeIncludeOptions.PER_RESIDUE in include_options:
                    per_token_list = []
                    for lyr_idx in layers_to_use:
                        layer_emb = batch_out.hidden_states[lyr_idx][
                            i
                        ]  # [L+2, d_embed]
                        # Remove BOS/EOS => shape [L, d_embed]
                        emb_2d = layer_emb[1:-1].cpu().tolist()
                        per_token_list.append(
                            LayerPerTokenEmbeddings(layer=lyr_idx, embeddings=emb_2d)
                        )
                    encode_res.residue_embeddings = per_token_list

            if (
                ESMCEncodeIncludeOptions.LOGITS in include_options
                and batch_out.sequence_logits is not None
            ):
                # seq_logits_full: shape [L+2, vocab_size]
                seq_logits_full = batch_out.sequence_logits[i]
                # Remove BOS/EOS
                seq_logits_canonical = seq_logits_full[1:-1, self.canonical_idxs]
                encode_res.logits = seq_logits_canonical.cpu().tolist()
                encode_res.vocab_tokens = self.vocab_tokens

            results.append(encode_res)

        return ESMCEncodeResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict(self, payload: ESMCPredictRequest) -> ESMCPredictResponse:
        """
        Predict per-token logits for sequences containing <mask> tokens.

        Returns only 20-dim logits for the canonical amino acids, ignoring the rest
        of the tokenizer's vocabulary. The vocab_tokens field matches those
        same 20 characters, in the same order.
        """

        input_sequences = [item.sequence for item in payload.items]
        batch_out = self._forward_pass(input_sequences)

        batch_input_ids = self.model._tokenize(input_sequences)  # shape [B, L+2]
        decoded_list = self.model._detokenize(batch_input_ids)  # list of strings

        results = []
        for i, _ in enumerate(payload.items):
            seq_logits_full = batch_out.sequence_logits[i]  # [L+2, vocab_size]
            # Remove BOS/EOS
            seq_logits_canonical = (
                seq_logits_full[1:-1, self.canonical_idxs].cpu().tolist()
            )

            results.append(
                ESMCPredictResponseResult(
                    logits=seq_logits_canonical,
                    sequence_tokens=list(decoded_list[i]),
                    vocab_tokens=self.vocab_tokens,
                )
            )

        return ESMCPredictResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def log_prob(self, payload: ESMCLogProbRequest) -> ESMCLogProbResponse:
        """
        Computes the total log-prob of an unmasked sequence under ESM C.
        Sums over the canonical 20 amino acids only, ignoring positions with
        non-canonical residues.

        Steps:
          1) Tokenize the given sequence => input_ids
          2) Forward pass => logits shape [L+2, full_vocab_size]
          3) For each residue position:
             - If it's in the 20 canonical AAs:
                 a) Gather logits for just those 20 canonical tokens
                 b) Compute log-softmax over those 20
                 c) Add the log-prob of the actual residue
          4) Return the sum of log-probs.
        """
        sequences = [item.sequence for item in payload.items]

        # 1) Batched forward pass for all sequences
        batch_out = self._forward_pass(sequences)  # [B, L+2, vocab_size]

        all_log_probs = []
        for i, seq in enumerate(sequences):
            logits_full = batch_out.sequence_logits[i]  # shape [L+2, vocab_size]

            log_prob_sum = 0.0
            for pos, aa in enumerate(seq):
                aa_idx = self.model.tokenizer.convert_tokens_to_ids(aa)
                c_logits = logits_full[pos + 1, self.canonical_idxs]  # shape [20]
                c_log_probs = c_logits.log_softmax(dim=-1)
                sub_idx = self.canonical_idxs.index(aa_idx)
                log_prob_sum += float(c_log_probs[sub_idx])

            all_log_probs.append(log_prob_sum)

        # Convert to structured response
        results = [ESMCLogProbResponseResult(log_prob=lp) for lp in all_log_probs]
        return ESMCLogProbResponse(results=results)


if __name__ == "__main__":
    """
    Usage:
        MODEL_SIZE="300m" python models/esmc/app.py

        # Force deploy to "biolm-hub-dev" or "biolm-hub" environment:
        MODEL_SIZE="300m" python models/esmc/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        ESMCModel,
        description=f"Run and optionally deploy the {ESMCParams.display_name} {model_size} Modal app.",
    )
