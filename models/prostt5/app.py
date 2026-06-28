import os
import re

import modal

from models.commons.core.decorator import modal_endpoint
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
from models.commons.util.environment import (
    parse_variants,
)
from models.prostt5.config import MODEL_FAMILY
from models.prostt5.download import get_model_dir
from models.prostt5.schema import (
    ProstT5Directions,
    ProstT5EncodeRequestAA,
    ProstT5EncodeRequestFold,
    ProstT5EncodeResponse,
    ProstT5EncodeResponseResult,
    ProstT5GenerateRequestAA,
    ProstT5GenerateRequestFold,
    ProstT5GenerateResponse,
    ProstT5GenerateResponseGenerated,
    ProstT5Params,
    ProstT5Types,
)

logger = get_logger(__name__)

variant_config = parse_variants(
    [
        {
            "env_var_name": "MODEL_ACTION",
            "allowed_values": ProstT5Types,
            "default": ProstT5Types.ENCODE,
            # "var_is_required": True,
        },
        {
            "env_var_name": "MODEL_DIRECTION",
            "allowed_values": ProstT5Directions,
            "default": ProstT5Directions.FOLD,
            # "var_is_required": True,
        },
    ]
)

model_action = variant_config["MODEL_ACTION"]
model_direction = variant_config["MODEL_DIRECTION"]


# Build Modal container image
image = modal.Image.from_registry("pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime")
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=ProstT5Params.base_model_slug,
    params_version=ProstT5Params.params_version,
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
        "transformers==4.36.2",
        "sentencepiece==0.2.0",
        "protobuf==5.26.1",
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
class ProstT5Model(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")
    model_action: str = model_action
    model_direction: str = model_direction

    @modal.enter(snap=True)
    def setup_model(self):
        """Load model directly on GPU for GPU memory snapshot with deterministic behavior."""
        import torch
        from transformers import (
            AutoModelForSeq2SeqLM,
            T5EncoderModel,
            T5Tokenizer,
        )

        logger.info("Loading ProstT5 model directly on GPU for GPU memory snapshot...")

        self.torch = torch
        self.model_dir = get_model_dir()

        # Get device and setup for GPU inference
        self.device = get_torch_device()

        # Set the Torch Hub cache directory to the internal model path
        torch.hub.set_dir(self.model_dir)

        logger.info(
            "Loading ProstT5 in mode %s directly on %s from: %s",
            self.model_action,
            self.device,
            self.model_dir,
        )

        # Load tokenizer
        self.tokenizer = T5Tokenizer.from_pretrained(
            self.model_dir, do_lower_case=False, local_files_only=True
        )

        # Load model directly on GPU device
        if self.model_action == ProstT5Types.ENCODE:
            self.model = T5EncoderModel.from_pretrained(
                self.model_dir, local_files_only=True
            )
        else:
            self.model = AutoModelForSeq2SeqLM.from_pretrained(
                self.model_dir, local_files_only=True
            )

        # Move model to GPU device
        self.model = self.model.to(self.device, non_blocking=False)
        self.model.eval()  # Set to evaluation mode

        # Skip half precision when using memory snapshots to avoid CPU compatibility issues
        # Half precision operations are not well supported on CPU where model initially loads
        logger.warning(
            "Skipping half precision with memory snapshots for CPU compatibility"
        )

        logger.info(
            "ProstT5 model loaded directly on %s for GPU memory snapshot!", self.device
        )

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(
        self,
        payload: (
            ProstT5EncodeRequestAA
            if model_direction == ProstT5Directions.AA
            else ProstT5EncodeRequestFold
        ),
    ) -> ProstT5EncodeResponse:
        # Read environment variables at runtime
        current_direction = os.environ["MODEL_DIRECTION"]
        if current_direction != model_direction:
            raise ValueError(
                f"Direction mismatch: expected {model_direction} but got {current_direction}"
            )

        sequences = [item.sequence for item in payload.items]

        embeddings = self.prostt5_compute_embeddings(
            sequences,
            model_direction=current_direction,
        )
        return ProstT5EncodeResponse(results=embeddings)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def generate(
        self,
        payload: (
            ProstT5GenerateRequestAA
            if model_direction == ProstT5Directions.AA
            else ProstT5GenerateRequestFold
        ),
    ) -> ProstT5GenerateResponse:
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

        # Read environment variables at runtime
        current_direction = os.environ["MODEL_DIRECTION"]
        if current_direction != model_direction:
            raise ValueError(
                f"Direction mismatch: expected {model_direction} but got {current_direction}"
            )

        sequences = [item.sequence for item in payload.items]

        # Extract params and exclude 'seed' (already applied above, not needed by prostt5_translate)
        params_dict = payload.params.model_dump()
        params_dict.pop("seed", None)  # Remove seed if present

        translations = self.prostt5_translate(
            sequences,
            model_direction=current_direction,
            **params_dict,
        )
        return translations

    def prostt5_compute_embeddings(  # noqa: C901
        self,
        sequences: list[str],
        model_direction: str = "AA2fold",
    ) -> list[ProstT5EncodeResponseResult]:

        import torch

        # prepare your protein sequences/structures as a list.
        # Amino acid sequences are expected to be upper-case ("PRTEINO" below)
        # while 3Di-sequences need to be lower-case ("strctr" below).

        max_seq_len = len(max(sequences, key=len)) + 1
        # replace all rare/ambiguous amino acids by X (3Di sequences do not have those) and introduce white-space between all sequences (AAs and 3Di)
        sequences = [
            " ".join(list(re.sub(r"[UZOB]", "X", sequence))) for sequence in sequences
        ]

        # The model_direction of the translation is indicated by two special tokens:
        # if you go from AAs to 3Di (or if you want to embed AAs), you need to prepend "<AA2fold>"
        # if you go from 3Di to AAs (or if you want to embed 3Di), you need to prepend "<fold2AA>"
        if model_direction == "fold2AA":  # if we go from 3Di (start/s) to AA (target/t)
            sequences = [
                "<fold2AA>" + " " + s
                # this expects 3Di sequences to be already lower-case
                for s in sequences
            ]

        else:  # if we go from AA (start) to 3Di (target)
            sequences = ["<AA2fold>" + " " + s for s in sequences]
        # tokenize sequences and pad up to the longest sequence in the batch
        ids = self.tokenizer.batch_encode_plus(
            sequences, add_special_tokens=True, padding="longest", return_tensors="pt"
        ).to(self.device)

        with torch.no_grad():
            embedding_repr = self.model(
                ids.input_ids, attention_mask=ids.attention_mask
            )

        # extract residue embeddings for the first ([0,:]) sequence in the batch and remove padded & special tokens, incl. prefix ([0,1:8])
        embs = embedding_repr.last_hidden_state[
            :, 1:max_seq_len
        ]  # shape (seq_len x 1024)

        # if you want to derive a single representation (per-protein embedding) for the whole protein
        embs_per_protein = (
            embs.mean(dim=1).detach().cpu().numpy().tolist()
        )  # shape (1024)
        return [
            ProstT5EncodeResponseResult(mean_representation=embedding)
            for embedding in embs_per_protein
        ]

    def prostt5_translate(  # noqa: C901
        self,
        sequences: list[str],
        top_p: float = 0.95,
        top_k: float = 6,
        temperature: float = 1.2,
        repetition_penalty: float = 1.2,
        num_samples: int = 1,
        num_beams: int = 3,
        model_direction: str = "AA2fold",
    ) -> ProstT5GenerateResponse:
        gen_kwargs = {
            "do_sample": True,
            "top_p": top_p,
            "temperature": temperature,
            "top_k": top_k,
            "repetition_penalty": repetition_penalty,
        }

        import torch

        num_return_sequences = num_samples  # keep ProstT5 internal convention
        # prepare your protein sequences/structures as a list.
        # Amino acid sequences are expected to be upper-case ("PRTEINO" below)
        # while 3Di-sequences need to be lower-case ("strctr" below).

        seq_lens = [len(s) for s in sequences]
        max_len = int(max(seq_lens) + 1)
        min_len = int(min(seq_lens) + 1)

        # replace all rare/ambiguous amino acids by X (3Di sequences do not have those) and introduce white-space between all sequences (AAs and 3Di)
        sequences = [
            " ".join(list(re.sub(r"[UZOB]", "X", sequence))) for sequence in sequences
        ]

        # The model_direction of the translation is indicated by two special tokens:
        # if you go from AAs to 3Di (or if you want to embed AAs), you need to prepend "<AA2fold>"
        # if you go from 3Di to AAs (or if you want to embed 3Di), you need to prepend "<fold2AA>"

        if model_direction == "fold2AA":  # if we go from 3Di (start/s) to AA (target/t)
            # don't generate 3Di or rare/ambig. AAs when outputting AA
            noGood = "acdefghiklmnpqrstvwyXBZ"
            gen_kwargs["early_stopping"] = (
                True  # stop early if end-of-text token is generated
            )

            sequences = [
                "<fold2AA>" + " " + s
                # this expects 3Di sequences to be already lower-case
                for s in sequences
            ]
        else:  # if we go from AA (start) to 3Di (target)
            # don't generate AAs when outputting 3Di
            noGood = "ARNDBCEQZGHILKMFPSTWYVXOU"
            gen_kwargs["num_beams"] = num_beams
            if num_beams > 1:
                gen_kwargs["early_stopping"] = (
                    True  # TODO: UserWarning: `num_beams` is set to 1. However, `early_stopping` is set to `True` -- this flag is only used in beam-based generation modes. You should set `num_beams>1` or unset `early_stopping`.
                )
            sequences = ["<AA2fold>" + " " + s for s in sequences]

        bad_words = self.tokenizer(
            [" ".join(list(noGood))], add_special_tokens=False
        ).input_ids

        # tokenize sequences and pad up to the longest sequence in the batch
        ids = self.tokenizer.batch_encode_plus(
            sequences, add_special_tokens=True, padding="longest", return_tensors="pt"
        ).to(self.device)

        try:
            with torch.no_grad():
                # forward translation tokens
                translations = self.model.generate(
                    ids.input_ids,
                    attention_mask=ids.attention_mask,
                    max_length=max_len,  # max length of generated text
                    min_length=min_len,  # minimum length of the generated text
                    length_penalty=1.0,  # import for correct normalization of scores
                    bad_words_ids=bad_words,  # avoid generation of tokens from other vocabulary
                    num_return_sequences=num_return_sequences,  # return only a single sequence
                    **gen_kwargs,
                )
        except RuntimeError as e:
            # rare cases trigger the following error (seemed to depend on generation config):
            # RuntimeError: probability tensor contains either `inf`, `nan` or element < 0
            logger.warning(
                "RuntimeError during ProstT5 generation "
                "(if OOM, lower num_return_sequences and/or max_batch)",
                exc_info=True,
            )
            raise e

        # Decode and remove white-spaces between tokens
        t_strings = self.tokenizer.batch_decode(translations, skip_special_tokens=True)
        results = []
        for batch_idx, _ in enumerate(
            sequences
        ):  # all individual input sequences in a batch
            sub_results = []
            for seq_idx in range(
                num_return_sequences
            ):  # all sequences generated per individual input sequence

                s_len = seq_lens[batch_idx]
                # offset accounts for multiple sequences generated per input sequence
                batch_seq_idx = (batch_idx * num_return_sequences) + seq_idx
                t_seq = "".join(
                    t_strings[batch_seq_idx].split(" ")
                )  # target sequence (prediction)
                t_len = len(t_seq)

                # this is only triggered rarely and only if processing in batched mode,
                # happens esp. for proteins with L>512 (beyond training length)
                if t_len != s_len:
                    logger.warning("source length=%s vs target length=%s", s_len, t_len)
                    if t_len > s_len:  # truncate if target longer than groundtruth
                        t_seq = t_seq[:s_len]
                    elif s_len < t_len:
                        while t_len < s_len:
                            t_seq += "d"  # append d's in case of too short
                            t_len = len(t_seq)
                sub_results.append(ProstT5GenerateResponseGenerated(sequence=t_seq))
            results.append(sub_results)

        return ProstT5GenerateResponse(results=results)


if __name__ == "__main__":
    """
    Usage:
        MODEL_ACTION=encode MODEL_DIRECTION=fold2AA python models/prostt5/app.py

        # Force deploy to "qa" or "main" environment:
        MODEL_ACTION=encode MODEL_DIRECTION=fold2AA python models/prostt5/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        ProstT5Model,
        description=f"Run and optionally deploy the {ProstT5Params.display_name} {model_action} Modal app.",
    )
