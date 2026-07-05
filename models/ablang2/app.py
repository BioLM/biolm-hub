from pathlib import Path

import modal

from models.ablang2.config import MODEL_FAMILY, N_CPUS
from models.ablang2.download import get_model_dir
from models.ablang2.schema import (
    AbLang2EncodeOptions,
    AbLang2EncodeRequest,
    AbLang2EncodeResponse,
    AbLang2EncodeResult,
    AbLang2GenerateRequest,
    AbLang2GenerateResponse,
    AbLang2GenerateResponseResult,
    AbLang2LikelihoodResult,
    AbLang2LogProbRequest,
    AbLang2LogProbResponse,
    AbLang2LogProbResponseResult,
    AbLang2Params,
    AbLang2PredictRequest,
    AbLang2PredictResponse,
)
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

logger = get_logger(__name__)


# Build Modal container image
image = (
    modal.Image.from_registry("pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime")
    .apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    # NOTE: Pre-install all dependencies if download layer might depend upon it
    .uv_pip_install(
        "ablang2==0.2.1",
        "einops==0.8.1",
        "rotary-embedding-torch==0.8.9",
    )
)
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=AbLang2Params.base_model_slug,
    weights_version=AbLang2Params.weights_version,
    variant_config=None,  # this model has no variants
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
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class AbLang2Model(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def load_model(self) -> None:
        """
        Loads the AbLang2 model on CPU for memory snapshot.

        The model weights are already downloaded and symlinked during the image build phase.
        The symlink is created by download.py to point ablang2 to our cached weights.
        """
        import torch
        from ablang2.pretrained import pretrained

        logger.info("Loading Ablang2 model on CPU for memory snapshot...")

        # Set deterministic behavior for consistent results across CPU loading
        torch.manual_seed(42)

        self.torch = torch
        self.model_dir = get_model_dir()

        logger.info("AbLang2 model directory: %s", self.model_dir)

        # Verify the symlink exists (should have been created during download phase)
        import ablang2

        module_dir = Path(ablang2.__file__).parent
        expected_symlink = module_dir / "model-weights-ablang2-paired"

        if expected_symlink.exists() and expected_symlink.is_symlink():
            logger.info(
                "Symlink verified: %s -> %s",
                expected_symlink,
                expected_symlink.resolve(),
            )

            # Verify model files are accessible through the symlink
            if (expected_symlink / "model.pt").exists():
                logger.info("model.pt accessible through symlink")
            else:
                logger.warning("model.pt not found through symlink")

            if (expected_symlink / "hparams.json").exists():
                logger.info("hparams.json accessible through symlink")
            else:
                logger.warning("hparams.json not found through symlink")
        else:
            logger.warning("Expected symlink not found at %s", expected_symlink)
            logger.warning("AbLang2 may attempt to download weights on its own")

        # Load the model on CPU first
        # AbLang2 will use the symlinked weights directory
        logger.info("Loading AbLang2 pretrained model...")
        self.model = pretrained(
            model_to_use="ablang2-paired",
            random_init=False,
            ncpu=N_CPUS,
            device="cpu",  # Force CPU loading for snapshot
        )
        self.model.freeze()  # Since we are in inference mode

        self.vocab_tokens = [self.model.tokenizer.token_to_aa[i] for i in range(1, 21)]

        logger.info("Completed CPU load of AbLang2 model for memory snapshot")

        # Diagnostic: Check if ablang2 created any new download directories
        common_download_locations = [
            Path.home() / ".cache" / "ablang2",
            Path.home() / ".ablang",
            Path("/tmp") / "ablang2",
        ]
        for location in common_download_locations:
            if location.exists():
                logger.warning(
                    "Found ablang2 directory at %s - may indicate bypass", location
                )

    @modal.enter(snap=False)
    def setup_model(self) -> None:
        """
        Transfers the model to the inference device (GPU when available).
        """

        # Set deterministic behavior for consistent results across GPU loading
        if self.torch.cuda.is_available():
            self.torch.cuda.manual_seed_all(42)

        # Get device and transfer model to GPU
        self.device = get_torch_device()

        logger.info("Transferring AbLang2 model to device=%s...", self.device)
        self.model.AbLang.to(self.device)
        self.model.AbLang.eval()

        logger.info("AbLang2 model ready for inference")

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(
        self,
        payload: AbLang2EncodeRequest,
    ) -> AbLang2EncodeResponse:
        """
        Single endpoint that runs either seqcoding or rescoding, returning a
        unified AbLang2EncodeResponse. Per item, `embeddings` is populated for
        seqcoding and `residue_embeddings` for rescoding (depending on
        payload.params.include); the unused field is dropped on serialization.
        """
        input_batch = [(item.heavy_chain, item.light_chain) for item in payload.items]
        include = payload.params.include  # "seqcoding" or "rescoding"

        if payload.params.align:
            raise ValidationError400(
                "align=True is not yet supported; it requires ANARCI which is not installed. "
                "Set align=False (the default)."
            )

        align = False

        if include == AbLang2EncodeOptions.SEQCODING:
            raw_output = self.model(
                input_batch,
                mode="seqcoding",
                align=align,
                batch_size=AbLang2Params.batch_size,
            )

            results: list[AbLang2EncodeResult] = []
            for emb_vector in raw_output:
                results.append(
                    AbLang2EncodeResult(embeddings=emb_vector.astype(float).tolist())
                )

            return AbLang2EncodeResponse(results=results)

        else:
            raw_output = self.model(
                input_batch,
                mode="rescoding",
                align=False,
                batch_size=AbLang2Params.batch_size,
            )

            rescoding_results: list[AbLang2EncodeResult] = []
            number_alignment = None

            if hasattr(raw_output, "aligned_embeds"):

                aligned_data = raw_output.aligned_embeds  # shape [B, L, embed_dim]
                for i in range(len(aligned_data)):
                    row = aligned_data[i].astype(float).tolist()
                    rescoding_results.append(
                        AbLang2EncodeResult(residue_embeddings=row)
                    )

                if hasattr(raw_output, "number_alignment"):
                    number_alignment = list(raw_output.number_alignment)

            else:

                for per_item_matrix in raw_output:
                    rescoding_results.append(
                        AbLang2EncodeResult(
                            residue_embeddings=per_item_matrix.astype(float).tolist()
                        )
                    )

            return AbLang2EncodeResponse(
                results=rescoding_results,
                number_alignment=number_alignment,
            )

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict(self, payload: AbLang2PredictRequest) -> AbLang2PredictResponse:
        """
        Uses ablang2's "likelihood" mode, which computes the per-position logits.
        Note: _predict_logits is an internal ablang2 API (pinned to ==0.2.1).
        """
        input_batch = [(item.heavy_chain, item.light_chain) for item in payload.items]

        raw_output = self.model(
            input_batch,
            mode="likelihood",
            batch_size=AbLang2Params.batch_size,
        )

        results = []
        for logits_matrix, item in zip(raw_output, payload.items, strict=False):
            canonical_logits_matrix = logits_matrix[:, 1:21]
            results.append(
                AbLang2LikelihoodResult(
                    logits=canonical_logits_matrix.astype(float).tolist(),
                    sequence_tokens=list(f"<{item.heavy_chain}>|<{item.light_chain}>"),
                    vocab_tokens=self.vocab_tokens,
                )
            )

        return AbLang2PredictResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def generate(self, payload: AbLang2GenerateRequest) -> AbLang2GenerateResponse:
        align = payload.params.align
        input_batch = [(item.heavy_chain, item.light_chain) for item in payload.items]

        raw_output = self.model(
            input_batch,
            mode="restore",
            align=align,
            batch_size=AbLang2Params.batch_size,
        )

        results = []
        for seq_str in raw_output:
            heavy, light = (part.strip("<>") for part in seq_str.split("|"))
            results.append(
                AbLang2GenerateResponseResult(heavy_chain=heavy, light_chain=light)
            )

        return AbLang2GenerateResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def log_prob(self, payload: AbLang2LogProbRequest) -> AbLang2LogProbResponse:
        # 1. Format the input sequences (using the same convention as elsewhere)
        formatted_batch = [
            f"<{item.heavy_chain}>|<{item.light_chain}>" for item in payload.items
        ]

        # 2. Get the token IDs for the formatted sequences.
        #    (Assume that the tokenizer returns a torch.Tensor of shape [B, L],
        #     where B is the batch size and L is the sequence length, and that
        #     padding tokens are set to 0.)
        tokens = self.model.tokenizer(
            formatted_batch, pad=True, w_extra_tkns=False, device=self.model.used_device
        )

        # 3. Get the raw logits (without converting to numpy) so we can work with torch.
        #    Here we bypass the "likelihood" helper since that converts to numpy.
        raw_logits = self.model._predict_logits(formatted_batch)
        # raw_logits has shape [B, L, vocab_size]. We know that:
        #   - The logits for canonical amino acids are in positions 1 to 20.
        #   - Positions outside that range are extra/special tokens.
        logits_canonical = raw_logits[:, :, 1:21]  # now shape is [B, L, 20]

        # 4. Compute log probabilities along the last dimension.
        log_probs = self.torch.nn.functional.log_softmax(
            logits_canonical, dim=-1
        )  # shape [B, L, 20]

        # 5. For each sequence, iterate over token positions.
        #    For positions where the true token (from `tokens`) is in the range 1..20,
        #    add the corresponding log probability.
        total_log_probs = []
        # tokens is expected to be a tensor of shape [B, L]
        for i in range(tokens.shape[0]):
            seq_tokens = tokens[i]  # shape [L]
            seq_log_probs = log_probs[i]  # shape [L, 20]
            total_lp = 0.0
            # Iterate over each position in the sequence.
            # We exclude tokens that are outside 1-20 since they correspond to padding or
            # noncanonical characters
            for pos, t in enumerate(seq_tokens):
                t_val = t.item()
                # Only consider tokens corresponding to canonical amino acids (token IDs 1-20)
                if 1 <= t_val <= 20:
                    # Because our logits slice has indices 0-19 corresponding to token IDs 1-20:
                    total_lp += seq_log_probs[pos, t_val - 1].item()
            total_log_probs.append(total_lp)

        # 6. Convert to structured response
        results = [AbLang2LogProbResponseResult(log_prob=lp) for lp in total_log_probs]
        return AbLang2LogProbResponse(results=results)


if __name__ == "__main__":
    """
    Usage:
        python models/ablang2/app.py

        # Force deploy to "biolm-hub-dev" or "biolm-hub" environment:
        python models/ablang2/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        AbLang2Model,
        description=f"Run and optionally deploy the {AbLang2Params.display_name} Modal app.",
    )
