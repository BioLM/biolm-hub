import importlib.util
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

from models.commons.core.logging import get_logger
from models.commons.model.config import ModelFamily

logger = get_logger(__name__)


class ModelMapper:
    """
    Centralized model mapping and discovery system.

    Discovers all models by importing their ``config.py`` files and reading the
    declarative ``MODEL_FAMILY`` object, then provides unified access to model
    metadata, schemas, resource specs, and the Modal container class name.

    The Modal class name comes straight from ``ModelFamily.modal_class_name``
    (set per-model in ``config.py``) — there is no source-code scanning. A CI
    guard (``gateway/test_discovery.py``) keeps each ``modal_class_name`` in sync
    with the ``@biolm_model_class``-decorated class in that model's ``app.py``.
    """

    def __init__(self) -> None:
        """Initialize the discovery system and load all model configurations."""
        self._model_families: dict[str, ModelFamily] = {}
        self._variant_map: dict[str, dict[str, Any]] = {}
        self._action_registry: dict[
            tuple[str, str], tuple[type[BaseModel], type[BaseModel]]
        ] = {}
        self._class_names: dict[str, str] = {}
        self._resource_specs: dict[str, dict[str, Any]] = {}

        # Load all configurations at initialization
        self._load_all_configs()
        self._build_variant_map()
        self._build_action_registry()

    def _load_all_configs(self) -> None:
        """
        Import every ``models/*/config.py`` and register its ``MODEL_FAMILY``.

        The Modal class name is read from ``MODEL_FAMILY.modal_class_name`` — the
        single source of truth — so no AST/source scanning is needed.
        """
        models_dir = Path(__file__).parent.parent / "models"

        for model_dir in models_dir.iterdir():
            if (
                not model_dir.is_dir()
                or model_dir.name.startswith(("_", "."))
                or model_dir.name == "commons"
            ):
                continue

            config_path = model_dir / "config.py"
            if not config_path.exists():
                continue

            try:
                # Import the config module
                spec = importlib.util.spec_from_file_location(
                    f"models.{model_dir.name}.config", str(config_path)
                )
                if spec and spec.loader:
                    config_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(config_module)

                    # Extract MODEL_FAMILY if it exists
                    if hasattr(config_module, "MODEL_FAMILY"):
                        model_family = config_module.MODEL_FAMILY
                        if isinstance(model_family, ModelFamily):
                            base_slug = model_family.base_model_slug
                            self._model_families[base_slug] = model_family
                            if model_family.modal_class_name:
                                self._class_names[base_slug] = (
                                    model_family.modal_class_name
                                )
                            else:
                                logger.warning(
                                    "Model '%s' has no modal_class_name set; "
                                    "gateway cannot route to it.",
                                    base_slug,
                                )
                            logger.info("Loaded config for %s", base_slug)

            except Exception as e:
                logger.warning("Failed to load config for %s: %s", model_dir.name, e)

    def _build_variant_map(self) -> None:
        """
        Build the variant map from model configurations.
        Maps public API slugs to base model slug and variant info.
        """
        for base_slug, model_family in self._model_families.items():
            for variant in model_family.resolved_variants:
                # Store the mapping from public slug to variant info
                self._variant_map[variant.public_endpoint_slug] = {
                    "base_model_slug": base_slug,
                    "model_variant": variant.name if variant.name else None,
                    "modal_app_name": variant.modal_app_name,
                    "env_vars": variant.env_vars,
                    "display_name": variant.public_display_name,
                }

                # Also store resource specs indexed by modal app name
                self._resource_specs[variant.modal_app_name] = (
                    variant.modal_resource_spec.model_dump()
                )

    def _build_action_registry(self) -> None:
        """
        Build the action registry from model configurations.
        Maps (base_model_slug, action) to (request_schema, response_schema).
        """
        for base_slug, model_family in self._model_families.items():
            for action_map in model_family.action_schemas:
                key = (base_slug, action_map.name)
                self._action_registry[key] = (
                    action_map.request_schema,
                    action_map.response_schema,
                )

    def get_variant_info(self, api_slug: str) -> Optional[dict[str, Any]]:
        """
        Get variant information for a given API slug.

        Args:
            api_slug: The public API endpoint slug (e.g., 'esm2-650m')

        Returns:
            Dictionary with base_model_slug, model_variant, modal_app_name,
            env_vars, display_name; or None if not found.
        """
        return self._variant_map.get(api_slug)

    def get_action_schemas(
        self, base_model_slug: str, action: str
    ) -> tuple[Optional[type[BaseModel]], Optional[type[BaseModel]]]:
        """
        Get request and response schemas for a model action.

        Args:
            base_model_slug: The base model identifier (e.g., 'esm2')
            action: The action name (e.g., 'predict')

        Returns:
            Tuple of (RequestSchema, ResponseSchema) or (None, None) if not found.
        """
        return self._action_registry.get((base_model_slug, action), (None, None))

    def get_class_name(self, base_model_slug: str) -> Optional[str]:
        """
        Get the Modal container class name for a model.

        Read directly from ``ModelFamily.modal_class_name`` (set in the model's
        ``config.py``).

        Args:
            base_model_slug: The base model identifier (e.g., 'esm2')

        Returns:
            The Modal class name or None if not configured.
        """
        return self._class_names.get(base_model_slug)

    def get_resource_spec(self, modal_app_name: str) -> Optional[dict[str, Any]]:
        """
        Get resource specification for a Modal app.

        Args:
            modal_app_name: The Modal app name (e.g., 'esm2-650m')

        Returns:
            Dictionary with resource specifications or None if not found.
        """
        return self._resource_specs.get(modal_app_name)

    def get_all_resource_specs(self) -> dict[str, dict[str, Any]]:
        """
        Get all resource specifications.

        Returns:
            Dictionary mapping Modal app names to resource specifications.
        """
        return self._resource_specs.copy()

    def get_all_actions_for_model(
        self, base_model_slug: str
    ) -> list[tuple[str, type[BaseModel], type[BaseModel]]]:
        """
        Get all actions and their schemas for a given model.

        Args:
            base_model_slug: The base model identifier (e.g., 'esm2')

        Returns:
            List of tuples (action_name, request_schema, response_schema).
        """
        result = []
        for (slug, action), (req_schema, res_schema) in self._action_registry.items():
            if slug == base_model_slug:
                result.append((action, req_schema, res_schema))
        return result

    def get_all_variant_mappings(self) -> dict[str, dict[str, Any]]:
        """
        Get the complete variant mapping.

        Returns:
            Dictionary mapping API slugs to variant information.
        """
        return self._variant_map.copy()

    def get_all_registered_models(self) -> list[str]:
        """
        Get list of all registered base model slugs.

        Returns:
            List of base model identifiers.
        """
        return list(self._model_families.keys())


# Global singleton instance
_discovery_instance: Optional[ModelMapper] = None


def get_model_mapper() -> ModelMapper:
    """
    Get the global ModelMapper instance.
    Creates it on first call (lazy initialization).

    Returns:
        The global ModelMapper instance.
    """
    global _discovery_instance
    if _discovery_instance is None:
        logger.info("Initializing model mapper system...")
        _discovery_instance = ModelMapper()
        logger.info("Mapped %d model variants", len(_discovery_instance._variant_map))
    return _discovery_instance
