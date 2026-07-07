from pathlib import Path
from typing import TYPE_CHECKING

import modal

from models.chemberta.config import MODEL_FAMILY, hf_pin_revision, hf_repo_id
from models.chemberta.schema import (
    ChemBERTaEncodeRequest,
    ChemBERTaEncodeResponse,
    ChemBERTaEncodeResponseResult,
    ChemBERTaLogProbRequest,
    ChemBERTaLogProbResponse,
    ChemBERTaLogProbResponseResult,
    ChemBERTaParams,
)
from models.commons.core.decorator import modal_endpoint
from models.commons.core.error import ModelExecutionError
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

if TYPE_CHECKING:
    import torch

logger = get_logger(__name__)

# --- Image build ---
# ChemBERTa is a vanilla RobertaForMaskedLM (no trust_remote_code), so a modern
# transformers is fine. CPU-only: use debian_slim + the CPU torch wheel instead
# of a heavy CUDA base image (mirrors the antifold / mpnn CPU pattern).
base_image = modal.Image.debian_slim(python_version="3.12")
# Include huggingface_hub so the r2_then_hf fallback can import it at build time
# (the download layer runs before the main dependency install below).
image = setup_download_layer(
    base_image,
    base_model_slug=ChemBERTaParams.base_model_slug,
    weights_version=ChemBERTaParams.weights_version,
    variant_config=None,  # this model has no variants
    extra_pip_packages=["huggingface_hub==0.26.0"],
)
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        "torch==2.6.0",
        index_url="https://download.pytorch.org/whl/cpu",
    )
    .uv_pip_install(
        "transformers==4.48.1",
        "tokenizers==0.21.0",
        "safetensors==0.5.3",
        "huggingface_hub==0.26.0",
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
    secrets=runtime_secrets(),
    enable_memory_snapshot=True,  # CPU memory snapshot — no GPU snapshot on a CPU container
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class ChemBERTaModel(ModelMixinSnap):

    @modal.enter(snap=True)
    def setup_model(self) -> None:
        """Load ChemBERTa onto the CPU for the memory snapshot, deterministically."""
        import torch
        from transformers import AutoModelForMaskedLM, AutoTokenizer

        logger.info("Loading ChemBERTa model for memory snapshot...")

        # Deterministic behavior for consistent results (torch model).
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.torch = torch
        self.device = get_torch_device()

        # Resolve the deterministic HuggingFace snapshot path created at build time:
        #   {model_dir}/models--{org}--{name}/snapshots/{revision}/
        from models.chemberta.download import get_model_dir

        model_dir = Path(get_model_dir())
        cache_name = f"models--{hf_repo_id.replace('/', '--')}"
        self.snapshot_path = str(model_dir / cache_name / "snapshots" / hf_pin_revision)
        logger.info("Using HF snapshot path: %s", self.snapshot_path)

        # ChemBERTa uses a standard RobertaForMaskedLM + byte-level BPE tokenizer;
        # no trust_remote_code is required.
        self.model = AutoModelForMaskedLM.from_pretrained(self.snapshot_path)
        self.model = self.model.to(self.device)
        self.model.eval()

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.snapshot_path, use_fast=True
        )

        logger.info("ChemBERTa model loaded on %s for memory snapshot!", self.device)

    def _mean_pooling(
        self,
        last_hidden_state: "torch.Tensor",
        attention_mask: "torch.Tensor",
    ) -> "torch.Tensor":
        """Mean pooling across non-padded tokens.

        last_hidden_state: [B, L, D]; attention_mask: [B, L]; returns [B, D].
        """
        input_mask_expanded = (
            attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
        )
        sum_embeddings = self.torch.sum(last_hidden_state * input_mask_expanded, dim=1)
        sum_mask = self.torch.clamp(input_mask_expanded.sum(dim=1), min=1e-9)
        pooled: torch.Tensor = sum_embeddings / sum_mask
        return pooled

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(self, payload: ChemBERTaEncodeRequest) -> ChemBERTaEncodeResponse:
        """Compute a single mean-pooled embedding vector for each input SMILES.

        The SMILES string is passed to the byte-level BPE tokenizer verbatim
        (RoBERTa char-level tokenization — it is NOT space-joined).
        """
        smiles_list = [item.smiles for item in payload.items]

        tokenized = self.tokenizer(
            smiles_list,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=ChemBERTaParams.max_token_len,
        ).to(self.device)

        with self.torch.no_grad():
            outputs = self.model.base_model(**tokenized)
            last_hidden_state = outputs[0]

        embeddings_tensor = self._mean_pooling(
            last_hidden_state, tokenized["attention_mask"]
        )
        embeddings_list = embeddings_tensor.cpu().tolist()

        results = [
            ChemBERTaEncodeResponseResult(embedding=emb) for emb in embeddings_list
        ]
        return ChemBERTaEncodeResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def log_prob(self, payload: ChemBERTaLogProbRequest) -> ChemBERTaLogProbResponse:
        """Pseudo-log-likelihood of each SMILES under the masked LM.

        For each non-special token position, the token is replaced with <mask>,
        the MLM logits are computed, and the log-softmax probability of the
        original token is summed. This yields a per-SMILES pseudo-log-likelihood
        (summed over byte-level BPE *tokens*, not atoms) — a higher value means
        the molecule's SMILES is more typical under ChemBERTa.
        """
        results = []
        for item in payload.items:
            enc = self.tokenizer(
                item.smiles,
                return_tensors="pt",
                add_special_tokens=True,
                truncation=True,
                max_length=ChemBERTaParams.max_token_len,
            )
            input_ids = enc["input_ids"][0].to(self.device)
            attention_mask = enc["attention_mask"][0].to(self.device)

            # Identify non-special (real) token positions to mask one at a time.
            all_special_ids = set(self.tokenizer.all_special_ids)
            valid_positions = [
                i
                for i in range(len(input_ids))
                if input_ids[i].item() not in all_special_ids
            ]
            if not valid_positions:
                results.append(ChemBERTaLogProbResponseResult(log_prob=0.0))
                continue

            mask_id = self.tokenizer.mask_token_id
            if mask_id is None:
                raise ModelExecutionError("Tokenizer has no <mask> token.")

            valid_positions_tensor = self.torch.tensor(
                valid_positions, device=self.device
            )
            num_valid = len(valid_positions)
            rows = self.torch.arange(num_valid, device=self.device)

            # One masked copy of the sequence per valid position.
            masked_input_ids = input_ids.unsqueeze(0).repeat(num_valid, 1)
            masked_input_ids[rows, valid_positions_tensor] = mask_id
            batch_attention_mask = attention_mask.unsqueeze(0).repeat(num_valid, 1)

            with self.torch.no_grad():
                out = self.model(masked_input_ids, attention_mask=batch_attention_mask)
                logits = out.logits  # [num_valid, L, vocab_size]

            selected_logits = logits[rows, valid_positions_tensor, :]
            log_probs = self.torch.log_softmax(selected_logits, dim=-1)
            original_tokens = input_ids[valid_positions_tensor]
            token_log_probs = log_probs[rows, original_tokens]

            sequence_log_prob = float(token_log_probs.sum().item())
            results.append(ChemBERTaLogProbResponseResult(log_prob=sequence_log_prob))

        return ChemBERTaLogProbResponse(results=results)


if __name__ == "__main__":
    """
    Usage:
        python models/chemberta/app.py

        # Force deploy:
        python models/chemberta/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        ChemBERTaModel,
        description=f"Run and optionally deploy the {ChemBERTaParams.display_name} Modal app.",
    )
