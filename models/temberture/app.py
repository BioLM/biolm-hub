from pathlib import Path

import modal

from models.commons.billing.mixin import BillingMixinSnap
from models.commons.core.decorator import modal_endpoint
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.config import biolm_model_class
from models.commons.storage.downloads import build_hf_snapshot_path
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
    redis_url_secret,
)
from models.commons.util.device import get_torch_device
from models.commons.util.environment import parse_variant
from models.temberture.config import MODEL_FAMILY
from models.temberture.download import (
    get_model_dir,
    get_shared_base_model_dir,
    hf_pinned_revision,
    hf_repo_id,
)
from models.temberture.schema import (
    TemBERTureEncodeIncludeOptions,
    TemBERTureEncodeRequest,
    TemBERTureEncodeResponse,
    TemBERTureEncodeResponseResult,
    TemBERTureModelTypes,
    TemBERTureParams,
    TemBERTurePredictRequest,
    TemBERTurePredictResponse,
    TemBERTurePredictResponseResult,
)

variant_config = parse_variant(
    env_var_name="MODEL_TYPE",
    allowed_values=TemBERTureModelTypes,
    default=TemBERTureModelTypes.CLASSIFIER,
)
model_type = variant_config["MODEL_TYPE"]


# Build Modal container image
image = modal.Image.from_registry("pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime")
# Install system dependencies first (needed for download layer)
image = image.apt_install("curl", "wget", "git")
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=TemBERTureParams.base_model_slug,
    params_version=TemBERTureParams.params_version,
    variant_config=variant_config,
)
# Add Python dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        "transformers==4.35.2",
        "adapters==0.1.1",
        "torch==2.0.1",
        "numpy==1.23.5",
        "tqdm==4.66.1",
        "huggingface_hub==0.16.4",  # Compatible version with adapters==0.1.1
    )
)
# Finally, add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)


# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config(**variant_config)
print(f"App name: {app_name}")
app = modal.App(app_name, image=image)


@app.cls(
    image=image,
    secrets=[cloudflare_r2_secret, redis_url_secret],
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class TemBERTureModel(BillingMixinSnap):
    app_username: str = modal.parameter(default="default_user")
    model_type: str = model_type

    @modal.enter(snap=True)
    def setup_model(self):
        """Load model directly on GPU for GPU memory snapshot with deterministic behavior."""
        import torch
        import torch.nn as nn
        from adapters import BertAdapterModel
        from transformers import BertTokenizer

        print(
            f"🚀 Loading TemBERTure {self.model_type} model directly on GPU for GPU memory snapshot..."
        )

        # Set deterministic behavior for consistent results
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.torch = torch
        self.adapter_dir = get_model_dir()
        self.model_name = hf_repo_id

        # Get device and setup for GPU inference
        self.device = get_torch_device()

        # Get the deterministic snapshot directory directly
        base_dir = get_shared_base_model_dir()
        self.base_model_dir = build_hf_snapshot_path(
            base_dir, hf_repo_id, hf_pinned_revision
        )

        # Set adapter path based on model type from the downloaded/cached adapters
        adapters_base_dir = Path(self.adapter_dir)
        if self.model_type == TemBERTureModelTypes.CLASSIFIER:
            self.adapter_path = str(adapters_base_dir / "temBERTure_CLS") + "/"
        else:
            # For regression, use replica1 by default
            self.adapter_path = (
                str(adapters_base_dir / "temBERTure_TM" / "replica1") + "/"
            )

        print(f"📂 Base model snapshot directory: {self.base_model_dir}")
        print(f"📂 Using {self.model_type} adapters from: {self.adapter_path}")

        # Load tokenizer from shared base model directory (HF snapshot structure)
        self.tokenizer = BertTokenizer.from_pretrained(self.base_model_dir)

        # Load model using shared base model directory (HF snapshot structure)
        self.model = BertAdapterModel.from_pretrained(self.base_model_dir)

        # Load adapter from local files (avoid hub resolution)
        adapter_dir = self.adapter_path + "AdapterBERT_adapter"
        head_dir = self.adapter_path + "AdapterBERT_head_adapter"

        print(f"🔧 Loading adapter from: {adapter_dir}")
        print(f"🔧 Loading head from: {head_dir}")

        # Check if base model and adapter files exist
        print(f"🔍 Checking base model snapshot: {self.base_model_dir}")
        print(f"🔍 Checking adapter directory: {adapter_dir}")

        if not Path(self.base_model_dir).exists():
            raise RuntimeError(
                f"Shared base model snapshot directory not found: {self.base_model_dir}"
            )

        if not Path(adapter_dir).exists():
            print(f"❌ Adapter directory not found: {adapter_dir}")
            print(f"🔍 Available directories in {self.adapter_dir}:")
            if Path(self.adapter_dir).exists():
                for item in Path(self.adapter_dir).iterdir():
                    print(f"  - {item}")
            raise RuntimeError(f"Adapter directory not found: {adapter_dir}")

        if not Path(head_dir).exists():
            raise RuntimeError(f"Head directory not found: {head_dir}")

        # Load adapter and head directly from local paths
        self.model.load_adapter(
            adapter_dir, with_head=False, load_as="AdapterBERT_adapter", source="local"
        )
        self.model.load_head(head_dir, load_as="AdapterBERT_head_adapter")
        self.model.set_active_adapters(["AdapterBERT_adapter"])
        self.model.active_head = "AdapterBERT_head_adapter"
        self.model.train_adapter(["AdapterBERT_adapter"])
        self.model.delete_head("default")
        self.model.bert.prompt_tuning = nn.Identity()

        # Move model to GPU device
        self.model.to(device=self.device)
        self.model.eval()

        # Model configuration
        self.max_sequence_len = TemBERTureParams.max_sequence_len

        print(
            f"✅ TemBERTure {self.model_type} model loaded directly on {self.device} for GPU memory snapshot!"
        )

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(self, payload: TemBERTureEncodeRequest) -> TemBERTureEncodeResponse:
        """
        Extract embeddings from protein sequences using TemBERTure.
        """
        print(
            f"🔢 TemBERTure {self.model_type} encode called with {len(payload.items)} sequences"
        )
        sequences = [item.sequence for item in payload.items]
        include = [option.value for option in payload.params.include]
        print(f"📋 Include options: {include}")

        try:
            results = self._encode_forward_pass(
                sequences=sequences,
                include=include,
            )
            print(f"✅ TemBERTure {self.model_type} encode completed successfully")
        except Exception as e:
            print(f"❌ TemBERTure {self.model_type} encode failed with error [{e}]")
            raise e

        return TemBERTureEncodeResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict(self, payload: TemBERTurePredictRequest) -> TemBERTurePredictResponse:
        """
        Predict melting temperatures or thermophilicity for protein sequences.
        """
        print(
            f"🔮 TemBERTure {self.model_type} predict called with {len(payload.items)} sequences"
        )
        sequences = [item.sequence for item in payload.items]

        try:
            results = self._predict_forward_pass(
                sequences=sequences,
            )
            print(f"✅ TemBERTure {self.model_type} predict completed successfully")
        except Exception as e:
            print(f"❌ TemBERTure {self.model_type} predict failed with error [{e}]")
            raise e

        return TemBERTurePredictResponse(results=results)

    def _encode_forward_pass(
        self,
        sequences: list[str],
        include: list[str],
    ) -> list[TemBERTureEncodeResponseResult]:
        """
        Perform encoding inference on sequences.

        Args:
            sequences: List of amino acid sequences to process
            include: List of output types to include in results

        Returns:
            List of encoding results with requested embeddings
        """
        import math

        batch_size = TemBERTureParams.batch_size
        nb_batches = math.ceil(len(sequences) / batch_size)

        results = []

        for i in range(nb_batches):
            batch_sequences = sequences[i * batch_size : (i + 1) * batch_size]

            # Preprocess sequences (add spaces between amino acids as required by protBERT)
            processed_sequences = [
                " ".join("".join(seq.split())) for seq in batch_sequences
            ]

            # Tokenize
            encoded = self.tokenizer(
                processed_sequences,
                truncation=True,
                padding=True,
                max_length=self.max_sequence_len,
                return_tensors="pt",
            ).to(self.device)

            with self.torch.no_grad():
                # Get model outputs including hidden states
                outputs = self.model(
                    input_ids=encoded["input_ids"],
                    attention_mask=encoded["attention_mask"],
                    output_hidden_states=True,
                    return_dict=True,
                )

                # Extract embeddings from the last hidden state (before the head)
                hidden_states = outputs.hidden_states[
                    -1
                ]  # [batch_size, seq_len, hidden_size]

                # Process each sequence in the batch
                for j, _seq in enumerate(batch_sequences):
                    result_dict = {"sequence_index": i * batch_size + j}

                    # Remove padding and special tokens for the actual sequence
                    attention_mask = encoded["attention_mask"][j]
                    seq_len = attention_mask.sum().item()

                    # Extract sequence embeddings (excluding CLS and SEP tokens)
                    # Remove CLS and SEP tokens
                    seq_embeddings = hidden_states[j, 1 : seq_len - 1]

                    if TemBERTureEncodeIncludeOptions.MEAN in include:
                        # Mean pooling over sequence length
                        mean_embedding = seq_embeddings.mean(dim=0).cpu().tolist()
                        result_dict["embeddings"] = mean_embedding

                    if TemBERTureEncodeIncludeOptions.PER_RESIDUE in include:
                        # Per-token embeddings
                        per_residue_embeddings = seq_embeddings.cpu().tolist()
                        result_dict["per_residue_embeddings"] = per_residue_embeddings

                    if TemBERTureEncodeIncludeOptions.CLS in include:
                        # CLS token embedding
                        cls_embedding = hidden_states[j, 0].cpu().tolist()
                        result_dict["cls_embeddings"] = cls_embedding

                    result = TemBERTureEncodeResponseResult.model_validate(result_dict)
                    results.append(result)

        # Sort results by sequence index
        results = sorted(results, key=lambda x: x.sequence_index)
        return results

    def _predict_forward_pass(
        self,
        sequences: list[str],
    ) -> list[TemBERTurePredictResponseResult]:
        """
        Perform prediction inference on sequences.

        Args:
            sequences: List of amino acid sequences

        Returns:
            List of prediction results
        """
        import math

        import numpy as np

        print(
            f"🔍 Processing {len(sequences)} sequences for {self.model_type} prediction"
        )

        batch_size = TemBERTureParams.batch_size
        nb_batches = math.ceil(len(sequences) / batch_size)

        print(f"📦 Processing in {nb_batches} batches of size {batch_size}")

        results = []

        for i in range(nb_batches):
            batch_sequences = sequences[i * batch_size : (i + 1) * batch_size]
            print(
                f"⚙️  Processing batch {i+1}/{nb_batches} with {len(batch_sequences)} sequences"
            )

            # Preprocess sequences (add spaces between amino acids as required by protBERT)
            processed_sequences = [
                " ".join("".join(seq.split())) for seq in batch_sequences
            ]

            # Tokenize
            encoded = self.tokenizer(
                processed_sequences,
                truncation=True,
                padding=True,
                max_length=self.max_sequence_len,
                return_tensors="pt",
            ).to(self.device)

            with self.torch.no_grad():
                outputs = self.model(**encoded)
                logits = outputs.logits.reshape(-1).cpu().tolist()
                print(f"📊 Got {len(logits)} predictions from model")

            # Process predictions based on model type
            for j, pred in enumerate(logits):
                result_dict = {"prediction": float(pred)}

                if self.model_type == "classifier":
                    # Apply sigmoid and convert to classification
                    prob = 1 / (1 + np.exp(-pred))
                    classification = (
                        "Thermophilic" if prob > 0.5 else "Non-thermophilic"
                    )
                    result_dict["classification"] = classification
                    # Return probability instead of logit
                    result_dict["prediction"] = float(prob)
                    print(f"🏷️  Sequence {j+1}: {classification} (prob: {prob:.4f})")
                else:
                    print(f"🌡️  Sequence {j+1}: Tm = {pred:.2f}°C")

                result = TemBERTurePredictResponseResult.model_validate(result_dict)
                results.append(result)

        print(f"✅ Completed prediction for {len(results)} sequences")
        return results


if __name__ == "__main__":
    """
    Usage:
        MODEL_TYPE="classifier" python models/temberture/app.py
        MODEL_TYPE="regression" python models/temberture/app.py

        # Force deploy to "qa" or "main" environment:
        MODEL_TYPE="classifier" python models/temberture/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        TemBERTureModel,
        description=f"Run and optionally deploy the {TemBERTureParams.display_name} {model_type} Modal app.",
    )
