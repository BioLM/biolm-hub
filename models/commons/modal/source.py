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

        from models.commons.util.config import remote_models_path

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

        return image

    return add_files
