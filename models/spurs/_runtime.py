from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - used for type hints only
    import torch
    from omegaconf import OmegaConf

from models.commons.core.logging import get_logger
from models.commons.util.device import get_torch_device

logger = get_logger(__name__)

AMINO_ACID_ALPHABET = "ACDEFGHIKLMNPQRSTVWY"

### SPURS Runtime Loader


class SpursRunner:
    def __init__(
        self,
        repo_root: Path,
        weights_root: Path,
        esm2_cache_path: Path,
    ) -> None:
        if str(repo_root) not in sys.path:
            sys.path.append(str(repo_root))

        self._ensure_pytorch_lightning_compat()

        import spurs  # noqa: F401  # pylint: disable=unused-import
        import torch
        from biotite.structure.io import pdb as biotite_pdb
        from omegaconf import OmegaConf
        from spurs.inference import parse_pdb, parse_pdb_for_mutation
        from spurs.models.stability.spurs import SPURS
        from spurs.models.stability.spurs_multi import SPURSMulti
        from spurs.utils import seed_everything
        from spurs.utils.io import load_structure

        self._parse_pdb = parse_pdb
        self._parse_pdb_for_mutation = parse_pdb_for_mutation
        self._SPURS = SPURS
        self._SPURSMulti = SPURSMulti
        self._seed_everything = seed_everything
        self._load_structure = load_structure
        self._torch = torch
        self._OmegaConf = OmegaConf
        self._biotite_pdb = biotite_pdb

        self.device = get_torch_device()
        self.esm2_cache_path = esm2_cache_path
        self._torch.manual_seed(42)
        if self._torch.cuda.is_available():
            self._torch.cuda.manual_seed_all(42)

        self.weights_root = weights_root

        self._initialise_environment()

        self.single_cfg, self.single_model = self._load_model(
            self.weights_root / "spurs", self._SPURS
        )
        self.multi_cfg, self.multi_model = self._load_model(
            self.weights_root / "spurs_multi", self._SPURSMulti
        )

    @staticmethod
    def _ensure_pytorch_lightning_compat() -> None:
        """Add shims for older SPURS imports when lightning changes APIs."""

        try:
            import pytorch_lightning.utilities.imports as pl_imports
        except ModuleNotFoundError:
            return

        # Lightning 1.9 moved LightningLoggerBase; re-create symbol if missing
        try:
            from pytorch_lightning.loggers import (
                LightningLoggerBase,  # type: ignore # noqa: F401
            )
        except ImportError:
            try:
                from pytorch_lightning.loggers.logger import Logger
            except ModuleNotFoundError:
                Logger = None  # type: ignore
            else:
                import pytorch_lightning.loggers as pl_loggers

                pl_loggers.LightningLoggerBase = Logger
                module = sys.modules.get("pytorch_lightning.loggers")
                if module is not None:
                    module.LightningLoggerBase = Logger

        if not hasattr(pl_imports, "_FAIRSCALE_AVAILABLE"):
            module_available = getattr(pl_imports, "_module_available", None)
            if module_available is not None:
                is_available = module_available("fairscale")
            else:
                try:
                    from lightning_utilities.core.imports import module_available
                except ModuleNotFoundError:
                    is_available = False
                else:
                    is_available = module_available("fairscale")

            pl_imports._FAIRSCALE_AVAILABLE = is_available

    def _initialise_environment(self) -> None:
        os.environ.setdefault("HF_HUB_CACHE", str(self.esm2_cache_path))
        os.environ.setdefault("HF_HOME", str(self.esm2_cache_path))
        os.environ.setdefault("TORCH_HOME", str(self.esm2_cache_path))

        torch = self._torch
        torch.hub.set_dir(str(self.esm2_cache_path))

    def _load_model(
        self, model_dir: Path, model_cls
    ) -> tuple[OmegaConf, torch.nn.Module]:
        OmegaConf = self._OmegaConf
        torch = self._torch
        cfg_path = model_dir / ".hydra" / "config.yaml"
        ckpt_path = model_dir / "checkpoints" / "best.ckpt"

        if not cfg_path.exists() or not ckpt_path.exists():
            raise FileNotFoundError(
                f"Missing SPURS checkpoint files under {model_dir}."
            )

        cfg = OmegaConf.load(cfg_path)
        model_cfg = OmegaConf.to_container(cfg.model, resolve=True)
        model_cfg.pop("_target_", None)
        model = model_cls(OmegaConf.create(model_cfg)).to(self.device)

        checkpoint = torch.load(ckpt_path, map_location="cpu")
        state_dict = {
            key[6:]: value
            for key, value in checkpoint["state_dict"].items()
            if key.startswith("model.")
        }
        missing, unexpected = model.load_state_dict(state_dict, strict=False)
        if missing:
            logger.warning("Missing keys during load: %s", missing)
        if unexpected:
            logger.warning("Unexpected keys during load: %s", unexpected)
        model.eval()
        model.to(self.device)
        train_cfg = getattr(cfg, "train", None)
        seed = getattr(train_cfg, "seed", 42) if train_cfg is not None else 42
        self._seed_everything(seed)
        return cfg, model

    def predict(
        self,
        sequence: str,
        structure: str,
        structure_format: str,
        chain_id: str,
        mutations: list[str] | None,
    ) -> dict[str, object]:
        structure_path = self._materialise_structure(
            structure=structure,
            structure_format=structure_format,
            chain_id=chain_id,
        )
        try:
            pdb_name = Path(structure_path).stem
            parsed = self._parse_pdb(
                str(structure_path),
                pdb_name,
                chain_id,
                self.single_cfg,
                device=self.device,
            )
            parsed["seq"] = sequence
            ddg_matrix = self._single_model_forward(parsed)

            if not mutations:
                return {
                    "ddg_value": None,
                    "contributions": None,
                    "ddg_matrix": self._format_ddg_matrix(ddg_matrix, sequence),
                }

            if len(mutations) == 1:
                mutation = mutations[0]
                ddg_value = self._extract_single_mutation(
                    ddg_matrix, mutation, sequence
                )
                return {
                    "ddg_value": ddg_value,
                    "contributions": None,
                    "ddg_matrix": None,
                }

            contributions = {
                mutation: self._extract_single_mutation(ddg_matrix, mutation, sequence)
                for mutation in mutations
            }
            combined = self._multi_model_forward(parsed, mutations)
            return {
                "ddg_value": combined,
                "contributions": contributions,
                "ddg_matrix": None,
            }
        finally:
            if structure_path.exists():
                structure_path.unlink(missing_ok=True)

    def _single_model_forward(self, parsed_batch: dict) -> torch.Tensor:
        torch = self._torch
        with torch.no_grad():
            ddg_matrix = self.single_model(parsed_batch, return_logist=True)
        return ddg_matrix.cpu()

    def _multi_model_forward(self, parsed_batch: dict, mutations: list[str]) -> float:
        torch = self._torch
        mut_ids, append_tensors = self._parse_pdb_for_mutation([mutations])
        parsed_batch = parsed_batch.copy()
        parsed_batch["mut_ids"] = mut_ids.to(self.device, dtype=torch.long)
        parsed_batch["append_tensors"] = append_tensors.to(
            self.device, dtype=torch.long
        )
        with torch.no_grad():
            ddg_values = self.multi_model(parsed_batch)
        return float(ddg_values.squeeze().cpu())

    @staticmethod
    def _mutation_to_indices(mutation: str) -> tuple[int, str, str]:
        wt = mutation[0]
        pos = int(mutation[1:-1])
        mt = mutation[-1]
        return pos, wt, mt

    def _extract_single_mutation(
        self, ddg_matrix: torch.Tensor, mutation: str, sequence: str
    ) -> float:
        pos, wt, mt = self._mutation_to_indices(mutation)
        if sequence[pos - 1] != wt:
            raise ValueError(
                f"Sequence residue mismatch at position {pos}: expected {wt}, found {sequence[pos - 1]}"
            )
        mt_index = AMINO_ACID_ALPHABET.index(mt)
        value = ddg_matrix[pos - 1, mt_index]
        return float(value)

    @staticmethod
    def _format_ddg_matrix(ddg_matrix, sequence: str) -> dict[str, object]:
        return {
            "values": ddg_matrix.tolist(),
            "residue_axis": list(sequence),
            "amino_acid_axis": list(AMINO_ACID_ALPHABET),
        }

    def _materialise_structure(
        self, structure: str, structure_format: str, chain_id: str
    ) -> Path:
        fmt = structure_format.lower()
        if fmt == "cif":
            with tempfile.NamedTemporaryFile(
                mode="w",
                delete=False,
                suffix=".cif",
            ) as handle:
                handle.write(structure)
                raw_path = Path(handle.name)

            atom_array = self._load_structure(str(raw_path), chain=chain_id)
            output_fd, output_name = tempfile.mkstemp(suffix=".pdb")
            output_path = Path(output_name)
            # Close the file descriptor so Biotite can write to the path
            os.close(output_fd)

            pdb_file = self._biotite_pdb.PDBFile()
            pdb_file.set_structure(atom_array)
            pdb_file.write(str(output_path))
            raw_path.unlink(missing_ok=True)
            return output_path

        if fmt == "pdb":
            with tempfile.NamedTemporaryFile(
                mode="w",
                delete=False,
                suffix=".pdb",
            ) as handle:
                handle.write(structure)
                return Path(handle.name)

        raise ValueError(f"Unsupported structure format '{structure_format}'.")
