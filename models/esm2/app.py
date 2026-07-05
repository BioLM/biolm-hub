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
from models.esm2.config import MODEL_FAMILY, model_id_mapping
from models.esm2.download import get_model_dir
from models.esm2.schema import (
    ESM2EncodeRequest,
    ESM2EncodeResponse,
    ESM2EncodeResponseResult,
    ESM2LogProbRequest,
    ESM2LogProbResponse,
    ESM2LogProbResponseResult,
    ESM2ModelSizes,
    ESM2Params,
    ESM2PredictRequest,
    ESM2PredictResponse,
    ESM2PredictResponseResult,
)

logger = get_logger(__name__)

variant_config = parse_variant(
    env_var_name="MODEL_SIZE",
    allowed_values=ESM2ModelSizes,
    default=ESM2ModelSizes.SIZE_650M,
)
model_size = variant_config["MODEL_SIZE"]


# Build Modal container image
image = modal.Image.from_registry("pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime")
# Setup download layer with model weights.
# Include fair-esm so the r2_then_library fallback can import `esm` at build time
# (the download layer runs before the main dependency install below).
image = setup_download_layer(
    image,
    base_model_slug=ESM2Params.base_model_slug,
    weights_version=ESM2Params.weights_version,
    variant_config=variant_config,
    extra_pip_packages=[
        # fair-esm 2.0.1 from GitHub (needed for the fallback download)
        "https://github.com/facebookresearch/esm/archive/2b369911bb5b4b0dda914521b9475cad1656b2ac.zip",
    ],
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        # Install fair-esm 2.0.1 from GitHub ZIP archive (latest version from pip is 2.0.0)
        "https://github.com/facebookresearch/esm/archive/2b369911bb5b4b0dda914521b9475cad1656b2ac.zip",
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
    secrets=runtime_secrets(),
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class ESM2Model(ModelMixinSnap):
    model_size: str = model_size

    @modal.enter(snap=True)
    def setup_model(self) -> None:
        """Load model directly on GPU for GPU memory snapshot with deterministic behavior."""
        import esm
        import torch
        from esm.data import FastaBatchedDataset

        logger.info("Loading ESM2 model directly on GPU for GPU memory snapshot...")

        # Set deterministic behavior for consistent results
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.torch = torch
        self.device = get_torch_device()
        self.model_dir = get_model_dir(self.model_size)

        torch.hub.set_dir(self.model_dir)

        self.FastaBatchedDataset = FastaBatchedDataset

        # Load the model and alphabet directly on GPU
        model_id = model_id_mapping[ESM2ModelSizes(model_size)]
        logger.info("Initiating load of ESM2 model '%s' directly on GPU...", model_id)
        self.model, self.alphabet = esm.pretrained.load_model_and_alphabet_hub(model_id)
        self.model.eval()

        # Move model to GPU
        self.model.to(device=self.device)

        # Get batch converter
        self.batch_converter = self.alphabet.get_batch_converter()

        # Additional attributes
        self.max_sequence_len = ESM2Params.max_sequence_len

        # Set toks_per_batch based on model size
        # Adjusted value for 3B model with L40S GPU
        if model_size == ESM2ModelSizes.SIZE_3B:
            self.toks_per_batch = 1024
        else:
            self.toks_per_batch = 4096

        # Get aa vocab tokens
        self.vocab_tokens = self.alphabet.all_toks[4:-9]

        logger.info(
            "ESM2 model loaded directly on %s for GPU memory snapshot! (toks_per_batch=%s)",
            self.device,
            self.toks_per_batch,
        )

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(self, payload: ESM2EncodeRequest) -> ESM2EncodeResponse:
        """
        Performs encoding using the ESM2 model.

        Parameters:
        - payload (ESM2EncodeRequest): The request object containing sequences and parameters.

        Returns:
        - ESM2EncodeResponse: The response containing encoding results.
        """
        sequences = [item.sequence for item in payload.items]
        repr_layers = payload.params.repr_layers
        include = [option.value for option in payload.params.include]

        try:
            results = self._encode_forward_pass(
                sequences=sequences,
                repr_layers=repr_layers,
                include=include,
                max_sequence_len=self.max_sequence_len,
            )
        except Exception as e:
            logger.error("Model call failed with error [%s]", e, exc_info=True)
            raise

        return ESM2EncodeResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict(self, payload: ESM2PredictRequest) -> ESM2PredictResponse:
        """
        Performs prediction using the ESM2 model.

        Parameters:
        - payload (ESM2PredictRequest): The request object containing sequences.

        Returns:
        - ESM2PredictResponse: The response containing prediction results.
        """
        sequences = [item.sequence for item in payload.items]

        try:
            results = self._predict_forward_pass(
                sequences=sequences,
            )
        except Exception as e:
            logger.error("Model call failed with error [%s]", e, exc_info=True)
            raise

        return ESM2PredictResponse(results=results)

    def _encode_forward_pass(  # noqa: C901
        self,
        sequences: list[str],
        repr_layers: list[int],
        include: list[str],
        max_sequence_len: int,
    ) -> list[ESM2EncodeResponseResult]:
        # FIXME(noqa: C901): Refactor to reduce complexity below the linter's threshold.

        """
        Perform inference on a list of sequences using the ESM2 model.

        Parameters:
        - sequences (List[str]): A list of amino acid sequences to process.
        - repr_layers (List[int]): List of layer indices to extract representations from.
            Valid values are integers from 0 to model.num_layers.
            Negative indices can also be used to refer to layers from the end (-1 refers to the last layer).
        - include (List[str]): List of output types to include in the results.
            Options are:
                - "mean": Mean representation of tokens (default).
                - "per_residue": Per-residue representations.
                - "bos": Beginning-of-sequence representation.
                - "contacts": Predicted inter-residue distances (contacts).
                - "logits": Predicted per-token logits.
                - "attentions": Self-attention weights.
        - max_sequence_len (int): Maximum sequence length. Sequences longer than this will be truncated.

        Returns:
        - List[ESM2EncodeResponseResult]: The list of encoding results.
        """

        ## ESM2 params explained:

        # Use the toks_per_batch set during model initialization
        toks_per_batch = self.toks_per_batch

        # This is maximum length for each sequence; Longer sequences are truncated to this length; Try 1024 or 2048?
        truncation_seq_length = max_sequence_len  # set to 2048

        # extra_toks_per_seq: Used to add buffer tokens per sequence if needed, eg. <cls> and <eos> tokens.
        # Since alphabet.{prepend_bos, append_eos} are true, we set extra_toks_per_seq = 2.
        # ESM2 paper: "We used BOS and EOS tokens to signal the beginning and end of a real
        # protein, to allow the model to separate a full sized protein from a cropped one."
        extra_toks_per_seq = 2

        ## Process inputs
        return_contacts = ("contacts" in include) or ("attentions" in include)

        n_max_layers = self.model.num_layers
        if not all(-(n_max_layers + 1) <= i <= n_max_layers for i in repr_layers):
            raise ValidationError400(
                f"Requested representation layers are out of bounds. Ensure the "
                f"layer indices are between -{n_max_layers + 1} and {n_max_layers}."
            )
        # Convert layer indices to positive indices
        repr_layers = [(i + n_max_layers + 1) % (n_max_layers + 1) for i in repr_layers]

        dataset = self.FastaBatchedDataset(*zip(*enumerate(sequences), strict=True))
        batches = dataset.get_batch_indices(
            toks_per_batch, extra_toks_per_seq=extra_toks_per_seq
        )
        data_loader = self.torch.utils.data.DataLoader(
            dataset,
            collate_fn=self.alphabet.get_batch_converter(truncation_seq_length),
            batch_sampler=batches,
        )

        results = []
        for batch_idx, (
            sequence_labels,
            sequence_strings,
            tokenized_sequences,
        ) in enumerate(data_loader):
            # batch_idx: Index of the current batch within the data_loader iteration.
            # sequence_labels: List/Batch of labels for all sequences in the current batch. These labels uniquely identify each sequence.
            # sequence_strings: List/Batch of raw amino acid sequences in string format, representing a batch of sequences for processing.
            # tokenized_sequences: A tensor containing the tokenized versions of the amino acid sequences in the batch, ready for model input.

            logger.debug(
                "Processing %s of %s batches (%s sequences)",
                batch_idx + 1,
                len(batches),
                tokenized_sequences.size(0),
            )

            tokenized_sequences = tokenized_sequences.to(
                device=self.device, non_blocking=False
            )
            with self.torch.no_grad():
                model_output = self.model(
                    tokenized_sequences,
                    repr_layers=repr_layers,
                    return_contacts=return_contacts,
                )

            ## Process 'logits'
            # Note: has 2 extra tokens <cls>, <eos>; shape: (batch_size, seq_len+2, num_tokens)
            logits = model_output.get("logits", None)
            if logits is not None:
                logits = logits.cpu()

            ## Process 'representations'
            # Note: has 2 extra tokens <cls>, <eos>; shape: (batch_size, seq_len+2, representation_dim)
            embeddings = {
                layer: r.cpu() for layer, r in model_output["representations"].items()
            }

            ## Process 'contacts'
            # Note: does NOT have extra tokens; shape: (batch_size, seq_len, seq_len)
            contacts = model_output.get("contacts", None)
            if contacts is not None:
                contacts = contacts.cpu()

            ## Process 'attentions'
            # Note: has extra tokens; shape: (batch_size, num_layers, num_heads, seq_len+2, seq_len+2)
            attentions = model_output.get("attentions", None)
            if attentions is not None:
                attentions = attentions.cpu()

            for i, label_ in enumerate(sequence_labels):
                result_dict = {"sequence_index": label_}

                # In case sequence was truncated, we only want to return the non-truncated part.
                # HOWEVER, this should always be length of full sequence, since we are using
                # validation enforces sequence length <= max_sequence_len.
                truncate_len = min(truncation_seq_length, len(sequence_strings[i]))

                # Call clone on tensors to ensure tensors are not views into a larger embeddings
                # See https://github.com/pytorch/pytorch/issues/1995
                if "per_residue" in include:
                    result_dict["residue_embeddings"] = [
                        {
                            "layer": layer_n,
                            "embeddings": t[i, 1 : truncate_len + 1]
                            .clone()
                            .tolist(),  # These indices remove <cls> and <eos> tokens
                        }
                        for layer_n, t in embeddings.items()
                    ]
                if "mean" in include:
                    result_dict["embeddings"] = [
                        {
                            "layer": layer_n,
                            "embedding": t[i, 1 : truncate_len + 1]
                            .mean(dim=0)
                            .clone()
                            .tolist(),  # These indices remove <cls> and <eos> tokens
                        }
                        for layer_n, t in embeddings.items()
                    ]
                if "bos" in include:
                    result_dict["bos_embeddings"] = [
                        {
                            "layer": layer_n,
                            "embedding": t[i, 0]
                            .clone()
                            .tolist(),  # Grabs the <cls> token (which is same as <bos> token)
                        }
                        for layer_n, t in embeddings.items()
                    ]
                if "contacts" in include and contacts is not None:
                    result_dict["contacts"] = (
                        contacts[i, :truncate_len, :truncate_len].clone().tolist()
                    )
                if "logits" in include and logits is not None:
                    # The indices below remove <cls> and <eos> tokens
                    # Returns the logits for each token
                    result_dict["logits"] = (
                        logits[i, 1 : truncate_len + 1, 4:-9].clone().tolist()
                    )
                    result_dict["vocab_tokens"] = self.vocab_tokens
                if "attentions" in include and attentions is not None:
                    # Attentions[i] shape: (num_layers, num_heads, seq_len+2, seq_len+2)
                    # .mean(dim=1): average over heads → (num_layers, seq_len+2, seq_len+2)
                    # .mean(dim=1): average over query positions → (num_layers, seq_len+2)
                    # [:, 1:truncate_len+1]: remove BOS/EOS, keep key positions → (num_layers, seq_len)
                    # Result: per-layer mean attention received per residue position
                    avg_attentions = (
                        attentions[i]
                        .clone()
                        .mean(dim=1)
                        .mean(dim=1)[:, 1 : truncate_len + 1]
                    )
                    result_dict["attentions"] = avg_attentions.tolist()

                result = ESM2EncodeResponseResult.model_validate(result_dict)
                results.append(result)

        results = sorted(results, key=lambda x: x.sequence_index)
        return results

    def _predict_forward_pass(
        self,
        sequences: list[str],
    ) -> list[ESM2PredictResponseResult]:
        """
        Perform prediction on sequences with <mask> tokens.

        Parameters:
        - sequences (List[str]): List of amino acid sequences containing <mask> tokens.

        Returns:
        - List[ESM2PredictResponseResult]: The list of prediction results.
        """

        n_max_layers = self.model.num_layers
        batch_converter = self.alphabet.get_batch_converter()

        batch_labels, batch_strs, batch_tokens = batch_converter(
            list(enumerate(sequences))
        )
        batch_lens = (batch_tokens != self.alphabet.padding_idx).sum(1)

        batch_tokens = batch_tokens.to(device=self.device, non_blocking=False)
        with self.torch.no_grad():
            model_output = self.model(
                batch_tokens, repr_layers=[n_max_layers], return_contacts=False
            )

        logits = model_output["logits"].cpu()

        results = []
        for batch_idx, tokens_len in enumerate(batch_lens):
            # [L + 2, num_all_tokens] => [L, aa_vocab_size]
            logit = logits[batch_idx, 1 : tokens_len - 1, 4:-9].clone().tolist()
            sequence_tokens = self.alphabet.tokenize(batch_strs[batch_idx])
            result = ESM2PredictResponseResult(
                logits=logit,
                sequence_tokens=sequence_tokens,
                vocab_tokens=self.vocab_tokens,
            )
            results.append(result)

        return results

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def log_prob(self, payload: ESM2LogProbRequest) -> ESM2LogProbResponse:
        """
        Computes the total log-probability of an unmasked sequence under ESM2,
        using the existing _encode_forward_pass() to extract per-token logits.

        This method performs the following steps:
          1) Call _encode_forward_pass() with include=["logits"] and repr_layers set
             to [self.model.num_layers] so that we get the final-layer logits.
          2) For each sequence, compute log-softmax over the logits at each token position.
          3) For each position corresponding to a canonical residue (as defined in
             self.vocab_tokens), add the log-probability for that residue.
          4) Return a list of total log-probabilities (one per sequence).
        """
        sequences = [item.sequence for item in payload.items]
        encode_results = self._encode_forward_pass(
            sequences=sequences,
            repr_layers=[self.model.num_layers],
            include=["logits"],
            max_sequence_len=self.max_sequence_len,
        )

        canonical_map = {aa: idx for idx, aa in enumerate(self.vocab_tokens)}

        log_prob_sums = []
        for seq, result in zip(sequences, encode_results, strict=False):
            # result.logits is a list-of-lists: shape [L, 20] (with BOS/EOS already removed).
            logits_tensor = self.torch.tensor(result.logits)  # [L, 20]
            # Compute log-softmax along the vocabulary dimension.
            log_probs = self.torch.nn.functional.log_softmax(
                logits_tensor, dim=-1
            )  # [L, 20]

            total_log_prob = 0.0
            # Iterate only over positions present in the logits.
            # (Note: _encode_forward_pass may truncate sequences to max_sequence_len.)
            for pos in range(logits_tensor.shape[0]):
                aa = seq[pos]
                # Only add if the residue is canonical.
                if aa not in canonical_map:
                    continue
                idx = canonical_map[aa]
                total_log_prob += float(log_probs[pos, idx])
            log_prob_sums.append(total_log_prob)

        # Convert to structured response
        results = [ESM2LogProbResponseResult(log_prob=lp) for lp in log_prob_sums]
        return ESM2LogProbResponse(results=results)


if __name__ == "__main__":
    """
    Usage:
        MODEL_SIZE="650m" python models/esm2/app.py

        # Force deploy to "biolm-hub-dev" or "biolm-hub" environment:
        MODEL_SIZE="650m" python models/esm2/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        ESM2Model,
        description=f"Run and optionally deploy the {ESM2Params.display_name} {model_size} Modal app.",
    )
