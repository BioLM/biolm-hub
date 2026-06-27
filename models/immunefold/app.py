import os
from pathlib import Path

import modal

from models.commons.model.base import ModelMixinSnap
from models.commons.core.decorator import modal_endpoint
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
    r2_model_store_dir,
)
from models.commons.util.environment import parse_variant
from models.immunefold.config import (
    MODEL_FAMILY,
    immunefold_commit_hash,
    model_config_mapping,
    model_id_mapping,
)
from models.immunefold.download import get_model_dir
from models.immunefold.schema import (
    ImmuneFoldModelTypes,
    ImmuneFoldParams,
    ImmuneFoldPredictRequest,
    ImmuneFoldPredictResponse,
    ImmuneFoldPredictResponseResult,
)

variant_config = parse_variant(
    env_var_name="MODEL_TYPE",
    allowed_values=ImmuneFoldModelTypes,
    default=ImmuneFoldModelTypes.ANTIBODY,
)
model_type = variant_config["MODEL_TYPE"]


# Build Modal container image
image = modal.Image.micromamba(python_version="3.10").env(
    {"_BIOLM_REBUILD_IMAGE_ATTEMPT": "1"}  # increment by 1 to force rebuild
)
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=MODEL_FAMILY.base_model_slug,
    params_version=ImmuneFoldParams.params_version,
    variant_config=variant_config,
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .apt_install(["git", "wget", "gcc", "g++", "libffi-dev"])
    # Use micromamba ONLY for bioconda C tools (fast solve).
    # Everything else via pip — matches the working production env which
    # actually runs torch==2.1.2 + CUDA 12, not the conda env's torch 1.12.
    .micromamba_install(
        "hmmer==3.3.2",
        "hhsuite==3.3.0",
        "kalign2==2.04",
        "anarci",
        channels=["bioconda", "conda-forge"],
    )
    .uv_pip_install(
        [
            "torch==2.1.2",
            "numpy==1.21.2",
            "scipy==1.7.3",
            "biopython==1.79",
            "dm-tree==0.1.6",
            "PyYAML==6.0.1",
            "requests==2.26.0",
            "tqdm==4.62.2",
            "typing-extensions==4.15.0",
            "ml-collections==0.1.1",
            "einops==0.4.1",
            "fairscale==0.4.3",
            "omegaconf==2.3.0",
            "hydra-core==1.3.2",
            "pandas==2.0.3",
            "setuptools==59.5.0",
        ]
    )
    # pytorch_lightning 1.6.0 declares Python <3.10 in metadata but works
    # fine at runtime (proven on production). pip>=24.1 enforces Requires-Python
    # even with --no-deps, so downgrade pip first then install.
    .run_commands(
        "pip install 'pip<24.1'",
        "pip install pytorch_lightning==1.6.0 --no-deps",
    )
    .uv_pip_install(
        common_requirements
    )  # Install after deps so runtime env has redis, modal, pydantic, etc.
    .workdir("/root/models/immunefold")
    .run_commands(
        f"git clone https://github.com/CarbonMatrixLab/immunefold.git  && cd immunefold && git switch --detach {immunefold_commit_hash}"
    )
    .uv_pip_install(["fair-esm==2.0.0"])
    .workdir("/root/models/immunefold/immunefold")
    .run_commands(
        "mkdir /tmp_in",
        "mkdir /tmp_out",
        f"ln -s /{r2_model_store_dir}/{ImmuneFoldParams.base_model_slug}/{ImmuneFoldParams.params_version} /root/models/immunefold/immunefold/params",
        # Copy config to both locations
        "mkdir -p /root/immunefold/config",
        "cp -r /root/models/immunefold/immunefold/config/* /root/immunefold/config/",
        # Fix Hydra config files by adding missing _self_ to defaults list
        """sed -i '/^defaults:/a\\  - _self_' /root/immunefold/config/antibody_structure_prediction.yaml""",
        """sed -i '/^defaults:/a\\  - _self_' /root/immunefold/config/TCR_structure_prediction.yaml""",
        # Also fix the original config files
        """sed -i '/^defaults:/a\\  - _self_' /root/models/immunefold/immunefold/config/antibody_structure_prediction.yaml""",
        """sed -i '/^defaults:/a\\  - _self_' /root/models/immunefold/immunefold/config/TCR_structure_prediction.yaml""",
    )
    .add_local_file(
        "models/immunefold/external/inference.py",
        "/root/models/immunefold/immunefold/inference.py",
        copy=True,
    )
    .add_local_file("models/immunefold/__init__.py", "/root/", copy=True)
)
# Finally, add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)


# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config(**variant_config)
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
class ImmuneFoldModel(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")
    model_type: str = model_type

    @modal.enter(snap=True)
    def setup_model(self):
        """Load model directly on GPU for GPU memory snapshot with deterministic behavior."""
        import logging

        import torch
        from omegaconf import DictConfig

        from models.commons.util.device import get_torch_device
        from models.immunefold.immunefold.inference import load

        print("🚀 Loading ImmuneFold model directly on GPU for GPU memory snapshot...")

        # Set deterministic behavior for consistent results
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.torch = torch
        self.model_dir = get_model_dir()

        # Get device and setup for GPU inference
        self.device = get_torch_device()

        logging.basicConfig(level=logging.INFO)
        self.DictConfig = DictConfig

        # Configure to load directly on GPU
        cfg = self.load_config(
            "immunefold/config",
            model_config_mapping[self.model_type],
            overrides={
                "restore_model_ckpt": f"{get_model_dir()}/{model_id_mapping[self.model_type]}",
                "restore_esm2_model": f"{get_model_dir()}/esm2_t36_3B_UR50D.pt",
                "device": str(self.device),  # Load directly on GPU device
            },
        )
        print(
            f"⏳ Loading ImmuneFold model '{self.model_type}' directly on GPU from: {self.model_dir}"
        )

        # Load model directly on GPU
        self.model = load(cfg)

        # Ensure model is in eval mode
        if hasattr(self.model, "eval"):
            self.model.eval()

        print(
            f"✅ ImmuneFold model '{self.model_type}' loaded directly on {self.device} for GPU memory snapshot!"
        )

    def _pre_process_payload(
        self, payload: ImmuneFoldPredictRequest
    ) -> ImmuneFoldModelTypes:
        request_kind = payload.items[0]._kind  # Just check the first one

        if any(item._kind != self.model_type for item in payload.items) or (
            (
                request_kind == ImmuneFoldModelTypes.ANTIBODY
                and self.model_type != ImmuneFoldModelTypes.ANTIBODY
            )
            or (
                request_kind == ImmuneFoldModelTypes.TCR
                and self.model_type != ImmuneFoldModelTypes.TCR
            )
        ):
            raise ValueError(
                f"Mismatch detected: expected '{self.model_type}' but got '{request_kind}' in request."
            )

        return request_kind

    def _handle_domain_numbering_error(
        self, error: Exception, request_kind: ImmuneFoldModelTypes
    ) -> None:
        """Handle domain numbering errors with appropriate error messages."""
        import traceback

        stack_trace = traceback.format_exc()

        # Check if this is a domain numbering error by examining the stack trace
        is_domain_numbering_error = (
            "domain_numbering is not None" in stack_trace
            or "base_dataset.py" in stack_trace
            or "parser.py" in stack_trace
            or "make_domain" in stack_trace
            or ("assert" in stack_trace and ("domain" in stack_trace))
        )

        if not is_domain_numbering_error:
            # Not a domain numbering error - re-raise as-is
            raise error

        # Domain numbering error - provide specific guidance based on model type
        if request_kind == ImmuneFoldModelTypes.ANTIBODY:
            raise ValueError(
                "Antibody domain detection failed for the provided chains. "
                "ImmuneFold expects full VH/VL variable domains; please supply longer canonical antibody sequences or remove unexpected characters."
            ) from error
        elif request_kind == ImmuneFoldModelTypes.TCR:
            raise ValueError(
                "TCR domain detection failed for input sequences. "
                "This can happen when the input sequences cannot be identified as TCR domains. "
                "Please check your input sequences and contact Support if the issue persists."
            ) from error
        else:
            # Defensive: should not reach here given current model types
            raise ValueError(
                "Domain detection failed for input sequences. "
                "Please check your input sequences and contact Support if the issue persists."
            ) from error

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict(self, payload: ImmuneFoldPredictRequest) -> ImmuneFoldPredictResponse:
        """
        Predicts using the ImmuneFold model.

        Parameters:
        "payload (ImmuneFoldPredictRequest): The request object containing sequences and parameters.

        Returns:
        "ImmuneFoldPredictResponse: The response containing predict results.
        """

        import shutil

        from models.immunefold.immunefold.inference import predict_with_model

        request_kind = self._pre_process_payload(payload)
        path_in = Path("/tmp_in/")
        results = []
        for i, item in enumerate(payload.items):

            os.makedirs("/tmp_in/", exist_ok=True)
            os.makedirs("/tmp_out/", exist_ok=True)

            fasta_path = path_in / f"{i}.fasta"
            data_io = "fasta"

            overrides = {
                "restore_model_ckpt": f"{self.model_dir}/{model_id_mapping[self.model_type]}",
                "restore_esm2_model": f"{self.model_dir}/esm2_t36_3B_UR50D.pt",
                "output_dir": "/tmp_out",
                "test_data": fasta_path,
            }

            if request_kind == ImmuneFoldModelTypes.ANTIBODY:
                fasta_header = "nanobody_H"  # fasta header seems to control pdb output chain labels and presence
                fasta_seq = item.H
                type = "nb"
                if item.L:
                    fasta_header = "antibody_H_L"
                    fasta_seq = item.H + f":{item.L}"
                    type = "ab"

            else:
                fasta_header = "TCR_B_A_P_M"
                fasta_seq = f"{item.B}:{item.A}:{item.P}:{item.M}"
                type = "tcr"
            overrides["type"] = type

            if item.pdb:
                fasta_header = "antibody_H_L_A"
                pdb_path = path_in / f"{i}.pdb"
                with open(pdb_path, "w") as f:
                    f.write(item.pdb)
                data_io = "abag"
                overrides["ag"] = pdb_path
                overrides["fasta"] = fasta_path
                overrides["test_data"] = None
                if payload.params.contact_idx:
                    overrides["contact_idx"] = payload.params.contact_idx

            with open(fasta_path, "w") as f:
                f.write(f">{fasta_header}\n{fasta_seq}")

            overrides["data_io"] = data_io
            cfg = self.load_config(
                "immunefold/config",
                model_config_mapping[self.model_type],
                overrides=overrides,
            )

            try:
                confidence_results = predict_with_model(cfg, self.model)[
                    0
                ]  # batch size = 1
                pdb_str = open(f"/tmp_out/{fasta_header}.pdb").read()
                result = ImmuneFoldPredictResponseResult(
                    **{**confidence_results, "pdb": pdb_str}
                )
                results.append(result)
                shutil.rmtree("/tmp_out")
                shutil.rmtree("/tmp_in")
            except (AssertionError, RuntimeError, ValueError) as e:
                self._handle_domain_numbering_error(e, request_kind)
            except Exception as e:
                print(f"Model call failed with error [{e}]")
                raise e
        return ImmuneFoldPredictResponse(results=results)

    def load_config(self, config_path: str, config_name: str, overrides: dict = None):
        """Load Hydra config, apply overrides (creating missing keys), and return updated config."""
        from types import SimpleNamespace

        from hydra import compose, initialize
        from omegaconf import OmegaConf

        def dict_to_namespace(d):
            """Recursively convert a dictionary to a SimpleNamespace."""
            if isinstance(d, dict):
                return SimpleNamespace(
                    **{k: dict_to_namespace(v) for k, v in d.items()}
                )
            return d

        def namespace_to_dict(ns):
            """Recursively convert a SimpleNamespace back to a dictionary."""
            if isinstance(ns, SimpleNamespace):
                return {k: namespace_to_dict(v) for k, v in vars(ns).items()}
            return ns

        # Load Hydra config - config will be available in both locations
        with initialize(version_base=None, config_path=config_path):
            cfg = compose(config_name=config_name)

        # Convert to SimpleNamespace for flexible modification
        cfg_ns = dict_to_namespace(OmegaConf.to_container(cfg, resolve=True))

        # Apply overrides dynamically
        def set_nested_attr(obj, keys, value):
            """Recursively set attributes in SimpleNamespace."""
            for key in keys[:-1]:
                if not hasattr(obj, key):
                    setattr(obj, key, SimpleNamespace())  # Create missing keys
                obj = getattr(obj, key)
            setattr(obj, keys[-1], value)

        for key, value in (overrides or {}).items():
            keys = key.split(".")  # Support nested keys
            set_nested_attr(cfg_ns, keys, value)

        # Convert back to OmegaConf DictConfig
        return OmegaConf.create(namespace_to_dict(cfg_ns))


if __name__ == "__main__":
    """
    Usage:
        MODEL_TYPE="antibody" python models/immunefold/app.py

        # Force deploy to "qa" or "main" environment:
        MODEL_TYPE="antibody" python models/immunefold/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        ImmuneFoldModel,
        description=f"Run and optionally deploy the {ImmuneFoldParams.display_name} {model_type} Modal app.",
    )
