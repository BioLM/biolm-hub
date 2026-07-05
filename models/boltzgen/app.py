import tempfile
import warnings
from pathlib import Path
from typing import Any, Optional

import modal

from models.boltzgen.config import MODEL_FAMILY
from models.boltzgen.download import ARTIFACTS, get_model_dir
from models.boltzgen.helpers import (
    BOLTZGEN_COMMIT,
    BOLTZGEN_REPO_URL,
    convert_binding_types,
    convert_chain_selectors,
    convert_design_specs,
    convert_ss_specs,
)
from models.boltzgen.pipeline import BoltzGenPipelineMixin
from models.boltzgen.schema import (
    BoltzGenConstraint,
    BoltzGenDesignParams,
    BoltzGenDesignRequest,
    BoltzGenDesignRequestItem,
    BoltzGenDesignResponse,
    BoltzGenFileEntity,
    BoltzGenLigandEntity,
    BoltzGenParams,
    BoltzGenProteinEntity,
)
from models.commons.core.decorator import modal_endpoint
from models.commons.core.error import UserError
from models.commons.core.logging import get_logger
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.base import ModelMixinSnap
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    common_requirements,
    runtime_secrets,
)

logger = get_logger(__name__)

# Build Modal container image
# Match the official boltzgen Dockerfile: nvidia/cuda:12.2.2-cudnn8-devel-ubuntu22.04
# Use CUDA base image for proper CUDA support
image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.2.2-cudnn8-devel-ubuntu22.04", add_python="3.12"
    )
    .apt_install(
        "procps",
        "software-properties-common",
        "curl",
        "build-essential",
        "git",
        "cmake",
        "pkg-config",
        "libffi-dev",
        "libssl-dev",
        "libxml2-dev",
        "libxslt-dev",
        "libgl1",
        "libhdf5-dev",
        "libboost-all-dev",
        "libjpeg-dev",  # Required for torchvision image extension
        "libpng-dev",  # Required for torchvision image extension
    )
    .env(
        {
            "PIP_EXTRA_INDEX_URL": "https://download.pytorch.org/whl/cu124",
            "CUDA_HOME": "/usr/local/cuda",
        }
    )
)
# Install Python dependencies
# Install boltzgen, then re-pin torch. boltz[cuda]'s cuequivariance deps
# upgrade torch from 2.6.0 to 2.11.0+cu130 which is incompatible with the
# CUDA 12.2 base image (libnvrtc-builtins.so.13.0 missing).
image = (
    image.uv_pip_install(common_requirements)
    .run_commands(
        f"git clone {BOLTZGEN_REPO_URL} /opt/boltzgen && "
        f"cd /opt/boltzgen && "
        f"git checkout {BOLTZGEN_COMMIT} && "
        f"pip install --no-cache-dir -e ."
    )
    # Re-pin torch after boltzgen install overrode it. boltz[cuda]'s
    # cuequivariance deps pull torch 2.11+cu130, incompatible with CUDA 12.2.
    # Uninstall cuequivariance (ABI-linked to wrong torch) — boltz falls back
    # to standard PyTorch ops via --no_kernels.
    .pip_install("torch==2.6.0", index_url="https://download.pytorch.org/whl/cu124")
    .run_commands(
        "pip uninstall -y cuequivariance_ops_cu12 cuequivariance_ops_torch_cu12 cuequivariance_torch cuequivariance || true"
    )
    .run_commands(
        # Patch 1: Fix IndexError in CIF writer (mmcif.py:441)
        # label_seq_dict index can be out of range when chains are filtered.
        # Use the residue's own res_idx instead of the sequential enumerate index.
        "cd /opt/boltzgen && sed -i"
        " 's/str(label_seq_dict\\[entity_id\\]\\[seq_id - 1\\])/str(res[\"res_idx\"].item() + 1)/'"
        " src/boltzgen/data/write/mmcif.py"
        " && grep -q 'res\\[\"res_idx\"\\].item()' src/boltzgen/data/write/mmcif.py"
        " || (echo 'FATAL: sed patch 1 (mmcif.py) did not apply' && exit 1)",
        # Patch 2: Fix design_mask all-False bug (boltzgen issue #48, fix-48 branch)
        # The exclude handler wrongly zeroed include_mask instead of exclude_mask.
        "cd /opt/boltzgen && sed -i"
        " 's/include_mask\\[c_start:c_end\\] = 0/exclude_mask[c_start:c_end] = 0/'"
        " src/boltzgen/data/parse/schema.py"
        " && grep -q 'exclude_mask\\[c_start:c_end\\] = 0' src/boltzgen/data/parse/schema.py"
        " || (echo 'FATAL: sed patch 2 (schema.py) did not apply' && exit 1)",
    )
    .uv_pip_install(
        "pyyaml==6.0.3",  # Additional dependency — pin for reproducibility
    )
    .workdir("/opt/boltzgen")
    .env(
        {
            "HF_HOME": "/root/.cache/huggingface",
        }
    )
)

# Setup download layer with model weights
# huggingface_hub is listed explicitly: the HF fallback in the download layer
# runs at build time, before the boltzgen runtime layer is installed. Even
# though boltzgen transitively provides huggingface_hub in the runtime image,
# declaring it here ensures the download layer is self-contained.
image = setup_download_layer(
    image,
    base_model_slug=BoltzGenParams.base_model_slug,
    weights_version=BoltzGenParams.weights_version,
    variant_config=None,
    extra_pip_packages=["huggingface_hub==0.26.0"],
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
    enable_memory_snapshot=True,  # Required for ModelMixinSnap
    experimental_options={
        "enable_gpu_snapshot": False
    },  # Disable GPU snapshots for large model
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class BoltzGenModel(BoltzGenPipelineMixin, ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def setup_model(self) -> None:  # noqa: C901
        """Setup BoltzGen model and environment."""
        import sys

        # Suppress torchvision image extension warnings (harmless - boltzgen doesn't use image functionality)
        warnings.filterwarnings(
            "ignore", message="Failed to load image Python extension"
        )

        # Add boltzgen to Python path
        sys.path.insert(0, "/opt/boltzgen/src")

        # Get model directory
        self.model_dir = get_model_dir()

        # Get paths to all checkpoints
        # Checkpoints are in HuggingFace snapshot directories
        self.checkpoints = {}
        for artifact_name, artifact_info in ARTIFACTS.items():
            if artifact_name == "moldir":
                continue  # Skip moldir, handled separately

            artifact_dir = self.model_dir / artifact_name
            filename = artifact_info["filename"]

            # Find the checkpoint in the snapshot directory
            # Structure: {artifact_dir}/models--{repo}/snapshots/{commit}/{filename}
            cache_name = f"models--{artifact_info['repo_id'].replace('/', '--')}"
            snapshots_dir = artifact_dir / cache_name / "snapshots"

            if snapshots_dir.exists():
                # Find the snapshot directory (should be one or use the first one)
                snapshots = list(snapshots_dir.iterdir())
                if snapshots:
                    snapshot_dir = snapshots[0]
                    checkpoint_path = snapshot_dir / filename
                    if checkpoint_path.exists():
                        self.checkpoints[artifact_name] = str(checkpoint_path)
                    else:
                        raise FileNotFoundError(
                            f"Checkpoint file not found: {checkpoint_path}\n"
                            f"Searched in snapshot: {snapshot_dir}"
                        )
                else:
                    raise FileNotFoundError(f"No snapshots found in {snapshots_dir}")
            else:
                raise FileNotFoundError(
                    f"Snapshot directory not found: {snapshots_dir}\n"
                    f"Artifact directory: {artifact_dir}"
                )

        # Extract mols.zip if needed
        # Find mols.zip in the dataset snapshot directory
        moldir_artifact_dir = self.model_dir / "moldir"
        cache_name = f"datasets--{ARTIFACTS['moldir']['repo_id'].replace('/', '--')}"
        snapshots_dir = moldir_artifact_dir / cache_name / "snapshots"

        mols_zip = None
        if snapshots_dir.exists():
            snapshots = list(snapshots_dir.iterdir())
            if snapshots:
                snapshot_dir = snapshots[0]
                mols_zip = snapshot_dir / "mols.zip"

        mols_dir = self.model_dir / "moldir" / "mols"
        if mols_zip and mols_zip.exists() and not mols_dir.exists():
            import zipfile

            logger.info("Extracting mols.zip to %s", mols_dir)
            mols_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(mols_zip, "r") as zip_ref:
                # Validate no path traversal in zip members
                for name in zip_ref.namelist():
                    member_path = (mols_dir / name).resolve()
                    if not str(member_path).startswith(str(mols_dir.resolve())):
                        raise ValueError(f"Zip path traversal detected: {name}")
                zip_ref.extractall(mols_dir)

        # Set moldir path - boltzgen expects the path to the extracted mols directory
        self.moldir = str(mols_dir) if mols_dir.exists() else None
        if not self.moldir:
            # Fallback: try to use the HuggingFace cache location
            if snapshots_dir.exists():
                snapshots = list(snapshots_dir.iterdir())
                if snapshots:
                    # Use the snapshot directory as moldir (boltzgen can handle zips)
                    self.moldir = str(snapshots[0])
                    logger.warning(
                        "Using HuggingFace cache directory as moldir: %s", self.moldir
                    )

        logger.info("BoltzGen model setup complete")
        logger.info("   Model directory: %s", self.model_dir)
        logger.info("   Checkpoints: %s", list(self.checkpoints.keys()))

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def generate(self, payload: BoltzGenDesignRequest) -> BoltzGenDesignResponse:
        """
        Generate protein designs using BoltzGen.

        Provide `items` describing the design target. Each design is returned
        inline in the response as an mmCIF structure with metrics and sequence.
        """
        import sys

        import yaml

        sys.path.insert(0, "/opt/boltzgen/src")

        params = payload.params

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Belt-and-suspenders: BoltzGenDesignRequest.items has max_length=1
            # (batch_size=1), so Pydantic validation always rejects >1 before here.
            if len(payload.items) > 1:
                raise UserError(
                    f"BoltzGen only supports one design item per request, got {len(payload.items)}."
                )
            item = payload.items[0]
            logger.info("BoltzGen generate")

            # Convert Pydantic model to YAML and write to tmp_path
            logger.info("Converting request to YAML format...")
            yaml_spec = self._convert_to_yaml_spec(item, params, tmp_path)
            yaml_file = tmp_path / "design_spec.yaml"
            with open(yaml_file, "w") as f:
                yaml.dump(yaml_spec, f, default_flow_style=False)
            logger.info("YAML spec written to %s", yaml_file)

            # Create output directory
            output_dir = tmp_path / "output"
            output_dir.mkdir()
            logger.info("Output directory created: %s", output_dir)

            return self._run_boltzgen_pipeline(yaml_file, output_dir, params)

    def _convert_to_yaml_spec(
        self,
        item: BoltzGenDesignRequestItem,
        params: BoltzGenDesignParams,
        tmp_path: Path,
    ) -> dict[str, Any]:
        """Convert Pydantic request item to YAML format expected by BoltzGen."""
        yaml_spec: dict[str, Any] = {"entities": []}

        for entity in item.entities:
            if entity.protein:
                yaml_spec["entities"].append(self._convert_protein(entity.protein))
            elif entity.ligand:
                yaml_spec["entities"].append(self._convert_ligand(entity.ligand))
            elif entity.file:
                yaml_spec["entities"].append(self._convert_file(entity.file, tmp_path))
            elif entity.dna:
                yaml_spec["entities"].append({"dna": entity.dna})
            elif entity.rna:
                yaml_spec["entities"].append({"rna": entity.rna})

        if item.constraints:
            yaml_spec["constraints"] = [
                self._convert_constraint(c) for c in item.constraints
            ]

        reset = self._resolve_reset_res_index(item)
        if reset:
            yaml_spec["reset_res_index"] = reset

        return yaml_spec

    # -- entity converters --

    @staticmethod
    def _convert_protein(p: BoltzGenProteinEntity) -> dict[str, Any]:
        spec: dict[str, Any] = {"id": p.id, "sequence": p.sequence}
        if p.cyclic:
            spec["cyclic"] = True
        if p.secondary_structure:
            spec["secondary_structure"] = convert_ss_specs(p.secondary_structure)
        if p.binding_types:
            spec["binding_types"] = convert_binding_types(p.binding_types)
        if p.msa is not None:
            spec["msa"] = p.msa
        return {"protein": spec}

    @staticmethod
    def _convert_ligand(lig: BoltzGenLigandEntity) -> dict[str, Any]:
        spec: dict[str, Any] = {"id": lig.id}
        if lig.ccd:
            spec["ccd"] = lig.ccd
        if lig.smiles:
            spec["smiles"] = lig.smiles
        if lig.binding_types:
            spec["binding_types"] = convert_binding_types(lig.binding_types)
        return {"ligand": spec}

    @staticmethod
    def _convert_file(  # noqa: C901
        f: BoltzGenFileEntity, tmp_path: Path
    ) -> dict[str, Any]:
        # Write structure content to a temp file
        file_ext = ".cif" if f.cif else ".pdb"
        file_content = f.cif or f.pdb
        # validate_file_provided guarantees exactly one of cif/pdb is set.
        assert file_content is not None
        temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=file_ext, delete=False, dir=str(tmp_path)
        )
        temp_file.write(file_content)
        temp_file.close()

        spec: dict[str, Any] = {"path": Path(temp_file.name).name}

        if f.include:
            spec["include"] = convert_chain_selectors(f.include)
        if f.exclude:
            spec["exclude"] = convert_chain_selectors(f.exclude)
        if f.fuse:
            spec["fuse"] = f.fuse
        if f.binding_types:
            spec["binding_types"] = convert_binding_types(f.binding_types)
        if f.design:
            spec["design"] = convert_design_specs(f.design)
        if f.not_design:
            spec["not_design"] = convert_design_specs(f.not_design)
        if f.secondary_structure:
            spec["secondary_structure"] = convert_ss_specs(f.secondary_structure)
        if f.design_insertions:
            spec["design_insertions"] = [
                {"insertion": di.insertion} for di in f.design_insertions
            ]
        if f.structure_groups:
            spec["structure_groups"] = [
                {"group": {**sg.group, "visibility": sg.visibility}}
                for sg in f.structure_groups
            ]
        if f.include_proximity:
            spec["include_proximity"] = f.include_proximity
        if f.use_assembly is not None:
            spec["use_assembly"] = f.use_assembly
        if f.add_cyclization:
            spec["add_cyclization"] = f.add_cyclization
        if f.msa is not None:
            spec["msa"] = f.msa

        return {"file": spec}

    # -- constraint converter --

    @staticmethod
    def _convert_constraint(c: BoltzGenConstraint) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if c.bond:
            d["bond"] = {"atom1": c.bond.atom1, "atom2": c.bond.atom2}
        if c.contact:
            d["contact"] = {
                "token1": c.contact.token1,
                "token2": c.contact.token2,
                "max_distance": c.contact.max_distance,
            }
        if c.pocket:
            pocket: dict[str, Any] = {
                "binder": c.pocket.binder,
                "contacts": c.pocket.contacts,
            }
            if c.pocket.max_distance:
                pocket["max_distance"] = c.pocket.max_distance
            d["pocket"] = pocket
        if c.total_len:
            tl: dict[str, Any] = {}
            if c.total_len.min is not None:
                tl["min"] = c.total_len.min
            if c.total_len.max is not None:
                tl["max"] = c.total_len.max
            d["total_len"] = tl
        return d

    # -- reset_res_index resolution --

    @staticmethod
    def _resolve_reset_res_index(
        item: BoltzGenDesignRequestItem,
    ) -> Optional[list[dict[str, Any]]]:
        """Determine reset_res_index from explicit settings or scaffold redesign heuristic."""
        # 1. Explicit top-level setting
        if item.reset_res_index:
            return [{"chain": {"id": sel.id}} for sel in item.reset_res_index]

        # 2. Explicit per-file-entity setting
        for entity in item.entities:
            if entity.file and entity.file.reset_res_index:
                return [
                    {"chain": {"id": sel.id}} for sel in entity.file.reset_res_index
                ]

        # 3. Auto-infer for single-file scaffold redesign pattern
        if (
            len(item.entities) == 1
            and item.entities[0].file
            and item.entities[0].file.design
        ):
            seen: set[str] = set()
            result: list[dict[str, Any]] = []
            for ds in item.entities[0].file.design:
                if isinstance(ds.chain, str):
                    chain_ids = [ds.chain]
                elif isinstance(ds.chain, list):
                    chain_ids = ds.chain
                else:
                    continue
                for chain_id in chain_ids:
                    if chain_id and chain_id not in seen:
                        result.append({"chain": {"id": chain_id}})
                        seen.add(chain_id)
            return result or None

        return None


if __name__ == "__main__":
    """
    Usage:
        python models/boltzgen/app.py

        # Force deploy to "biolm-hub-dev" or "biolm-hub" environment:
        python models/boltzgen/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        BoltzGenModel,
        description=f"Run and optionally deploy the {BoltzGenParams.display_name} Modal app.",
    )
