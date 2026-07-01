import re
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from models.boltzgen.helpers import DEFAULT_PIPELINE_STEPS
from models.boltzgen.schema import (
    BoltzGenDesignParams,
    BoltzGenDesignResponse,
    BoltzGenDesignResult,
    BoltzGenPipelineStep,
)
from models.commons.core.logging import get_logger

if TYPE_CHECKING:
    import pandas as pd

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Result-reading helpers (pure functions, no Modal dependency)
# ---------------------------------------------------------------------------

# Priority-ordered list of (step_guard, subpath) pairs.  The first entry whose
# guard step was run *and* whose directory exists on disk wins.
_DESIGNS_DIR_CANDIDATES = [
    # (step that must have been requested, subdirectory under output_dir)
    (BoltzGenPipelineStep.FILTERING, "final_ranked_designs/final_{budget}_designs"),
    (BoltzGenPipelineStep.INVERSE_FOLDING, "intermediate_designs_inverse_folded"),
    (None, "intermediate_designs"),  # fallback — no step guard
]

_METRICS_CSV_CANDIDATES = [
    # (step guard, subpath template)
    (
        BoltzGenPipelineStep.FILTERING,
        "final_ranked_designs/final_designs_metrics_{budget}.csv",
    ),
    (BoltzGenPipelineStep.FILTERING, "final_ranked_designs/all_designs_metrics.csv"),
    (None, "intermediate_designs_inverse_folded/aggregate_metrics_analyze.csv"),
]

_SEQUENCE_COLS = ("designed_chain_sequence", "designed_sequence")
_EXCLUDE_METRIC_COLS = {
    "id",
    "file_name",
    "designed_sequence",
    "designed_chain_sequence",
    "sequence",
}


def _find_designs_dir(
    output_dir: Path, steps_run: set[BoltzGenPipelineStep], budget: int
) -> Path:
    """Locate the best available designs directory inside *output_dir*."""
    for step_guard, template in _DESIGNS_DIR_CANDIDATES:
        if step_guard is not None and step_guard not in steps_run:
            continue
        candidate = output_dir / template.format(budget=budget)
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"No output directory found in {output_dir}.\n"
        f"Pipeline may have failed before generating any designs.\n"
        f"Available: {list(output_dir.iterdir())}"
    )


def _load_metrics(
    output_dir: Path, steps_run: set[BoltzGenPipelineStep], budget: int
) -> Optional["pd.DataFrame"]:
    """Load the best available metrics CSV as a pandas DataFrame, or None."""
    if BoltzGenPipelineStep.ANALYSIS not in steps_run:
        return None

    import pandas as pd

    for step_guard, template in _METRICS_CSV_CANDIDATES:
        if step_guard is not None and step_guard not in steps_run:
            continue
        candidate = output_dir / template.format(budget=budget)
        if candidate.exists():
            try:
                df = pd.read_csv(candidate)
                logger.info("Loaded metrics from %s (%s designs)", candidate, len(df))
                return df
            except Exception as e:
                logger.warning("Failed to load metrics CSV: %s", e, exc_info=True)
                return None

    logger.warning("Metrics CSV not found (analysis step may not have produced one)")
    return None


def _strip_rank_prefix(filename: str) -> str:
    """rank001_design_spec_0.cif → design_spec_0.cif"""
    if re.match(r"^rank\d+_", filename):
        return "_".join(filename.split("_")[1:])
    return filename


def _match_metrics_row(
    filename_base: str, metrics_df: "pd.DataFrame"
) -> Optional["pd.Series"]:
    """Find the metrics row matching *filename_base*, trying three strategies."""
    if "file_name" in metrics_df.columns:
        rows = metrics_df[metrics_df["file_name"] == filename_base]
        if len(rows):
            return rows.iloc[0]

        no_ext = filename_base.removesuffix(".cif")
        rows = metrics_df[metrics_df["file_name"].str.removesuffix(".cif") == no_ext]
        if len(rows):
            return rows.iloc[0]

    id_match = re.search(r"(\d+)(?=\.cif$|$)", filename_base)
    if id_match and "id" in metrics_df.columns:
        rows = metrics_df[metrics_df["id"].astype(str) == id_match.group(1)]
        if len(rows):
            return rows.iloc[0]

    return None


def _extract_row_data(
    filename: str, metrics_df: Optional["pd.DataFrame"]
) -> tuple[Optional[dict[str, float]], Optional[str]]:
    """Return (metrics_dict, sequence) for a CIF file from the metrics dataframe."""
    import numpy as np
    import pandas as pd

    if metrics_df is None:
        return None, None

    filename_base = _strip_rank_prefix(filename)
    row = _match_metrics_row(filename_base, metrics_df)
    if row is None:
        return None, None

    # Extract sequence
    sequence = None
    for col in _SEQUENCE_COLS:
        if col in metrics_df.columns:
            val = row.get(col)
            if val is not None and not pd.isna(val):
                sequence = val
                break

    # Extract numeric metrics
    metrics_dict = {
        col: float(row[col])
        for col in metrics_df.columns
        if col not in _EXCLUDE_METRIC_COLS
        and pd.notna(row[col])
        and isinstance(row[col], int | float | np.integer | np.floating)
    }

    return metrics_dict, sequence


class BoltzGenPipelineMixin:
    """Plain Python mixin for BoltzGen pipeline logic — usable without Modal.

    Contains the pipeline methods (configure, execute, read results) that are
    independent of the Modal Cls wrapper. Pipeline orchestration is tested via
    real Modal integration tests, not mocked unit tests.
    """

    # Set by the concrete Modal model class (see BoltzGenModel.setup_model);
    # declared here so this mixin type-checks the attribute accesses below.
    checkpoints: dict[str, str]
    moldir: Optional[str]

    @staticmethod
    def _optional_configure_flags(params: BoltzGenDesignParams) -> list[str]:
        """Build optional CLI flags for ``boltzgen configure`` from *params*.

        Covers design-phase tuning, inverse-folding options, and
        filtering/ranking parameters.
        """
        flags: list[str] = []

        # Design / inverse-folding tuning
        _optional_flag = BoltzGenPipelineMixin._append_optional_flag
        _optional_flag(flags, "--diffusion_batch_size", params.diffusion_batch_size)
        _optional_flag(flags, "--step_scale", params.step_scale)
        _optional_flag(flags, "--noise_scale", params.noise_scale)
        # inverse_fold_num_sequences is a non-Optional int (default=1), so only
        # forward it when the user explicitly set a value other than the default.
        if params.inverse_fold_num_sequences != 1:
            flags.extend(
                ["--inverse_fold_num_sequences", str(params.inverse_fold_num_sequences)]
            )
        _optional_flag(flags, "--inverse_fold_avoid", params.inverse_fold_avoid)

        # Filtering / ranking params (meaningful when filtering step runs)
        _optional_flag(
            flags, "--refolding_rmsd_threshold", params.refolding_rmsd_threshold
        )
        _optional_flag(flags, "--alpha", params.alpha)
        if params.filter_biased is not None:
            flags.extend(["--filter_biased", str(params.filter_biased).lower()])
        if params.additional_filters:
            flags.extend(["--additional_filters"] + params.additional_filters)
        if params.metrics_override:
            import json

            flags.extend(["--metrics_override", json.dumps(params.metrics_override)])
        return flags

    @staticmethod
    def _append_optional_flag(
        flags: list[str], name: str, value: Optional[Union[int, float, str]]
    ) -> None:
        """Append ``[name, str(value)]`` to *flags* if *value* is truthy/not-None."""
        if value is not None:
            flags.extend([name, str(value)])

    def _run_configure(
        self, yaml_file: Path, output_dir: Path, params: BoltzGenDesignParams
    ) -> None:
        """Run `boltzgen configure` to write per-step YAML configs into output_dir.

        Always passes --reuse so skip_existing=True is baked into every step config,
        making the run safe to re-execute without duplicating completed work.
        """
        import subprocess

        steps_to_run = params.steps if params.steps else DEFAULT_PIPELINE_STEPS

        cmd = [
            "boltzgen",
            "configure",
            str(yaml_file),
            "--output",
            str(output_dir),
            "--protocol",
            params.protocol.value,
            "--num_designs",
            str(params.num_designs),
            "--reuse",  # bakes data.skip_existing=True into all step configs
            "--use_kernels",
            "false",  # cuequivariance uninstalled (ABI mismatch with pinned torch)
        ]

        if BoltzGenPipelineStep.FILTERING in steps_to_run:
            cmd.extend(["--budget", str(params.budget)])

        if params.steps:
            cmd.extend(["--steps"] + [s.value for s in params.steps])

        cmd.extend(self._optional_configure_flags(params))

        cmd.extend(
            [
                "--design_checkpoints",
                self.checkpoints["design-diverse"],
                self.checkpoints["design-adherence"],
            ]
        )
        cmd.extend(["--inverse_fold_checkpoint", self.checkpoints["inverse-fold"]])
        cmd.extend(["--folding_checkpoint", self.checkpoints["folding"]])
        cmd.extend(["--affinity_checkpoint", self.checkpoints["affinity"]])

        if self.moldir:
            cmd.extend(["--moldir", self.moldir])

        logger.info("Running boltzgen configure...")
        logger.info("Command: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            cwd="/opt/boltzgen",
            capture_output=True,
            text=True,
        )
        logger.debug("Configure STDOUT: %s", result.stdout)
        if result.returncode != 0:
            raise RuntimeError(
                f"boltzgen configure failed (rc={result.returncode})\n"
                f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
            )
        logger.info("Configure complete")

    def _run_execute(self, output_dir: Path) -> None:
        """Run all configured pipeline steps via a single `boltzgen execute` call.

        The steps to run are determined by the ``steps.yaml`` manifest written
        by ``boltzgen configure``.  With ``--reuse`` baked in, any step whose
        output files already exist is automatically skipped.

        Streams stdout/stderr live so step progress is visible in Modal logs.
        """
        import subprocess

        cmd = ["boltzgen", "execute", str(output_dir)]

        logger.info("=" * 80)
        logger.info("Executing pipeline: %s", " ".join(cmd))
        logger.info("=" * 80)

        process = subprocess.Popen(
            cmd,
            cwd="/opt/boltzgen",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None  # guaranteed by stdout=subprocess.PIPE

        output_lines = []
        try:
            for line in process.stdout:
                logger.info("%s", line.rstrip())
                output_lines.append(line)
        finally:
            process.stdout.close()
            process.wait()

        logger.info("Return code: %s", process.returncode)
        logger.info("=" * 80)

        if process.returncode != 0:
            output_text = "".join(output_lines)
            raise RuntimeError(
                f"boltzgen execute failed (rc={process.returncode})\n"
                f"OUTPUT:\n{output_text}"
            )
        logger.info("Pipeline execution complete")

    def _run_boltzgen_pipeline(
        self,
        yaml_file: Path,
        output_dir: Path,
        params: BoltzGenDesignParams,
    ) -> BoltzGenDesignResponse:
        """Configure and execute the BoltzGen pipeline.

        Runs ``boltzgen configure`` once to write per-step YAML configs, then a
        single ``boltzgen execute`` call that runs all configured steps.  Each
        design is read off disk and returned inline in the response.
        """
        steps_requested = params.steps if params.steps else DEFAULT_PIPELINE_STEPS
        requested_step_values = [s.value for s in steps_requested]

        logger.info("Pipeline steps requested: %s", requested_step_values)

        # (Re-)generate per-step config YAMLs. Safe to run on existing output_dir —
        # boltzgen configure renames any previous config/ dir to previous-config-N.
        self._run_configure(yaml_file, output_dir, params)

        self._run_execute(output_dir)

        # Read and return results
        results = self._read_results(output_dir, params)

        logger.info("Successfully read %s design(s)", len(results))
        return BoltzGenDesignResponse(results=results)

    def _read_results(
        self, output_dir: Path, params: BoltzGenDesignParams
    ) -> list[BoltzGenDesignResult]:
        """Read CIF files and metrics from boltzgen output directories."""
        steps_run = set(params.steps if params.steps else DEFAULT_PIPELINE_STEPS)

        designs_dir = _find_designs_dir(output_dir, steps_run, params.budget)
        metrics_df = _load_metrics(output_dir, steps_run, params.budget)

        cif_files = sorted(designs_dir.glob("*.cif"))
        # Exclude the input spec if designs_dir happens to be the root output dir
        cif_files = [
            f
            for f in cif_files
            if not (f.name == "design_spec.cif" and designs_dir == output_dir)
        ]
        if not cif_files:
            raise FileNotFoundError(
                f"No CIF files found in {designs_dir}.\n"
                "Pipeline completed but no design files were generated."
            )
        logger.info("Found %s design CIF files in %s", len(cif_files), designs_dir)

        from models.boltzgen.helpers import extract_sequence_from_cif

        results = []
        for cif_file in cif_files:
            cif_content = cif_file.read_text()
            metrics_dict, sequence = _extract_row_data(cif_file.name, metrics_df)

            # Fallback: extract sequence from CIF when metrics CSV has none
            if not sequence:
                sequence = extract_sequence_from_cif(cif_content)

            results.append(
                BoltzGenDesignResult(
                    cif=cif_content, metrics=metrics_dict, sequence=sequence
                )
            )

        if not results:
            raise RuntimeError(f"No design results processed from {designs_dir}")

        return results
