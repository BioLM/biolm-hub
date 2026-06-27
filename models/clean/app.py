from typing import Any

import modal

from models.clean.config import MODEL_FAMILY
from models.clean.download import get_model_dir
from models.clean.schema import (
    CLEANEncodeRequest,
    CLEANEncodeResponse,
    CLEANEncodeResult,
    CLEANParams,
    CLEANPredictRequest,
    CLEANPredictResponse,
    CLEANPredictResult,
    ECPrediction,
)
from models.commons.core.decorator import modal_endpoint
from models.commons.core.logging import get_logger
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer

# NOTE: models.clean.util is imported inside methods to avoid
# torch dependency at module level (torch is only available in Modal container)
from models.commons.model.base import ModelMixinSnap
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
)
from models.commons.util.device import get_torch_device

logger = get_logger(__name__)

# Build Modal container image
image = modal.Image.from_registry("pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime")

# Setup download layer with model weights
# gdown is needed to download pretrained weights from Google Drive
image = setup_download_layer(
    image,
    base_model_slug=CLEANParams.base_model_slug,
    params_version=CLEANParams.params_version,
    variant_config=None,
    extra_pip_packages=["gdown==5.2.0"],
)

# Add dependencies
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        # ESM-1b from Facebook Research (specific commit for reproducibility)
        "https://github.com/facebookresearch/esm/archive/2b369911bb5b4b0dda914521b9475cad1656b2ac.zip",
        # Data processing
        "pandas==2.1.4",
        "numpy==1.26.4",
        # GMM for confidence estimation
        "scikit-learn==1.2.0",
    )
)

# Add model source files
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
class CLEANModel(ModelMixinSnap):
    """CLEAN: Contrastive Learning Enabled Enzyme ANnotation."""

    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def load_model(self) -> None:
        """Load all model components during snapshot creation."""
        import pickle

        import esm
        import numpy as np
        import torch

        from models.clean.util import LayerNormNet, load_ec_id_mapping

        logger.info("Loading CLEAN model components...")

        # Set deterministic behavior
        torch.manual_seed(42)
        np.random.seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

        self.device = get_torch_device()
        self.model_dir = get_model_dir()

        # Load ESM-1b model (backbone for embeddings)
        logger.info("Loading ESM-1b model...")
        self.esm_model, self.alphabet = esm.pretrained.esm1b_t33_650M_UR50S()
        self.esm_model.eval()
        self.esm_model.to(self.device)
        self.batch_converter = self.alphabet.get_batch_converter()

        # Load CLEAN projection network
        logger.info("Loading CLEAN projection network...")
        self.clean_model = LayerNormNet(hidden_dim=512, out_dim=128)
        checkpoint = torch.load(
            self.model_dir / "split100.pth",
            map_location=self.device,
            weights_only=False,  # Trusted: checkpoints from R2 model store
        )
        self.clean_model.load_state_dict(checkpoint)
        self.clean_model.eval()
        self.clean_model.to(self.device)

        # Load EC-ID mapping FIRST to know expected embedding count
        logger.info("Loading EC-ID mappings...")
        _, self.ec_id_dict = load_ec_id_mapping(self.model_dir / "split100.csv")
        self.ec_list = list(self.ec_id_dict.keys())

        # Calculate expected total sequences from EC-ID dict
        expected_n_sequences = sum(len(ids) for ids in self.ec_id_dict.values())
        n_ec_classes = len(self.ec_list)
        logger.info(
            "Found %s EC classes with %s total sequences",
            n_ec_classes,
            expected_n_sequences,
        )

        # Load precomputed per-sequence embeddings (shape: n_sequences x 128)
        # These are model embeddings for all training sequences, ordered by EC
        logger.info("Loading precomputed embeddings (100.pt)...")
        self.ec_embeddings = torch.load(
            self.model_dir / "100.pt",
            map_location=self.device,
            weights_only=False,  # Trusted: checkpoints from R2 model store
        )

        # Validate 100.pt shape and build cluster centers
        self._build_cluster_center_tensor(expected_n_sequences)

        # Load GMM ensemble for confidence estimation
        logger.info("Loading GMM ensemble...")
        with open(self.model_dir / "gmm_ensumble.pkl", "rb") as f:
            self.gmm_ensemble = pickle.load(f)

        logger.info("CLEAN model loaded with %s EC classes", len(self.ec_list))

    def _build_cluster_center_tensor(self, expected_n_sequences: int) -> None:
        """
        Build a tensor of cluster centers for efficient distance computation.

        The 100.pt file contains per-sequence embeddings ordered by EC class.
        We average them per-EC to create cluster centers.

        Args:
            expected_n_sequences: Expected number of sequences based on split100.csv
        """
        import torch

        n_ec_classes = len(self.ec_id_dict.keys())
        embedding_dim = 128

        # Validate 100.pt tensor shape
        actual_shape = self.ec_embeddings.shape
        if len(actual_shape) != 2 or actual_shape[1] != embedding_dim:
            raise RuntimeError(
                f"100.pt has unexpected shape {actual_shape}. "
                f"Expected (n_sequences, {embedding_dim})"
            )

        actual_n_sequences = actual_shape[0]
        logger.debug(
            "100.pt contains %s embeddings of dim %s", actual_n_sequences, embedding_dim
        )

        # Check if this is per-sequence embeddings or pre-averaged cluster centers
        if actual_n_sequences == n_ec_classes:
            # Already cluster centers - use directly
            logger.info("100.pt appears to contain pre-averaged cluster centers")
            self.cluster_center_tensor = self.ec_embeddings.to(self.device)
        elif actual_n_sequences == expected_n_sequences:
            # Per-sequence embeddings - need to average by EC
            logger.info(
                "100.pt contains per-sequence embeddings, computing cluster centers..."
            )
            self.cluster_center_tensor = torch.zeros(
                n_ec_classes,
                embedding_dim,
                device=self.device,
            )

            # Compute cluster centers by averaging embeddings for each EC
            idx = 0
            for i, ec in enumerate(self.ec_list):
                n_seqs = len(self.ec_id_dict[ec])
                if idx + n_seqs > actual_n_sequences:
                    raise RuntimeError(
                        f"Index overflow at EC {ec}: idx={idx}, n_seqs={n_seqs}, "
                        f"but only {actual_n_sequences} embeddings available"
                    )
                ec_embs = self.ec_embeddings[idx : idx + n_seqs]
                self.cluster_center_tensor[i] = ec_embs.mean(dim=0)
                idx += n_seqs

            logger.info("Computed %s cluster centers", n_ec_classes)
        else:
            raise RuntimeError(
                f"100.pt has {actual_n_sequences} embeddings, but expected either "
                f"{n_ec_classes} (pre-averaged) or {expected_n_sequences} (per-sequence)"
            )

        # Free memory from raw embeddings after computing centers
        del self.ec_embeddings
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    @modal.enter(snap=False)
    def setup_model(self) -> None:
        """Called after restoring from snapshot."""
        logger.info(
            "%s ready for inference on %s!", CLEANParams.display_name, self.device
        )

    def _get_esm_embeddings(self, sequences: list[str]) -> Any:
        """
        Compute ESM-1b mean embeddings for sequences.

        Args:
            sequences: List of protein sequences

        Returns:
            Tensor of shape (batch_size, 1280)
        """
        import torch

        # Prepare data for ESM batch converter
        data = [(f"seq_{i}", seq) for i, seq in enumerate(sequences)]
        _, _, tokens = self.batch_converter(data)
        tokens = tokens.to(self.device)

        # Get ESM-1b representations
        with torch.no_grad():
            results = self.esm_model(
                tokens,
                repr_layers=[33],  # Layer 33 is the last layer
                return_contacts=False,
            )

        # Extract mean representations (exclude BOS and EOS tokens)
        representations = results["representations"][33]

        # Compute mean over sequence positions (excluding special tokens)
        embeddings = []
        for i, seq in enumerate(sequences):
            seq_len = len(seq)
            # tokens[i] has shape (seq_len + 2) including BOS and EOS
            # representations[i] has shape (seq_len + 2, 1280)
            # Take positions 1 to seq_len+1 (excluding BOS at 0 and EOS at end)
            seq_repr = representations[i, 1 : seq_len + 1, :]
            mean_repr = seq_repr.mean(dim=0)
            embeddings.append(mean_repr)

        return torch.stack(embeddings)

    def _get_clean_embeddings(self, sequences: list[str]) -> Any:
        """
        Compute CLEAN embeddings (128-dim) for sequences.

        Args:
            sequences: List of protein sequences

        Returns:
            Tensor of shape (batch_size, 128)
        """
        import torch

        # Get ESM-1b embeddings
        esm_embeddings = self._get_esm_embeddings(sequences)

        # Project through CLEAN network
        with torch.no_grad():
            clean_embeddings = self.clean_model(esm_embeddings)

        return clean_embeddings

    def _compute_distances(self, embeddings: Any) -> Any:
        """
        Compute distances from embeddings to all EC cluster centers.

        Args:
            embeddings: Tensor of shape (batch_size, 128)

        Returns:
            Tensor of shape (batch_size, n_ec_classes)
        """
        import torch

        # Compute pairwise Euclidean distances
        # embeddings: (batch_size, 128)
        # cluster_center_tensor: (n_ec_classes, 128)
        distances = torch.cdist(embeddings, self.cluster_center_tensor, p=2)
        return distances

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict(self, payload: CLEANPredictRequest) -> CLEANPredictResponse:
        """
        Predict EC numbers for protein sequences.

        Uses the max-separation algorithm to select confident EC predictions
        and GMM ensemble for confidence estimation.
        """
        import numpy as np

        from models.clean.util import compute_gmm_confidence, maximum_separation

        # Extract parameters
        max_predictions = 10
        min_confidence = 0.05
        if payload.params:
            max_predictions = payload.params.max_predictions
            min_confidence = payload.params.min_confidence

        # Extract sequences
        sequences = [item.sequence for item in payload.items]
        logger.info("Predicting EC numbers for %s sequences...", len(sequences))

        # Get CLEAN embeddings
        embeddings = self._get_clean_embeddings(sequences)

        # Compute distances to all EC cluster centers
        distances = self._compute_distances(embeddings)

        # Process each sequence
        results = []
        for i in range(len(sequences)):
            seq_distances = distances[i].detach().cpu().numpy()

            # Get top candidates (sorted by distance)
            # Use max_predictions + buffer to give max-separation algorithm room to work
            top_k = min(max_predictions + 5, len(self.ec_list))
            top_indices = np.argsort(seq_distances)[:top_k]
            top_distances = seq_distances[top_indices]

            # Apply max-separation algorithm
            # Note: The original CLEAN algorithm caps at 5 predictions by design
            # (returns index 0 if separation found at index >= 5)
            cutoff_idx = maximum_separation(top_distances)

            # Build predictions up to cutoff or max_predictions, whichever is smaller
            predictions = []
            for j in range(min(cutoff_idx + 1, max_predictions)):
                ec_idx = top_indices[j]
                ec_number = self.ec_list[ec_idx]
                distance = float(top_distances[j])
                confidence = compute_gmm_confidence(distance, self.gmm_ensemble)

                # Filter by minimum confidence
                if confidence >= min_confidence:
                    predictions.append(
                        ECPrediction(
                            ec_number=ec_number,
                            distance=round(distance, 4),
                            confidence=round(confidence, 4),
                        )
                    )

            # Ensure at least one prediction (even if below threshold)
            if not predictions and cutoff_idx >= 0:
                ec_idx = top_indices[0]
                ec_number = self.ec_list[ec_idx]
                distance = float(top_distances[0])
                confidence = compute_gmm_confidence(distance, self.gmm_ensemble)
                predictions.append(
                    ECPrediction(
                        ec_number=ec_number,
                        distance=round(distance, 4),
                        confidence=round(confidence, 4),
                    )
                )

            results.append(CLEANPredictResult(predictions=predictions))

        logger.info("Completed predictions for %s sequences", len(results))
        return CLEANPredictResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(self, payload: CLEANEncodeRequest) -> CLEANEncodeResponse:
        """
        Extract CLEAN embeddings (128-dim) for protein sequences.

        These embeddings capture enzyme functional similarity - enzymes with
        similar functions will have similar embeddings.
        """
        sequences = [item.sequence for item in payload.items]
        logger.info("Encoding %s sequences...", len(sequences))

        # Get CLEAN embeddings
        embeddings = self._get_clean_embeddings(sequences)

        # Convert to response format
        results = [
            CLEANEncodeResult(embedding=emb.cpu().tolist()) for emb in embeddings
        ]

        logger.info("Completed encoding for %s sequences", len(results))
        return CLEANEncodeResponse(results=results)


if __name__ == "__main__":
    """
    Usage:
        python models/clean/app.py

        # Force deploy to QA or main:
        python models/clean/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        CLEANModel,
        description=f"Run and optionally deploy the {CLEANParams.display_name} Modal app.",
    )
