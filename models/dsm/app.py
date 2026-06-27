from typing import TYPE_CHECKING

import modal

if TYPE_CHECKING:
    from torch import Tensor

from models.commons.billing.mixin import BillingMixinSnap
from models.commons.core.decorator import modal_endpoint
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
    redis_url_secret,
)
from models.commons.util.device import get_torch_device
from models.commons.util.environment import parse_variants
from models.dsm.config import DSM_HF_REPO_MAP, DSM_HF_REVISION_MAP, MODEL_FAMILY
from models.dsm.download import get_model_dir, get_model_id
from models.dsm.schema import (
    DSMEncodeIncludeOptions,
    DSMEncodeRequest,
    DSMEncodeResponse,
    DSMEncodeResponseResult,
    DSMGenerateRequest,
    DSMGenerateResponse,
    DSMGenerateResponseResult,
    DSMModelSizes,
    DSMParams,
    DSMScoreRequest,
    DSMScoreResponse,
    DSMScoreResponseResult,
    DSMVariants,
)

# Parse variant configuration
variant_config = parse_variants(
    [
        {
            "env_var_name": "MODEL_SIZE",
            "allowed_values": DSMModelSizes,
            "default": DSMModelSizes.SIZE_650M,
        },
        {
            "env_var_name": "VARIANT",
            "allowed_values": DSMVariants,
            "default": DSMVariants.BASE,
        },
    ]
)
model_size = variant_config["MODEL_SIZE"]
variant = variant_config["VARIANT"]


# Build Modal container image
image = modal.Image.debian_slim(python_version="3.12")
image = image.apt_install("git").apt_install("bash").env({"SHELL": "/bin/bash"})
# Add dependencies and packages
image = image.apt_install("procps")  # Critical for computing container uptime
image = image.uv_pip_install(common_requirements)
image = image.uv_pip_install(
    [
        # Core ML libraries
        "torch==2.9.0",
        "transformers==4.57.1",
        "datasets==4.3.0",
        "tokenizers==0.22.1",
        "safetensors==0.6.2",
        "huggingface_hub==0.36.0",
        # Scientific computing
        "numpy==1.26.4",
        "scipy==1.16.2",
        "scikit-learn==1.7.2",
        "pandas==2.3.3",
        # Plotting
        "matplotlib==3.10.7",
        "seaborn==0.13.2",
        # Utilities
        "tqdm==4.67.1",
        "joblib==1.5.2",
        # Protein-specific
        "biopython==1.84",
        "biotite==1.5.0",
        # DSM dependencies (from DSM/requirements.txt)
        "einops==0.8.1",
        "torchmetrics==1.8.2",
        "torchinfo==1.8.0",
        "peft==0.17.1",
        "sentencepiece==0.2.1",
        "accelerate==1.11.0",
    ]
)

image = image.run_commands(
    [
        "ln -sf /bin/bash /bin/sh",
        "echo 'Now all scripts use bash by default'",
    ]
)

# Add DSM model source code (pinned to known-working commit)
# The --remote flag on submodule update was fetching latest FastPLMs HEAD which
# introduced an entrypoint_setup dependency not available in our build env.
# Pin to ca7b5c8c (Nov 4, 2025) and use recorded submodule commits instead.
DSM_REPO_COMMIT = "ca7b5c8c4a6a50517d6d7f41026886e9812e04e4"
image = image.run_commands(
    [
        "git clone https://github.com/Gleghorn-Lab/DSM.git /root/DSM",
        f"cd /root/DSM && git checkout {DSM_REPO_COMMIT}",
        "cd /root/DSM && git submodule update --init --recursive",
    ]
)
image = image.run_commands(
    [
        "cd /root/DSM && chmod +x setup_bioenv.sh",
        "cd /root/DSM && ./setup_bioenv.sh",
    ]
)
image = image.run_commands(
    [
        # Create a setup.py for DSM to enable proper package installation
        "cd /root/DSM && python -c \"with open('setup.py', 'w') as f: f.write('from setuptools import setup, find_packages\\\\nsetup(name=\\\"dsm\\\", version=\\\"0.1.0\\\", packages=find_packages(), install_requires=[])\\\\n')\"",
        # Create __init__.py for models package
        "cd /root/DSM && touch models/__init__.py",
        "/root/bioenv/bin/python -m pip install -e /root/DSM",
        # Verify the installation
        '/root/bioenv/bin/python -c \'import sys; sys.path.insert(0, "/root/DSM"); from models.modeling_dsm import DSM; print("DSM import successful")\'',
    ]
)
# Set PYTHONPATH to include DSM repository
image = image.env({"PYTHONPATH": "/root/DSM"})

image = setup_download_layer(
    image,
    base_model_slug=DSMParams.base_model_slug,
    params_version=DSMParams.params_version,
    variant_config=variant_config,
    extra_pip_packages=["huggingface_hub==0.36.0"],
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
class DSMModel(BillingMixinSnap):
    app_username: str = modal.parameter(default="default_user")
    model_size: DSMModelSizes = model_size
    variant: DSMVariants = variant
    model_id: str = get_model_id(model_size, variant)

    """
    DSMModel class offers these methods:
     - generate() => generate protein sequences (masked or unconditional)
     - encode() => compute embeddings
     - score() => calculate log probabilities
    """

    @modal.enter(snap=True)
    def setup_model(self):  # noqa: C901
        # FIXME(noqa: C901): Refactor complex dynamic import logic to reduce complexity.
        """Load DSM model directly on GPU for GPU memory snapshot."""
        import sys

        import torch

        print(f"🚀 Loading DSM {self.model_size} {self.variant} model...")

        # Dynamic import of DSM model classes (EXACT COPY from dsm_rl approach)
        import importlib.util
        import os

        dsm_root = "/root/DSM"

        # Load DSM models package
        if "dsm_models" not in sys.modules:
            spec = importlib.util.spec_from_file_location(
                "dsm_models",
                os.path.join(dsm_root, "models", "__init__.py"),
                submodule_search_locations=[os.path.join(dsm_root, "models")],
            )
            dsm_models_pkg = importlib.util.module_from_spec(spec)
            sys.modules["dsm_models"] = dsm_models_pkg
            dsm_models_pkg.__package__ = "dsm_models"
            spec.loader.exec_module(dsm_models_pkg)

        # Now load modeling_dsm as part of the package
        spec = importlib.util.spec_from_file_location(
            "dsm_models.modeling_dsm",
            os.path.join(dsm_root, "models", "modeling_dsm.py"),
            submodule_search_locations=[os.path.join(dsm_root, "models")],
        )
        modeling_dsm = importlib.util.module_from_spec(spec)
        sys.modules["dsm_models.modeling_dsm"] = modeling_dsm
        modeling_dsm.__package__ = "dsm_models"
        spec.loader.exec_module(modeling_dsm)

        # Get the DSM classes
        DSM = modeling_dsm.DSM

        self.torch = torch
        self.device = get_torch_device()

        # Get model directory
        model_dir = get_model_dir(self.model_size, self.variant)
        print(f"📂 Model directory: {model_dir}")

        # Build deterministic HuggingFace snapshot path (like other models do)
        from models.commons.storage.downloads import build_hf_snapshot_path

        # Get HF repo ID and revision from config
        repo_key = (self.model_size, self.variant)
        hf_repo_id = DSM_HF_REPO_MAP.get(repo_key)
        hf_revision = DSM_HF_REVISION_MAP.get(repo_key)

        if not hf_repo_id:
            raise ValueError(
                f"No HuggingFace repository mapped for model size: {self.model_size}, variant: {self.variant}"
            )

        # Build the deterministic snapshot path
        snapshot_path = build_hf_snapshot_path(
            model_dir, hf_repo_id, hf_revision, repo_type="model"
        )
        print(f"📁 Using deterministic HF snapshot path: {snapshot_path}")

        # Convert to absolute Path and verify it exists
        # Files should have been downloaded during image build via setup_download_layer
        from pathlib import Path

        snapshot_path_obj = Path(snapshot_path).resolve()

        if not snapshot_path_obj.exists():
            raise RuntimeError(
                f"Model snapshot path does not exist: {snapshot_path_obj}. "
                f"Model should have been downloaded during image build."
            )

        # Load DSM model from snapshot directory
        # Use local_files_only=True to prevent HuggingFace from trying to validate the path as a repo ID
        # Pass as absolute path string to ensure it's treated as a local directory
        print(f"   📥 Loading model from: {snapshot_path_obj.absolute()}")
        self.model = DSM.from_pretrained(
            str(snapshot_path_obj.absolute()),
            local_files_only=True,
            trust_remote_code=True,
        )
        self.model.to(self.device)
        self.model.eval()

        # Get tokenizer from the model (like dsm_rl does)
        self.tokenizer = self.model.tokenizer
        print(f"✅ Tokenizer loaded: {len(self.tokenizer)} tokens")

        # Get hidden size from model config
        self.hidden_size = self.model.config.hidden_size
        print(f"📊 Hidden size: {self.hidden_size}")

        # Model configuration
        self.max_sequence_len = DSMParams.max_sequence_len

        print(f"✅ DSM {self.model_size} {self.variant} loaded on {self.device}!")

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def generate(self, payload: DSMGenerateRequest) -> DSMGenerateResponse:
        """
        Generate protein sequences using DSM.

        Supports:
        - Unconditional generation (empty input sequence)
        - Masked sequence filling (sequence with <mask> tokens)
        - Conditional generation (sequence prefix)
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

        print(f"🧬 DSM generate called with {len(payload.items)} inputs (seed={seed})")
        print(
            f"Generation params: num_sequences={payload.params.num_sequences}, "
            f"temp={payload.params.temperature}"
        )

        results = []

        with self.torch.no_grad():
            for i, item in enumerate(payload.items):
                print(f"\n📝 Processing input {i+1}/{len(payload.items)}")

                input_seq = item.sequence
                num_sequences = payload.params.num_sequences
                temperature = payload.params.temperature
                max_length = payload.params.max_length or self.max_sequence_len

                # Generate sequences
                if not input_seq or input_seq.strip() == "":
                    # Unconditional generation
                    print("   Mode: Unconditional generation")
                    generated = self._generate_unconditional(
                        payload=payload,
                        num_sequences=num_sequences,
                        max_length=max_length,
                        temperature=temperature,
                        top_k=payload.params.top_k,
                        top_p=payload.params.top_p,
                    )
                elif "<mask>" in input_seq:
                    # Masked sequence filling
                    print(f"   Mode: Mask filling ({input_seq.count('<mask>')} masks)")
                    generated = self._generate_mask_fill(
                        payload=payload,
                        input_sequence=input_seq,
                        num_sequences=num_sequences,
                        temperature=temperature,
                        top_k=payload.params.top_k,
                        top_p=payload.params.top_p,
                    )
                else:
                    # Conditional generation from prefix
                    print(
                        f"   Mode: Conditional generation (prefix length: {len(input_seq)})"
                    )
                    generated = self._generate_conditional(
                        payload=payload,
                        prefix=input_seq,
                        num_sequences=num_sequences,
                        max_length=max_length,
                        temperature=temperature,
                        top_k=payload.params.top_k,
                        top_p=payload.params.top_p,
                    )

                # Calculate log probs and perplexity for each generated sequence
                sequence_results = []
                for seq_dict in generated:
                    seq = seq_dict["sequence"]
                    seq2 = seq_dict.get("sequence2")
                    log_prob, perplexity = self._calculate_log_prob(seq)
                    sequence_results.append(
                        DSMGenerateResponseResult(
                            sequence=seq,
                            log_prob=log_prob,
                            perplexity=perplexity,
                            sequence2=seq2,
                        )
                    )

                results.append(sequence_results)
                print(f"   ✓ Generated {len(generated)} sequences")

        print(f"\n✅ DSM generate completed for {len(results)} inputs")
        return DSMGenerateResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(self, payload: DSMEncodeRequest) -> DSMEncodeResponse:
        """Extract embeddings from protein sequences."""
        print(f"🔢 DSM encode called with {len(payload.items)} sequences")
        include = [option.value for option in payload.params.include]
        print(f"Include options: {include}")

        results = []

        with self.torch.no_grad():
            for i, item in enumerate(payload.items):
                # Tokenize
                encoded = self.tokenizer(
                    item.sequence,
                    return_tensors="pt",
                    add_special_tokens=True,
                    truncation=True,
                    max_length=self.max_sequence_len,
                ).to(self.device)

                # Get model outputs
                outputs = self.model.esm(
                    input_ids=encoded["input_ids"],
                    attention_mask=encoded["attention_mask"],
                )
                hidden_states = outputs.last_hidden_state  # [1, seq_len, hidden_size]

                result_dict = {"sequence_index": i}

                # Mean pooling
                if DSMEncodeIncludeOptions.MEAN in include:
                    # Exclude special tokens (CLS, SEP)
                    attention_mask = encoded["attention_mask"]
                    seq_len = attention_mask.sum().item()
                    # Remove CLS and SEP
                    seq_hidden = hidden_states[0, 1 : seq_len - 1]
                    mean_embedding = seq_hidden.mean(dim=0).cpu().tolist()
                    result_dict["embeddings"] = mean_embedding

                # Per-residue embeddings
                if DSMEncodeIncludeOptions.PER_RESIDUE in include:
                    attention_mask = encoded["attention_mask"]
                    seq_len = attention_mask.sum().item()
                    per_residue = hidden_states[0, 1 : seq_len - 1].cpu().tolist()
                    result_dict["per_residue_embeddings"] = per_residue

                # CLS token
                if DSMEncodeIncludeOptions.CLS in include:
                    cls_embedding = hidden_states[0, 0].cpu().tolist()
                    result_dict["cls_embeddings"] = cls_embedding

                results.append(DSMEncodeResponseResult(**result_dict))

        print(f"✅ DSM encode completed for {len(results)} sequences")
        return DSMEncodeResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def score(self, payload: DSMScoreRequest) -> DSMScoreResponse:
        """Calculate log probabilities for protein sequences."""
        print(f"📊 DSM score called with {len(payload.items)} sequences")

        results = []

        with self.torch.no_grad():
            for item in payload.items:
                log_prob, perplexity = self._calculate_log_prob(item.sequence)

                results.append(
                    DSMScoreResponseResult(
                        log_prob=log_prob,
                        perplexity=perplexity,
                        sequence_length=len(item.sequence),
                    )
                )

        print(f"✅ DSM score completed for {len(results)} sequences")
        return DSMScoreResponse(results=results)

    def _calculate_log_prob(self, sequence: str) -> tuple[float, float]:
        """Calculate log probability and perplexity for a sequence."""
        import math

        # Tokenize
        encoded = self.tokenizer(
            sequence,
            return_tensors="pt",
            add_special_tokens=True,
        ).to(self.device)

        # Get logits
        outputs = self.model.esm(
            input_ids=encoded["input_ids"],
            attention_mask=encoded["attention_mask"],
        )
        hidden_states = outputs.last_hidden_state
        logits = self.model.lm_head(hidden_states)  # [1, seq_len, vocab_size]

        # Compute log probabilities
        log_probs = self.torch.nn.functional.log_softmax(logits, dim=-1)

        # DSM uses a bidirectional ESM-2 backbone (discrete diffusion, not
        # autoregressive), so we sum a position-aligned pseudo-log-likelihood:
        # logits at position i score the token at position i. Skip the BOS
        # (index 0) and EOS (last index) special tokens.
        total_log_prob = 0.0
        seq_len = encoded["input_ids"].shape[1]
        num_residues = max(seq_len - 2, 1)

        for i in range(1, seq_len - 1):
            token_id = encoded["input_ids"][0, i].item()
            token_log_prob = log_probs[0, i, token_id].item()
            total_log_prob += token_log_prob

        avg_log_prob = total_log_prob / num_residues
        perplexity = math.exp(-avg_log_prob)

        return total_log_prob, perplexity

    def _decode_sequences(
        self, generated: "Tensor", input_tokens_batch: "Tensor"
    ) -> list[dict[str, str | None]]:
        """
        Decode generated token sequences into protein sequences.

        For PPI variants, attempts to decode dual sequences (sequence1 and sequence2).
        For base variants, decodes single sequences only.

        Args:
            generated: Generated token tensor from model
            input_tokens_batch: Input token tensor used for generation

        Returns:
            List of dictionaries with 'sequence' and 'sequence2' keys.
            For base variants, 'sequence2' is always None.
            For PPI variants, 'sequence2' may be None if empty or if dual decoding fails.
        """
        sequences = []

        if self.variant == DSMVariants.PPI:
            # For PPI models, use decode_dual_input to separate the two sequences
            try:
                seqa, seqb = self.model.decode_dual_input(
                    generated, input_tokens_batch, "<eos>"
                )
                for i in range(len(seqa)):
                    seq2 = seqb[i] if seqb[i] and len(seqb[i]) > 0 else None
                    sequences.append({"sequence": seqa[i], "sequence2": seq2})
            except (ValueError, IndexError):
                # Fall back to regular decode_output if dual decoding fails
                decoded_sequences = self.model.decode_output(generated)
                for seq in decoded_sequences:
                    sequences.append({"sequence": seq, "sequence2": None})
        else:
            # For base models, use regular decode_output
            decoded_sequences = self.model.decode_output(generated)
            for seq in decoded_sequences:
                sequences.append({"sequence": seq, "sequence2": None})

        return sequences

    def _generate_unconditional(
        self,
        payload: DSMGenerateRequest,
        num_sequences: int,
        max_length: int,
        temperature: float,
        top_k: int = None,
        top_p: float = None,
    ) -> list[str]:
        """Generate unconditional sequences using DSM's generate method."""

        # Note: Generate batch size is limited to 1 in schema (DSMParams.generate_batch_size)
        # so we always use items[0]. If batch size increases, this would need adjustment.
        input_sequence = payload.items[0].sequence

        # Tokenize the input sequence using encode method (returns tensor directly)
        input_tokens = self.tokenizer.encode(
            input_sequence, add_special_tokens=True, return_tensors="pt"
        ).to(self.device)

        # Repeat input for num_sequences and generate in batch
        input_tokens_batch = input_tokens.repeat(num_sequences, 1)

        # Use DSM's mask_diffusion_generate method with proper batching
        generated = self.model.mask_diffusion_generate(
            tokenizer=self.tokenizer,
            input_tokens=input_tokens_batch,
            step_divisor=payload.params.step_divisor,
            temperature=temperature,
            remasking=payload.params.remasking,
            preview=True,  # Always show preview
            slow=False,  # No delay
            return_trajectory=False,  # No trajectory
        )

        return self._decode_sequences(generated, input_tokens_batch)

    def _generate_mask_fill(
        self,
        payload: DSMGenerateRequest,
        input_sequence: str,
        num_sequences: int,
        temperature: float,
        top_k: int = None,
        top_p: float = None,
    ) -> list[str]:
        """Fill masked positions in a sequence."""

        # Tokenize input with masks
        # Tokenize the input sequence using encode method (returns tensor directly)
        input_tokens = self.tokenizer.encode(
            input_sequence, add_special_tokens=True, return_tensors="pt"
        ).to(self.device)

        # Repeat input for num_sequences and generate in batch
        input_tokens_batch = input_tokens.repeat(num_sequences, 1)

        # Generate with proper batching
        generated = self.model.mask_diffusion_generate(
            tokenizer=self.tokenizer,
            input_tokens=input_tokens_batch,
            step_divisor=payload.params.step_divisor,
            temperature=temperature,
            remasking=payload.params.remasking,
            preview=True,  # Always show preview
            slow=False,  # No delay
            return_trajectory=False,  # No trajectory
        )

        return self._decode_sequences(generated, input_tokens_batch)

    def _generate_conditional(
        self,
        payload: DSMGenerateRequest,
        prefix: str,
        num_sequences: int,
        max_length: int,
        temperature: float,
        top_k: int = None,
        top_p: float = None,
    ) -> list[str]:
        """Generate sequences conditioned on a prefix."""

        # For conditional generation, use the prefix as-is
        # User should send the exact sequence they want to condition on
        # Tokenize the input sequence using encode method (returns tensor directly)
        input_tokens = self.tokenizer.encode(
            prefix, add_special_tokens=True, return_tensors="pt"
        ).to(self.device)

        # Repeat input for num_sequences and generate in batch
        input_tokens_batch = input_tokens.repeat(num_sequences, 1)

        # Generate with proper batching
        generated = self.model.mask_diffusion_generate(
            tokenizer=self.tokenizer,
            input_tokens=input_tokens_batch,
            step_divisor=payload.params.step_divisor,
            temperature=temperature,
            remasking=payload.params.remasking,
            preview=True,  # Always show preview
            slow=False,  # No delay
            return_trajectory=False,  # No trajectory
        )

        return self._decode_sequences(generated, input_tokens_batch)


if __name__ == "__main__":
    """
    Usage:
        # Base 650M model
        MODEL_SIZE="650m" VARIANT="base" python models/dsm/app.py

        # PPI 650M model
        MODEL_SIZE="650m" VARIANT="ppi" python models/dsm/app.py

        # 150M model
        MODEL_SIZE="150m" VARIANT="base" python models/dsm/app.py

        # Force deploy to "qa" or "main" environment:
        MODEL_SIZE="650m" VARIANT="base" python models/dsm/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        DSMModel,
        description=f"Run and optionally deploy the {DSMParams.display_name} {model_size} {variant} Modal app.",
    )
