import modal
import numpy as np

from models.biotite.config import MODEL_FAMILY
from models.biotite.schema import (
    BiotiteExtractChainsRequest,
    BiotiteExtractChainsResponse,
    BiotiteExtractChainsResponseResult,
    BiotiteParams,
    BiotiteRMSDRequest,
    BiotiteRMSDResponse,
    BiotiteRMSDResponseResult,
)
from models.commons.core.decorator import modal_endpoint
from models.commons.core.error import ModelExecutionError, ValidationError400
from models.commons.core.logging import get_logger
from models.commons.modal.source import setup_source_layer
from models.commons.model.base import ModelMixinSnap
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
)

logger = get_logger(__name__)

# Define the Docker image with necessary dependencies
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("libopenblas-dev", "git", "wget", "gcc", "g++", "libffi-dev", "procps")
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        "biotite==1.3.0",
        "numpy==2.4.3",
    )
)

# Add model source files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)

# Get app configuration from MODEL_FAMILY
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config()
logger.info("App name: %s", app_name)

# Define the Modal app
app = modal.App(app_name, image=image)


@app.cls(
    image=image,
    secrets=[cloudflare_r2_secret],
    enable_memory_snapshot=True,
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class BiotiteModel(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def setup_model(self):
        from io import StringIO

        import biotite.structure as struc
        import biotite.structure.io.pdb as pdbio

        self.struc = struc
        self.pdbio = pdbio
        self.np = np
        self.StringIO = StringIO

        logger.info("Biotite model loaded successfully")

    def extract_ca_coords(self, chain):
        try:
            ca_atoms = chain[chain.atom_name == "CA"]
            if ca_atoms.array_length() == 0:
                return []
            return ca_atoms.coord
        except Exception as e:
            logger.error("Error extracting Ca coordinates: %s", e)
            return []

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def generate(
        self, payload: BiotiteExtractChainsRequest
    ) -> BiotiteExtractChainsResponse:
        """Extract multiple chains from PDB structures."""
        results = []

        for item in payload.items:
            chain_data = self._extract_chains_from_pdb(item.pdb, item.chain_ids)

            if chain_data is None:
                raise ValidationError400(
                    f"Failed to extract chains {item.chain_ids}: chains not found in PDB structure"
                )

            results.append(
                BiotiteExtractChainsResponseResult(
                    chain_sequences=chain_data["sequences"],
                    chain_pdb_strings=chain_data["pdb_strings"],
                )
            )

        return BiotiteExtractChainsResponse(results=results)

    def _extract_chains_from_pdb(  # noqa: C901
        self, pdb_str: str, chain_ids: list[str]
    ) -> dict | None:
        logger.debug("Extracting chains %s from PDB string.", chain_ids)
        import tempfile

        pdbio = self.pdbio
        pdbf = pdbio.PDBFile.read(self.StringIO(pdb_str))
        structure = pdbf.get_structure(model=1)
        all_chains = set(structure.chain_id)

        # Check if all requested chains exist
        missing_chains = [cid for cid in chain_ids if cid not in all_chains]
        if missing_chains:
            logger.warning("Chains %s not found in PDB structure", missing_chains)
            return None

        chain_sequences = {}
        chain_pdb_strings = {}

        for chain_id in chain_ids:
            chain = structure[structure.chain_id == chain_id]
            if chain.array_length() == 0:
                logger.warning("No atoms found in chain '%s'", chain_id)
                continue

            # Extract sequence
            try:
                # Get unique residue names and their positions
                residue_names = chain.res_name
                residue_numbers = chain.res_id

                # Create sequence by concatenating residue names
                sequence = ""
                current_res_num = None
                for res_name, res_num in zip(
                    residue_names, residue_numbers, strict=False
                ):
                    if res_num != current_res_num:
                        # Convert 3-letter code to 1-letter code
                        aa_code = self._get_amino_acid_code(res_name)
                        if aa_code:
                            sequence += aa_code
                        current_res_num = res_num

                chain_sequences[chain_id] = sequence
                logger.debug(
                    "Chain %s sequence (len %d): %s…",
                    chain_id,
                    len(sequence),
                    sequence[:32],
                )
            except Exception as e:
                logger.warning(
                    "Error extracting sequence for chain %s: %s", chain_id, e
                )
                chain_sequences[chain_id] = ""

            # Extract PDB string
            try:
                chain_pdbf = pdbio.PDBFile()
                chain_pdbf.set_structure(chain)

                with tempfile.NamedTemporaryFile(
                    mode="w+", suffix=".pdb", delete=True
                ) as tmp:
                    chain_pdbf.write(tmp.name)
                    tmp.seek(0)
                    chain_pdb_str = tmp.read()

                # Validate PDB string
                if (
                    chain_pdb_str
                    and len(chain_pdb_str) >= 100
                    and (
                        chain_pdb_str.lstrip().startswith("ATOM")
                        or chain_pdb_str.lstrip().startswith("HEADER")
                    )
                ):
                    chain_pdb_strings[chain_id] = chain_pdb_str
                    logger.info(
                        "Extracted chain '%s' with %d atoms",
                        chain_id,
                        chain.array_length(),
                    )
                else:
                    logger.warning("Invalid PDB string for chain %s", chain_id)
                    chain_pdb_strings[chain_id] = ""
            except Exception as e:
                logger.warning(
                    "Error extracting PDB string for chain %s: %s", chain_id, e
                )
                chain_pdb_strings[chain_id] = ""

        if not chain_sequences and not chain_pdb_strings:
            logger.warning("No valid chains extracted")
            return None

        return {"sequences": chain_sequences, "pdb_strings": chain_pdb_strings}

    def _get_amino_acid_code(self, three_letter_code: str) -> str:
        aa_mapping = {
            "ALA": "A",
            "ARG": "R",
            "ASN": "N",
            "ASP": "D",
            "CYS": "C",
            "GLN": "Q",
            "GLU": "E",
            "GLY": "G",
            "HIS": "H",
            "ILE": "I",
            "LEU": "L",
            "LYS": "K",
            "MET": "M",
            "PHE": "F",
            "PRO": "P",
            "SER": "S",
            "THR": "T",
            "TRP": "W",
            "TYR": "Y",
            "VAL": "V",
            "ASX": "B",
            "GLX": "Z",
            "XAA": "X",
            "XLE": "J",
            "X": "X",
        }
        return aa_mapping.get(three_letter_code.upper(), "X")

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict(self, payload: BiotiteRMSDRequest) -> BiotiteRMSDResponse:
        """Compute RMSD between generated and parent structures."""
        results = []

        for item in payload.items:
            rmsd = self._compute_rmsd_between_structures(
                item.pdb_a, item.pdb_b, item.chain_a, item.chain_b
            )

            results.append(
                BiotiteRMSDResponseResult(
                    rmsd=rmsd,
                )
            )

        return BiotiteRMSDResponse(results=results)

    def _compute_rmsd_between_structures(  # noqa: C901
        self, pdb_a: str, pdb_b: str, chain_a: list[str], chain_b: list[str]
    ) -> float:
        logger.debug("Computing RMSD between structures...")
        try:
            logger.debug("RMSD calculation: chain_a=%s, chain_b=%s", chain_a, chain_b)

            # Validate PDB strings
            if not pdb_a or not pdb_a.strip():
                raise ValidationError400("PDB A is empty or None")
            if not pdb_b or not pdb_b.strip():
                raise ValidationError400("PDB B is empty or None")

            struc = self.struc
            pdbio = self.pdbio
            np = self.np

            # Load structures with error handling
            try:
                struct_a_file = pdbio.PDBFile.read(self.StringIO(pdb_a))
                struct_a = struct_a_file.get_structure(model=1)
            except Exception as e:
                logger.error("Failed to load PDB A: %s", e)
                raise ValidationError400(f"Invalid PDB A structure: {e}") from e

            try:
                struct_b_file = pdbio.PDBFile.read(self.StringIO(pdb_b))
                struct_b = struct_b_file.get_structure(model=1)
            except Exception as e:
                logger.error("Failed to load PDB B: %s", e)
                raise ValidationError400(f"Invalid PDB B structure: {e}") from e

            # Log available chains in both structures
            all_chains_a = set(struct_a.chain_id)
            all_chains_b = set(struct_b.chain_id)
            logger.debug("Available chains in PDB A: %s", all_chains_a)
            logger.debug("Available chains in PDB B: %s", all_chains_b)
            logger.debug("Looking for chains A: %s", chain_a)
            logger.debug("Looking for chains B: %s", chain_b)

            struct_a_coords = []
            struct_b_coords = []

            # Process each chain pair
            for chain_id_a, chain_id_b in zip(chain_a, chain_b, strict=False):
                chain_seg_a = struct_a[struct_a.chain_id == chain_id_a]
                chain_seg_b = struct_b[struct_b.chain_id == chain_id_b]

                logger.debug(
                    "RMSD: chain_a=%s, chain_b=%s, atoms_a=%d, atoms_b=%d",
                    chain_id_a,
                    chain_id_b,
                    chain_seg_a.array_length(),
                    chain_seg_b.array_length(),
                )

                if chain_seg_a.array_length() == 0:
                    logger.warning("No atoms for chain '%s' in PDB A", chain_id_a)
                    continue
                if chain_seg_b.array_length() == 0:
                    logger.warning("No atoms for chain '%s' in PDB B", chain_id_b)
                    continue

                ca_a = self.extract_ca_coords(chain_seg_a)
                ca_b = self.extract_ca_coords(chain_seg_b)

                logger.debug("RMSD: ca_a len=%d, ca_b len=%d", len(ca_a), len(ca_b))

                if len(ca_a) == 0 or len(ca_b) == 0:
                    logger.warning(
                        "No Ca atoms found in chain pair '%s'/'%s'",
                        chain_id_a,
                        chain_id_b,
                    )
                    continue
                if len(ca_a) != len(ca_b):
                    logger.warning(
                        "Length mismatch for chain pair '%s'/'%s': A=%d, B=%d",
                        chain_id_a,
                        chain_id_b,
                        len(ca_a),
                        len(ca_b),
                    )
                    continue

                struct_a_coords.append(ca_a)
                struct_b_coords.append(ca_b)

            if not struct_a_coords or not struct_b_coords:
                raise ValidationError400(
                    "No valid chain pairs found for RMSD calculation"
                )

            # Concatenate all coordinates
            struct_a_coords = np.concatenate(struct_a_coords, axis=0)
            struct_b_coords = np.concatenate(struct_b_coords, axis=0)

            if struct_a_coords.shape != struct_b_coords.shape:
                raise ModelExecutionError("Concatenated coordinate shape mismatch")

            # Compute RMSD
            transform = struc.superimpose(struct_a_coords, struct_b_coords)[1]
            aligned_coords = transform.apply(struct_b_coords)
            rmsd = struc.rmsd(struct_a_coords, aligned_coords)

            logger.debug("RMSD value: %s", rmsd)
            return float(rmsd)

        except Exception as e:
            logger.error("RMSD computation error: %s", e)
            raise


if __name__ == "__main__":
    """
    Usage:
        python models/biotite/app.py

        # Force deploy to "biolm-models-dev" or "biolm-models" environment:
        python models/biotite/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        BiotiteModel,
        description=f"Run and optionally deploy the {BiotiteParams.display_name} Modal app.",
    )
