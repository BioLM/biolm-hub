import os
import shutil
from types import SimpleNamespace

import modal
from pydantic import ValidationError

from models.commons.core.decorator import modal_endpoint
from models.commons.core.error import ValidationError400
from models.commons.core.logging import get_logger
from models.commons.data.validator import aa_unambiguous
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.base import ModelMixinSnap
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
)
from models.commons.util.device import get_torch_device
from models.commons.util.environment import parse_variant
from models.mpnn.config import (
    MODEL_FAMILY,
    MPNNModelCheckpoints,
    mpnn_commit_hash,
    mpnn_schema_map,
)
from models.mpnn.download import get_model_dir
from models.mpnn.schema import (
    AllMPNNGenerateParams,
    MPNNGenerateParams,
    MPNNGenerateRequest,
    MPNNGenerateResponse,
    MPNNGenerateResponseItem,
    MPNNModelTypes,
    MPNNParams,
    MPNNSCGenerateResponseItem,
)

logger = get_logger(__name__)

aa_unambiguous_list = list(aa_unambiguous)
n_aa_unambiguous = len(aa_unambiguous_list)


variant_config = parse_variant(
    env_var_name="MODEL_TYPE",
    allowed_values=MPNNModelTypes,
    default=MPNNModelTypes.PROTEIN,
)
model_type = variant_config["MODEL_TYPE"]


# Build Modal container image
image = modal.Image.micromamba(python_version="3.12")
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=MPNNParams.base_model_slug,
    weights_version=MPNNParams.weights_version,
    variant_config=variant_config,
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .apt_install(["git", "wget", "gcc", "g++", "libffi-dev"])
    # mpnn is CPU-only (micromamba base, not PyTorch container) — must install torch explicitly.
    # ProDy installed separately via run_commands --no-deps (uv rejects its numpy pin).
    .uv_pip_install("torch==2.6.0", index_url="https://download.pytorch.org/whl/cpu")
    .uv_pip_install(
        [
            "biopython==1.84",
            "filelock==3.13.1",
            "fsspec==2024.3.1",
            "Jinja2==3.1.3",
            "MarkupSafe==2.1.5",
            "mpmath==1.3.0",
            "networkx==3.2.1",
            "numpy==1.26.4",
            "pyparsing==3.1.1",
            "scipy==1.12.0",
            "sympy==1.12",
            "typing_extensions==4.10.0",
            "ml-collections==0.1.1",
            "dm-tree==0.1.8",
        ]
    )
    # ProDy --no-deps: its deps (numpy, scipy, biopython) already installed above
    .run_commands("pip install ProDy==2.6.1 --no-deps")
    .workdir("/root/models/mpnn")
    .run_commands(
        f"git clone https://github.com/dauparas/LigandMPNN.git && cd LigandMPNN && git switch --detach {mpnn_commit_hash}"
    )
    .workdir("./LigandMPNN")
    # Patch openfold's deprecated np.int/np.float (removed in numpy 1.24+)
    .run_commands(
        "sed -i 's/np\\.int\\b/np.int64/g; s/np\\.float\\b/np.float64/g' openfold/np/residue_constants.py openfold/np/protein.py",
    )
    .run_commands("mkdir /tmp_pdbs", "mkdir /tmp_out")
    .add_local_file(
        "models/mpnn/util.py", "/root/models/mpnn/LigandMPNN/util.py", copy=True
    )
    .add_local_file("models/mpnn/__init__.py", "/root/", copy=True)
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
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class MPNNModel(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")
    model_type: str = model_type

    @modal.enter(snap=True)
    def load_model(self) -> None:
        """
        Loads the MPNN model on CPU for memory snapshot.
        """
        import torch

        from models.mpnn.util import load_mpnn

        logger.info("📸 Loading MPNN model on CPU for memory snapshot...")

        # Set deterministic behavior for consistent results across CPU loading
        torch.manual_seed(42)

        self.torch = torch
        self.model_dir = get_model_dir()

        torch.hub.set_dir(self.model_dir)
        logger.info(
            "⏳ Loading MPNN %s model on CPU for memory snapshot from: %s",
            self.model_type,
            self.model_dir,
        )

        self.model_checkpoint = MPNNModelCheckpoints[MPNNModelTypes(self.model_type)]

        # HyperMPNN uses the same architecture as ProteinMPNN, so use "protein_mpnn" as model_type
        # The checkpoint file is different, but the architecture is the same
        mpnn_model_type = (
            "protein_mpnn"
            if self.model_type == MPNNModelTypes.HYPER
            else f"{self.model_type}_mpnn"
        )

        # Load model on CPU first
        self.model, self.model_sc, self.atom_context_num = load_mpnn(
            model_type=mpnn_model_type,
            checkpoint_path=self.model_dir / self.model_checkpoint,
            checkpoint_path_sc=self.model_dir
            / MPNNModelCheckpoints[MPNNModelTypes.SIDE_CHAIN],
            device=torch.device("cpu"),  # Force CPU loading for snapshot
            ligand_mpnn_use_side_chain_context=False,
        )

        logger.info(
            "✅ Completed CPU load of MPNN model '%s' for memory snapshot",
            self.model_type,
        )

    @modal.enter(snap=False)
    def setup_model(self) -> None:
        """
        Transfers model to GPU and starts billing.
        """
        # Set deterministic behavior for consistent results across GPU loading
        if self.torch.cuda.is_available():
            self.torch.cuda.manual_seed_all(42)

        # Get device and transfer model to GPU
        self.device = get_torch_device()

        logger.info("Transferring MPNN model to device=%s...", self.device)

        self.model = self.model.to(self.device)
        self.model_sc = self.model_sc.to(self.device)

        logger.info("✅ MPNN model '%s' ready for inference", self.model_type)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def generate(self, payload: MPNNGenerateRequest) -> MPNNGenerateResponse:
        import random
        import time

        import numpy as np

        from models.mpnn.util import infer

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

        # Get the correct, specific Pydantic model for this model_type
        SpecificParamsModel = mpnn_schema_map.get(
            MPNNModelTypes(self.model_type), MPNNGenerateParams  # Fallback to base
        )

        try:
            # Re-validate the input against the specific model
            raw_user_params = payload.params.model_dump(
                exclude_unset=True, exclude_none=True
            )
            filtered_user_params = {
                k: v
                for k, v in raw_user_params.items()
                if k in SpecificParamsModel.model_fields.keys()
            }
            validated_params = SpecificParamsModel.model_validate(filtered_user_params)
        except ValidationError as e:
            raise ValidationError400(
                f"Invalid parameters for model_type '{self.model_type}': {e}"
            ) from e

        # Now construct the fully-validated params for the inference function
        params = AllMPNNGenerateParams().model_dump()
        params.update(validated_params.model_dump(exclude_none=True))

        # Internal/plumbing defaults not exposed in the public schema — set server-side
        params["fasta_seq_separation"] = ":"
        params["file_ending"] = ""
        params["zero_indexed"] = 0
        params["pdb_path"] = None
        params["redesigned_residues_multi"] = None
        params["fixed_residues_multi"] = None
        params["bias_AA_per_residue_multi"] = None
        params["omit_AA_per_residue_multi"] = None
        params["save_stats"] = None
        params["verbose"] = True
        params["ligand_mpnn_use_side_chain_context"] = (
            MPNNParams.ligand_mpnn_use_side_chain_context
        )

        pdbs = [item.pdb for item in payload.items]

        os.makedirs("/tmp_pdbs/", exist_ok=True)
        for i, pdb in enumerate(pdbs):
            with open(f"/tmp_pdbs/{i}.pdb", "w") as f:
                f.write(pdb)

        pdb_path_multi = [f"/tmp_pdbs/{i}.pdb" for i, pdb in enumerate(pdbs)]

        params["pdb_path_multi"] = pdb_path_multi

        # Normalise global_transmembrane_label
        if self.model_type == MPNNModelTypes.GLOBAL_LABEL_MEMBRANE:
            label = params.get("global_transmembrane_label")
            if label == "soluble":
                params["global_transmembrane_label"] = 0
            elif label == "membrane":
                params["global_transmembrane_label"] = 1

        params["out_folder"] = "/tmp_out/"
        # HyperMPNN uses the same architecture as ProteinMPNN
        params["model_type"] = (
            "protein_mpnn"
            if self.model_type == MPNNModelTypes.HYPER
            else f"{self.model_type}_mpnn"
        )

        ns = SimpleNamespace(**params)

        results = infer(
            model=self.model,
            model_sc=self.model_sc,
            atom_context_num=self.atom_context_num,
            args=ns,
        )
        shutil.rmtree("/tmp_pdbs")
        if params["pack_side_chains"]:
            return MPNNGenerateResponse(
                results=[MPNNSCGenerateResponseItem.model_validate(i) for i in results]
            )

        return MPNNGenerateResponse(
            results=[MPNNGenerateResponseItem.model_validate(i) for i in results]
        )


if __name__ == "__main__":
    """
    Usage:
        MODEL_TYPE="protein" python models/mpnn/app.py

        # Deploy to dev (biolm-hub-dev) or prod (biolm-hub) environment:
        MODEL_TYPE="protein" python models/mpnn/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        MPNNModel,
        description=f"Run and optionally deploy the {MPNNParams.display_name} {model_type} Modal app.",
    )
