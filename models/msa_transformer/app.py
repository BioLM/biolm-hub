import modal

from models.commons.model.base import ModelMixinSnap
from models.commons.core.decorator import modal_endpoint
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
)
from models.commons.util.device import get_torch_device
from models.msa_transformer.config import MODEL_FAMILY
from models.msa_transformer.download import get_model_dir
from models.msa_transformer.schema import (
    LayerEmbedding,
    LayerPerTokenEmbeddings,
    MSATransformerEncodeRequest,
    MSATransformerEncodeResponse,
    MSATransformerEncodeResponseResult,
    MSATransformerParams,
)

# Build Modal container image
image = modal.Image.from_registry("pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime")
# Setup download layer with model weights
# Include fair-esm so the fallback download strategy can use it
image = setup_download_layer(
    image,
    base_model_slug=MSATransformerParams.base_model_slug,
    params_version=MSATransformerParams.params_version,
    variant_config={},  # Single variant
    extra_pip_packages=[
        # fair-esm 2.0.1 from GitHub (needed for fallback download)
        "https://github.com/facebookresearch/esm/archive/2b369911bb5b4b0dda914521b9475cad1656b2ac.zip",
    ],
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        # Install fair-esm 2.0.1 from GitHub ZIP archive (same as ESM2)
        "https://github.com/facebookresearch/esm/archive/2b369911bb5b4b0dda914521b9475cad1656b2ac.zip",
    )
)
# Finally, add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)


# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config()
print(f"App name: {app_name}")
app = modal.App(app_name, image=image)


@app.cls(
    image=image,
    secrets=[cloudflare_r2_secret],
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class MSATransformerModel(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def setup_model(self):
        """Load model directly on GPU for GPU memory snapshot with deterministic behavior."""
        import esm
        import torch

        print(
            "Loading MSA Transformer model directly on GPU for GPU memory snapshot..."
        )

        # Set deterministic behavior for consistent results
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.torch = torch
        self.device = get_torch_device()
        self.model_dir = get_model_dir()

        # Set torch hub directory for model caching
        torch.hub.set_dir(self.model_dir)

        # Load the MSA Transformer model
        print("Loading MSA Transformer (esm_msa1b_t12_100M_UR50S)...")
        self.model, self.alphabet = esm.pretrained.esm_msa1b_t12_100M_UR50S()
        self.model.eval()
        self.model.to(device=self.device)

        # Get batch converter for MSA inputs
        self.batch_converter = self.alphabet.get_batch_converter()

        # Store model config
        self.num_layers = self.model.num_layers
        self.max_sequence_len = MSATransformerParams.max_sequence_len

        print(
            f"MSA Transformer loaded on {self.device}! "
            f"(layers={self.num_layers}, max_len={self.max_sequence_len})"
        )

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(
        self, payload: MSATransformerEncodeRequest
    ) -> MSATransformerEncodeResponse:
        """
        Encode MSAs and return embeddings, attention maps, and/or contacts.

        Parameters:
        - payload (MSATransformerEncodeRequest): Request with MSA inputs and parameters

        Returns:
        - MSATransformerEncodeResponse: Embeddings and optional attention/contacts
        """
        repr_layers = payload.params.repr_layers
        include = [opt.value for opt in payload.params.include]

        # Validate and normalize repr_layers
        n_max_layers = self.num_layers
        if not all(-(n_max_layers + 1) <= i <= n_max_layers for i in repr_layers):
            raise ValueError(
                f"Requested representation layers are out of bounds. Ensure the "
                f"layer indices are between -{n_max_layers + 1} and {n_max_layers}."
            )
        # Convert negative indices to positive
        repr_layers = [(i + n_max_layers + 1) % (n_max_layers + 1) for i in repr_layers]

        results = []
        for idx, item in enumerate(payload.items):
            print(f"Processing MSA {idx + 1} of {len(payload.items)}")
            result = self._encode_msa(
                msa=item.msa,
                repr_layers=repr_layers,
                include=include,
                sequence_index=idx,
            )
            results.append(result)

        return MSATransformerEncodeResponse(results=results)

    def _encode_msa(
        self,
        msa: list[str],
        repr_layers: list[int],
        include: list[str],
        sequence_index: int,
    ) -> MSATransformerEncodeResponseResult:
        """
        Encode a single MSA.

        Args:
            msa: List of aligned sequences (first is query)
            repr_layers: Layer indices to extract representations from
            include: What outputs to include (mean, per_token, row_attention, contacts)
            sequence_index: Index of this MSA in the batch

        Returns:
            Encoding result for this MSA
        """
        # Separate flags for efficiency: need_head_weights enables attention extraction,
        # return_contacts additionally runs the expensive contact prediction head.
        # Only run contact head when explicitly requested.
        need_head_weights = "row_attention" in include or "contacts" in include
        return_contacts = "contacts" in include

        # Prepare MSA for model
        # Format: list of (label, sequence) tuples for each sequence in MSA
        msa_data = [(f"seq_{i}", seq) for i, seq in enumerate(msa)]

        # Convert to tokens - batch_converter handles MSA format
        # For MSA models, input is a list of MSAs, where each MSA is a list of (label, seq) tuples
        # Single MSA batch: [[("seq_0", seq0), ("seq_1", seq1), ...]]
        batch_labels, batch_strs, batch_tokens = self.batch_converter([msa_data])

        # batch_tokens shape: [1, num_seqs, seq_len] for single MSA
        batch_tokens = batch_tokens.to(device=self.device, non_blocking=False)

        try:
            with self.torch.no_grad():
                model_output = self.model(
                    batch_tokens,
                    repr_layers=repr_layers,
                    need_head_weights=need_head_weights,
                    return_contacts=return_contacts,
                )
        except Exception as e:
            print(f"Model call failed with error [{e}]")
            raise e

        # Extract outputs
        result_dict: dict = {"sequence_index": sequence_index}
        seq_len = len(msa[0])  # Length of aligned sequences

        # Representations shape: [1, num_seqs, seq_len, embed_dim]
        # We extract from query sequence (first row, index 0)
        representations = {
            layer: r.cpu() for layer, r in model_output["representations"].items()
        }

        if "mean" in include:
            # Mean embedding of query sequence (first row)
            result_dict["embeddings"] = [
                LayerEmbedding(
                    layer=layer_n,
                    # [1, num_seqs, seq_len, embed_dim] -> [seq_len, embed_dim] -> [embed_dim]
                    embedding=t[0, 0, 1 : seq_len + 1].mean(dim=0).clone().tolist(),
                )
                for layer_n, t in representations.items()
            ]

        if "per_token" in include:
            # Per-token embeddings of query sequence
            result_dict["per_token_embeddings"] = [
                LayerPerTokenEmbeddings(
                    layer=layer_n,
                    # Remove BOS token, keep seq_len tokens
                    embeddings=t[0, 0, 1 : seq_len + 1].clone().tolist(),
                )
                for layer_n, t in representations.items()
            ]

        if "row_attention" in include and "row_attentions" in model_output:
            # Row attentions are the tied attention maps (shared across MSA rows)
            # Actual shape from ESM: [batch, num_layers, num_heads, seq_len+2, seq_len+2]
            # The +2 accounts for BOS and EOS tokens
            row_attn = model_output["row_attentions"].cpu()
            # row_attn[0] shape: [num_layers, num_heads, seq_len+2, seq_len+2]
            # Average over heads only (dim=1), keep layers separate
            # Result: [num_layers, seq_len+2, seq_len+2]
            avg_attn = row_attn[0].mean(dim=1)
            # Remove BOS/EOS tokens (first and last positions)
            avg_attn = avg_attn[:, 1 : seq_len + 1, 1 : seq_len + 1]
            result_dict["row_attentions"] = avg_attn.clone().tolist()

        if "contacts" in include and "contacts" in model_output:
            # Contacts shape: [1, seq_len, seq_len]
            contacts = model_output["contacts"][0].cpu()
            result_dict["contacts"] = contacts.clone().tolist()

        return MSATransformerEncodeResponseResult.model_validate(result_dict)


if __name__ == "__main__":
    """
    Usage:
        python models/msa_transformer/app.py

        # Force deploy to "qa" or "main" environment:
        python models/msa_transformer/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        MSATransformerModel,
        description=f"Run and optionally deploy the {MSATransformerParams.display_name} Modal app.",
    )
