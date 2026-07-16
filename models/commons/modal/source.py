from collections.abc import Callable
from pathlib import Path

import modal

# Exclude Python cache files from container mounts to prevent
# "modified during build process" errors in ephemeral deployments.
_PYCACHE_IGNORE = modal.FilePatternMatcher("**/__pycache__", "**/*.pyc")


def setup_source_layer(
    base_model_slug: str,
) -> Callable[[modal.Image], modal.Image]:
    """
    Adds common dependencies and model-specific files to a Modal image.

    Args:
        base_model_slug: The model's base slug from MODEL_FAMILY.base_model_slug
                        (e.g., "esm2", "esm-if1", "esmfold")

    Returns:
        A function that adds required dependencies and directories to a Modal image

    Example:
        ```python
        from models.commons.image_builder import setup_source_layer
        from models.esm2.config import MODEL_FAMILY

        image = modal.Image.from_registry("pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime")
        image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)
        ```
    """
    # Convert slug to folder name (hyphens to underscores)
    model_folder_name = base_model_slug.replace("-", "_")

    def add_files(image: modal.Image) -> modal.Image:
        # Import here to avoid circular imports

        from models.commons.util.config import remote_models_path, skip_modal_secrets

        # Guarantee PyYAML in every model image (this layer is common to ALL models, incl. the
        # weightless/algorithmic ones that skip the download layer). The framework's
        # ``ModelMixin.knowledge_graph()`` method reads each model's sources/comparison YAML at
        # request time, so its parser must be importable in-container. A RANGE (not an exact pin)
        # so it stays a no-op where a model already pins its own PyYAML (e.g. boltzgen, immunefold)
        # — any 6.x works for the loader — while still installing it where nothing else does.
        image = image.uv_pip_install("pyyaml>=6.0,<7.0")

        # Bake the model slug into the image so ``ModelMixin.knowledge_graph()`` can find its own
        # KG files at ``/root/models/<slug>/`` deterministically. Modal runs the app as ``__main__``
        # via its own entrypoint, so ``inspect``/``sys.modules`` resolve to the runner, not app.py —
        # an env var is the reliable in-container signal (this layer runs for every model).
        image = image.env({"_BIOLM_MODEL_SLUG": base_model_slug})

        # Use relative paths for Modal's add_local_dir
        local_models_base = Path("models")
        remote_models_base = Path(remote_models_path)

        # Define paths
        local_model_path = local_models_base / model_folder_name
        local_commons_path = local_models_base / "commons"
        local_init_path = local_models_base / "__init__.py"

        remote_model_path = remote_models_base / model_folder_name
        remote_commons_path = remote_models_base / "commons"
        remote_init_path = remote_models_base / "__init__.py"

        # Add all required components to the image
        image = (
            image.add_local_dir(
                local_model_path,
                str(remote_model_path),
                ignore=_PYCACHE_IGNORE,
                copy=True,
            )
            .add_local_dir(
                local_commons_path,
                str(remote_commons_path),
                ignore=_PYCACHE_IGNORE,
                copy=True,
            )
            .add_local_file(local_init_path, str(remote_init_path), copy=True)
        )

        # Bake the credential-less flag into the image so the RUNTIME container evaluates
        # runtime_secrets() (in @app.cls) identically to deploy time. When set at deploy,
        # runtime_secrets() returns [] so the class registers with 0 download secrets; if
        # the flag were absent inside the container, Modal's re-import of app.py would
        # re-evaluate runtime_secrets() to [cloudflare-r2] → the function would declare
        # more dependencies than were provisioned → crash-loop. This source layer is
        # common to ALL models (weight and weightless), so it's the universal place to
        # keep deploy-time and runtime secret resolution in lockstep.
        if skip_modal_secrets():
            image = image.env({"BIOLM_SKIP_MODAL_SECRETS": "1"})

        return image

    return add_files
