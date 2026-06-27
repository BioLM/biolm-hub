import os
import tempfile
from pathlib import Path

import modal

from models.antifold.config import MODEL_FAMILY, antifold_commit_hash
from models.antifold.download import get_model_dir
from models.antifold.schema import (
    AntiFoldEncodeIncludeOptions,
    AntiFoldEncodeRequest,
    AntiFoldEncodeResponse,
    AntiFoldGenerateIncludeOptions,
    AntiFoldGenerateRequest,
    AntiFoldGenerateResponse,
    AntiFoldLogProbResponse,
    AntiFoldLogProbResponseResult,
    AntiFoldParams,
    AntiFoldPredictRequest,
    AntiFoldScoreResponse,
)
from models.commons.billing.mixin import BillingMixinSnap
from models.commons.core.decorator import modal_endpoint
from models.commons.data.validator import (
    aa_unambiguous,
)
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
    redis_url_secret,
)
from models.commons.util.device import get_torch_device


def _py(x):
    import numpy as np

    if isinstance(x, np.integer | np.floating):
        return x.item()  # gives native int/float
    return x


# Build Modal container image
# AntiFold is CPU-only (gpu=None) — use debian_slim instead of heavy CUDA base image
image = modal.Image.debian_slim(python_version="3.11")
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=AntiFoldParams.base_model_slug,
    params_version=AntiFoldParams.params_version,
    variant_config=None,  # this model has no variants
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .apt_install("libopenblas-dev", "git", "wget", "gcc", "g++", "libffi-dev")
    .uv_pip_install(
        "torch==2.3.1",
        # CPU-only torch index — much smaller download (~200MB vs ~700MB CUDA)
        index_url="https://download.pytorch.org/whl/cpu",
    )
    .uv_pip_install(
        "torch_geometric==2.4.0",
        "biopython==1.83",
        "biotite==0.38",
        "pygam==0.9.1",
        "numpy==1.26.4",
        "pandas==2.3.3",
        "scipy==1.11.4",
    )
    .run_commands(
        f"git clone https://github.com/oxpig/AntiFold.git && cd AntiFold && git switch --detach {antifold_commit_hash}",
        "mkdir /tmp_pdbs",
        "mkdir /tmp_out",
    )
    .workdir("/AntiFold")
    # Patch AntiFold source files (V2 builder requires add_local_file
    # after all run_commands; package is importable via workdir)
    .add_local_file(
        "models/antifold/external/main.py",
        "/AntiFold/antifold/main.py",
        copy=True,
    )
    .add_local_file(
        "models/antifold/external/antiscripts.py",
        "/AntiFold/antifold/antiscripts.py",
        copy=True,
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
    secrets=[cloudflare_r2_secret, redis_url_secret],
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class AntiFoldModel(BillingMixinSnap):
    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def setup_model(self):
        """Load model directly on GPU for GPU memory snapshot with deterministic behavior."""
        import antifold.antiscripts
        import antifold.main
        import pandas as pd
        import torch

        print("🚀 Loading AntiFold model directly on GPU for GPU memory snapshot...")

        # Set deterministic behavior for consistent results
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.torch = torch
        self.model_dir = get_model_dir()

        # Get device and setup for GPU inference
        self.device = get_torch_device()

        self.pd = pd
        self.antifold_antiscripts = antifold.antiscripts
        self.antifold_main = antifold.main

        print(
            f"⏳ Loading AntiFold model directly on {self.device} from: {self.model_dir}"
        )

        # Load model directly on GPU
        self.model = self.antifold_antiscripts.load_model_modified(
            checkpoint_path=Path(self.model_dir) / "model.pt"
        )
        self.model.eval()
        self.model = self.model.to(self.device, non_blocking=False)

        # Pre-compute amino acid position mapping
        self.aa_to_pos = {aa: i for i, aa in enumerate(list(aa_unambiguous))}

        print(
            f"✅ AntiFold model loaded directly on {self.device} for GPU memory snapshot!"
        )

        # Continue billing through snapshot creation (billing was started in a_billing_enter)
        # This ensures we bill for all time including snapshot creation time
        # The billing thread is non-blocking and will stop naturally when container exits
        # On restore, it's a new container so the old billing thread won't be running

    def _prepare_pdb_input(self, pdb_str: str, params) -> tuple[str, str, str]:
        """
        Creates a temporary pdb file, writes the pdb_str into it, and prepares the input DataFrame.

        Returns:
            input_df (pd.DataFrame): A pandas DataFrame built from the temporary pdb filename and chain parameters.
            pdb_dir (str): The directory where the temporary file is located.
            tmp_pdb (str): The full path to the temporary pdb file.
        """
        # Create a temporary file in the /tmp_pdbs directory with a .pdb suffix.
        tmp_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".pdb", dir="/tmp_pdbs"
        )
        try:
            tmp_file.write(pdb_str)
            tmp_file.close()  # Close the file so that external commands can open it.
            tmp_pdb = tmp_file.name
            # Use the basename (without extension) as identifier.
            _pdb = os.path.splitext(os.path.basename(tmp_pdb))[0]

            # Determine chain: prefer heavy_chain unless a nanobody_chain is provided.
            h_chain_input = (
                params.heavy_chain
                if not params.nanobody_chain
                else params.nanobody_chain
            )

            # Build the input DataFrame.
            input_df = self.pd.DataFrame(
                {
                    "pdb": _pdb,
                    "Hchain": h_chain_input,
                    "Lchain": params.light_chain,
                },
                index=[0],
            )
            if params.antigen_chain:
                input_df.loc[0, "Agchain"] = params.antigen_chain

            pdb_dir = os.path.dirname(tmp_pdb)
            return input_df, pdb_dir, tmp_pdb

        except Exception as e:
            # In case of an error, ensure the temporary file is removed.
            if os.path.exists(tmp_file.name):
                os.remove(tmp_file.name)
            raise e

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(self, payload: AntiFoldEncodeRequest) -> AntiFoldEncodeResponse:
        """
        Performs encoding using the AntiFold model.

        Parameters:
        - payload (AntiFoldEncodeRequest): The request object containing PDB strings and parameters.

        Returns:
        - AntiFoldEncodeResponse: The response containing encoding results.
        """
        results_list = []
        for item in payload.items:
            pdb_str = item.pdb
            # Create temporary file and input DataFrame using the helper
            input_df, pdb_dir, tmp_pdb = self._prepare_pdb_input(
                pdb_str, payload.params
            )
            try:
                # 2) Use the utility function to extract logits and/or embeddings
                logits, embeddings = self.antifold_antiscripts.get_pdbs_logits(
                    model=self.model,
                    pdbs_csv_or_dataframe=input_df,
                    pdb_dir=pdb_dir,
                    out_dir="/tmp_out",
                    batch_size=AntiFoldParams.batch_size,
                    extract_embeddings=True,
                    custom_chain_mode=payload.params._custom_chain_mode,
                    num_threads=0,
                    seed=None,
                    save_flag=False,
                )
                embeddings = embeddings[0]
                results = {}
                if AntiFoldEncodeIncludeOptions.LOGITS in payload.params.include:
                    results["logits"] = logits[0][list(aa_unambiguous)].values.tolist()
                    results["vocab"] = list(aa_unambiguous)
                    results["pdb_posins"] = [
                        int(v) for v in logits[0]["pdb_posins"].tolist()
                    ]
                    results["pdb_chain"] = logits[0]["pdb_chain"].tolist()
                    results["pdb_res"] = logits[0]["pdb_res"].tolist()
                    results["top_res"] = logits[0]["top_res"].tolist()
                    results["perplexity"] = [
                        float(v) for v in logits[0]["perplexity"].tolist()
                    ]
                if AntiFoldEncodeIncludeOptions.MEAN in payload.params.include:
                    results["embeddings"] = embeddings.mean(
                        axis=0
                    ).tolist()  # shape (512,)
                if AntiFoldEncodeIncludeOptions.RESIDUE in payload.params.include:
                    results["residue_embeddings"] = (
                        embeddings.tolist()
                    )  # shape(seq_len, 512)
                results_list.append(results)
            finally:
                if os.path.exists(tmp_pdb):
                    os.remove(tmp_pdb)
        return AntiFoldEncodeResponse(results=results_list)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def generate(self, payload: AntiFoldGenerateRequest) -> AntiFoldGenerateResponse:
        """
        Inverse Fold the input pdb str
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

        results_list = []
        for item in payload.items:
            pdb_str = item.pdb
            # Create temporary file and input DataFrame using the helper
            input_df, pdb_dir, tmp_pdb = self._prepare_pdb_input(
                pdb_str, payload.params
            )
            try:
                # 2) Use the utility function to sample
                results_tmp = self.antifold_main.sample_pdbs(
                    model=self.model,
                    pdbs_csv_or_dataframe=input_df,
                    pdb_dir=pdb_dir,
                    regions_to_mutate=payload.params.regions,
                    out_dir="/tmp_out",
                    sample_n=payload.params.num_seq_per_target,
                    sampling_temp=payload.params.sampling_temp,
                    limit_expected_variation=payload.params.limit_expected_variation,
                    exclude_heavy=payload.params.exclude_heavy,
                    exclude_light=payload.params.exclude_light,
                    batch_size=AntiFoldParams.batch_size,
                    extract_embeddings=False,
                    custom_chain_mode=payload.params._custom_chain_mode,
                    num_threads=0,
                    seed=None,
                    save_flag=False,
                    light_chain=payload.params.light_chain,
                )
                for r in results_tmp:
                    results = {}
                    results["sequences"] = [
                        {k: _py(v) for k, v in s.items()}
                        for s in r["sequences"]["samples"]
                    ]
                    if payload.params.include:
                        if (
                            AntiFoldGenerateIncludeOptions.LOGITS
                            in payload.params.include
                        ):
                            logits = r["logits"]
                            results["logits"] = logits[
                                list(aa_unambiguous)
                            ].values.tolist()
                            results["vocab"] = list(aa_unambiguous)
                            results["pdb_posins"] = [
                                int(v) for v in logits["pdb_posins"].tolist()
                            ]
                            results["pdb_chain"] = logits["pdb_chain"].tolist()
                            results["pdb_res"] = logits["pdb_res"].tolist()
                            results["top_res"] = logits["top_res"].tolist()
                            results["perplexity"] = [
                                float(v) for v in logits["perplexity"].tolist()
                            ]
                        if (
                            AntiFoldGenerateIncludeOptions.LOGPROBS
                            in payload.params.include
                        ):
                            logprobs = r["logprobs"]
                            results["logprobs"] = logprobs[
                                list(aa_unambiguous)
                            ].values.tolist()
                            results["vocab"] = list(aa_unambiguous)
                    results_list.append(results)
            finally:
                if os.path.exists(tmp_pdb):
                    os.remove(tmp_pdb)
        return AntiFoldGenerateResponse(results=results_list)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def score(self, payload: AntiFoldPredictRequest) -> AntiFoldScoreResponse:
        """
        Inverse Fold the input pdb str
        """
        results_list = []
        for item in payload.items:
            pdb_str = item.pdb
            # Create temporary file and input DataFrame using the helper
            input_df, pdb_dir, tmp_pdb = self._prepare_pdb_input(
                pdb_str, payload.params
            )
            try:
                # 2) Use the utility function to sample
                results_tmp = self.antifold_main.sample_pdbs(
                    model=self.model,
                    pdbs_csv_or_dataframe=input_df,
                    regions_to_mutate=["CDR1"],  # placeholder value not actually used
                    pdb_dir=pdb_dir,
                    out_dir="/tmp_out",
                    sample_n=0,
                    batch_size=AntiFoldParams.batch_size,
                    extract_embeddings=False,
                    custom_chain_mode=payload.params._custom_chain_mode,
                    num_threads=0,
                    seed=None,
                    save_flag=False,
                    light_chain=payload.params.light_chain,
                    score=True,
                )
                for r in results_tmp:
                    results_list.append(r["sequences"]["input"])
            finally:
                if os.path.exists(tmp_pdb):
                    os.remove(tmp_pdb)
        return AntiFoldScoreResponse(results=results_list)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict_log_prob(
        self, payload: AntiFoldPredictRequest
    ) -> AntiFoldLogProbResponse:
        """
        Compute the log probability of each input pdb by:
          1. Writing a temporary pdb.
          2. Extracting the logits.
          3. Applying log_softmax over the vocab dimension.
          4. Summing the log-prob for the correct token at each position.
        """
        results_list = []
        for item in payload.items:
            pdb_str = item.pdb
            # Create temporary file and input DataFrame using the helper
            input_df, pdb_dir, tmp_pdb = self._prepare_pdb_input(
                pdb_str, payload.params
            )
            try:
                logits, embeddings = self.antifold_antiscripts.get_pdbs_logits(
                    model=self.model,
                    pdbs_csv_or_dataframe=input_df,
                    pdb_dir=pdb_dir,
                    out_dir="/tmp_out",
                    batch_size=AntiFoldParams.batch_size,
                    extract_embeddings=True,
                    custom_chain_mode=payload.params._custom_chain_mode,
                    num_threads=0,
                    seed=None,
                    save_flag=False,
                )
                seq_lp = 0
                for _i, row in logits[0].iterrows():
                    logits_softmax = self.torch.nn.functional.log_softmax(
                        self.torch.tensor(
                            row[list(aa_unambiguous)].values.astype(float),
                            dtype=self.torch.float32,
                        ),
                        dim=-1,
                    )  # should only be dim 1
                    seq_lp += logits_softmax[self.aa_to_pos[row["pdb_res"]]].item()
                results_list.append(AntiFoldLogProbResponseResult(log_prob=seq_lp))
            finally:
                if os.path.exists(tmp_pdb):
                    os.remove(tmp_pdb)
        return AntiFoldLogProbResponse(results=results_list)


if __name__ == "__main__":
    """
    Usage:
         python models/antifold/app.py

        # Force deploy to "qa" or "main" environment:
        python models/antifold/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        AntiFoldModel,
        description=f"Run and optionally deploy the {AntiFoldParams.display_name} Modal app.",
    )
