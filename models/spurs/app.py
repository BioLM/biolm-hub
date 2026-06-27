import os
from pathlib import Path

import modal

from models.commons.billing.mixin import BillingMixinSnap
from models.commons.core.decorator import modal_endpoint
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.config import biolm_model_class
from models.commons.storage.downloads import (
    build_hf_snapshot_path,
)
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
    redis_url_secret,
)
from models.esm2.download import get_model_dir as get_esm2_model_dir
from models.esm2.schema import ESM2ModelSizes, ESM2Params
from models.spurs._runtime import SpursRunner
from models.spurs.config import (
    HF_REPO_ID,
    HF_REVISION,
    MODEL_FAMILY,
    SPURS_COMMIT,
    SPURS_REPO_URL,
)
from models.spurs.download import get_model_dir
from models.spurs.schema import (
    SpursParams,
    SpursPredictRequest,
    SpursPredictResponse,
    SpursPredictResponseResult,
)
from models.spurs.util import (
    calculate_mutations,
)

# Build Modal container image
# Pinned: hydra dataclass bug on Python 3.12
image = modal.Image.from_registry("pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime")
# Setup download layer with ESM2 weights (needed for cached embeddings)
image = setup_download_layer(
    image,
    base_model_slug=ESM2Params.base_model_slug,
    params_version=ESM2Params.params_version,
    variant_config={"MODEL_SIZE": ESM2ModelSizes.SIZE_650M},
)
# Setup download layer with SPURS checkpoints
image = setup_download_layer(
    image,
    base_model_slug=MODEL_FAMILY.base_model_slug,
    params_version=SpursParams.params_version,
    extra_pip_packages=["huggingface_hub==0.24.6"],
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .apt_install("git", "build-essential")  # Tools + compilers
    .uv_pip_install(
        "numpy<2",  # Pin numpy to 1.x for compatibility
        "omegaconf==2.3.0",
        "hydra-core==1.2.0",
        "pytorch-lightning==1.9.5",  # Last stable 1.x release
        "torchmetrics>=0.9.3,<1.0",  # Compatible with pytorch-lightning 1.9
        "biotite==0.38.0",
        "lmdb==1.6.2",
        "atom3d==0.2.6",
        "huggingface_hub==0.24.6",
        "https://github.com/facebookresearch/esm/archive/2b369911bb5b4b0dda914521b9475cad1656b2ac.zip",
    )
    .run_commands(
        f"git clone {SPURS_REPO_URL} /opt/spurs && cd /opt/spurs && git switch --detach {SPURS_COMMIT}"
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
class SpursModel(BillingMixinSnap):
    app_username: str = modal.parameter(default="default_user")

    """
    SpursModel class offers this method:
     - predict() => computes ΔΔG values for protein mutations
    """

    @modal.enter(snap=True)
    def setup_model(self):
        """Load SPURS model directly for GPU memory snapshot with deterministic behavior."""
        import torch

        print("🚀 Loading SPURS model directly for GPU memory snapshot...")

        # Set deterministic behavior for consistent results
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.torch = torch

        # Get device and setup for GPU inference
        from models.commons.util.device import get_torch_device

        self.device = get_torch_device()

        weights_base = get_model_dir()
        self.weights_root = build_hf_snapshot_path(
            weights_base, HF_REPO_ID, HF_REVISION
        )
        self.esm2_cache = get_esm2_model_dir(ESM2ModelSizes.SIZE_650M)
        repo_path = Path(os.environ.get("SPURS_REPO_PATH", "/opt/spurs"))

        if not repo_path.exists():
            raise FileNotFoundError(
                "SPURS repository not found. Set SPURS_REPO_PATH to a valid clone."
            )

        print(f"📂 Using SPURS repository: {repo_path}")
        print(f"📂 SPURS weight base directory: {weights_base}")
        print(f"📦 SPURS snapshot directory: {self.weights_root}")
        print(f"📂 Using ESM2 cache: {self.esm2_cache}")

        self.runner = SpursRunner(
            repo_root=repo_path,
            weights_root=self.weights_root,
            esm2_cache_path=self.esm2_cache,
        )

        print(
            f"✅ SPURS model loaded directly on {self.device} for GPU memory snapshot!"
        )

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict(  # noqa: C901
        self, payload: SpursPredictRequest
    ) -> SpursPredictResponse:
        """
        Predict ΔΔG values for the supplied mutations.

        For each input item containing sequence, structure, and mutations,
        returns the predicted change in free energy (ΔΔG) in kcal/mol.
        For multiple mutations, also returns per-mutation contributions.
        """
        print(f"🧬 Predicting ΔΔG for {len(payload.items)} items...")

        results = []
        auto_calculated_items = []  # Track which items had auto-calculated mutations

        for i, item in enumerate(payload.items):
            # Determine mutations to use and the sequence to pass to SPURS
            mutations = item.mutations
            sequence_for_spurs = (
                item.sequence
            )  # Default: use input sequence (wild-type)
            calculated_from_variant = False  # Track if mutations were auto-calculated

            # If variant_sequence provided, calculate mutations automatically
            if item.variant_sequence and not item.return_full_dms:
                print(
                    f"  Processing item {i+1}/{len(payload.items)}: auto-calculating mutations from variant_sequence"
                )
                print(
                    f"    Wild-type sequence:  {item.sequence[:50]}{'...' if len(item.sequence) > 50 else ''}"
                )
                print(
                    f"    Variant sequence:    {item.variant_sequence[:50]}{'...' if len(item.variant_sequence) > 50 else ''}"
                )

                # Calculate mutations: wild-type (sequence) -> variant (variant_sequence)
                mutations = calculate_mutations(item.sequence, item.variant_sequence)
                calculated_from_variant = True
                auto_calculated_items.append(i)

                # Pass the wild-type sequence to SPURS (mutations reference WT residues)
                sequence_for_spurs = item.sequence

                if not mutations:
                    print(
                        "    ⚠️  No mutations detected - wild-type and variant sequences are identical"
                    )
                else:
                    print(
                        f"    ✓ Calculated {len(mutations)} mutation(s): {', '.join(mutations)}"
                    )

            mutation_count = len(mutations) if mutations else 0
            if mutation_count:
                if not calculated_from_variant:
                    print(
                        f"  Processing item {i+1}/{len(payload.items)}: {mutation_count} manual mutation(s)"
                    )
                    print(f"    Mutations: {', '.join(mutations)}")
            else:
                print(f"  Processing item {i+1}/{len(payload.items)}: full ΔΔG matrix")

            structure_text, structure_format = self._extract_structure(item)
            runtime_result = self.runner.predict(
                sequence=sequence_for_spurs,  # Use WT sequence when mutations are specified
                structure=structure_text,
                structure_format=structure_format,
                chain_id=item.chain_id,
                mutations=mutations,
            )

            results.append(
                SpursPredictResponseResult(
                    mutations=mutations,  # Includes auto-calculated mutations
                    ddG=runtime_result.get("ddg_value"),
                    ddG_contributions=runtime_result.get("contributions"),
                    ddG_matrix=runtime_result.get("ddg_matrix"),
                )
            )

            ddg_value = runtime_result.get("ddg_value")
            ddg_matrix = runtime_result.get("ddg_matrix")
            if ddg_value is not None:
                print(f"    → ΔΔG = {ddg_value:.3f} kcal/mol")
                if calculated_from_variant:
                    print(f"       (auto-calculated mutations: {', '.join(mutations)})")
            elif ddg_matrix is not None:
                matrix_rows = len(ddg_matrix["values"])
                print(
                    f"    → ΔΔG matrix generated with shape {matrix_rows}x{len(ddg_matrix['amino_acid_axis'])}"
                )

        print(f"\n✅ SPURS prediction complete for {len(results)} items")

        # Log summary of results
        manual_mut_count = sum(
            1
            for r in results
            if r.mutations and results.index(r) not in auto_calculated_items
        )
        matrix_count = sum(1 for r in results if r.ddG_matrix is not None)

        if len(auto_calculated_items) > 0:
            print(
                f"   • {len(auto_calculated_items)} item(s) with auto-calculated mutations from variant_sequence"
            )
        if manual_mut_count > 0:
            print(f"   • {manual_mut_count} item(s) with manual mutations")
        if matrix_count > 0:
            print(f"   • {matrix_count} item(s) with full DMS matrix")

        return SpursPredictResponse(results=results)

    @staticmethod
    def _extract_structure(item) -> tuple[str, str]:
        """
        Choose the provided structure representation and return its format.

        Args:
            item: Request item containing either pdb or cif structure data

        Returns:
            Tuple of (structure_text, format_string)

        Raises:
            ValueError: If neither PDB nor CIF content is provided
        """
        if item.pdb:
            return item.pdb, "pdb"
        if item.cif:
            return item.cif, "cif"
        raise ValueError("Expected either PDB or CIF content in request item")


if __name__ == "__main__":
    """
    Usage:
        python models/spurs/app.py

        # Force deploy to QA or production:
        python models/spurs/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        SpursModel,
        description=f"Run and optionally deploy the {MODEL_FAMILY.display_name} Modal app.",
    )
