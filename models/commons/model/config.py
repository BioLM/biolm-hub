import itertools
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel, Field, PrivateAttr

from models.commons.model.schema import ModalResourceSpec
from models.commons.model.tag import ModelTags

T = TypeVar("T")


def biolm_model_class(cls: type[T]) -> type[T]:
    """
    Decorator that marks a class as a BioLM model class for discovery purposes.

    Works by marking the class with ``_is_biolm_model_class = True`` so the
    gateway/test framework can resolve a model family's container class.
    """
    cls._is_biolm_model_class = True  # type: ignore[attr-defined]  # dynamic marker attribute for discovery
    return cls


# --- Pydantic Schemas for the config.py file ---


class ActionSchemaMap(BaseModel):
    """Declaratively maps an action name to its request/response schemas."""

    name: str
    request_schema: type[BaseModel]
    response_schema: type[BaseModel]


class ResolvedVariant(BaseModel):
    """A fully specified, unique model variant, computed automatically."""

    name: str  # The unique identifier for this variant, e.g., "n1", "aa2fold-encode"
    modal_app_name: str  # The internal name for the Modal deployment, e.g., "esm1v-n1"
    public_endpoint_slug: str  # The public-facing URL slug, e.g., "protein-lm-v1-small"
    public_display_name: str  # The human-readable display name, e.g., "ESM1v n1"
    env_vars: dict[
        str, str
    ]  # The environment variables needed for this variant's container
    modal_resource_spec: ModalResourceSpec

    # Internal mapping for the test framework
    _variant_config: dict[str, str] = PrivateAttr()


class ModelFamily(BaseModel):
    """The single, authoritative definition for a model family, to be defined in each model's config.py."""

    base_model_slug: str
    display_name: str  # Human-readable base display name, e.g., "ESM1v", "ProstT5"
    action_schemas: list[ActionSchemaMap]

    # Name of the @biolm_model_class-decorated container class in this model's
    # app.py (e.g. "ESM2Model"). Consumed by the gateway's config-driven routing
    # to resolve a family's container class without AST discovery. Optional so
    # configs import cleanly until the value is populated.
    modal_class_name: str | None = None

    # Model tags for categorization and discovery
    # Rule of Specificity: Models should be tagged with the most specific applicable
    # molecule type. For example, ablang2 is correctly tagged with just ANTIBODY.
    tags: ModelTags

    # Defines the axes of variation, e.g., {"MODEL_NUMBER": ["n1", "n2"], "DIRECTION": ["a", "b"]}
    variant_axes: dict[str, list[str]]

    # A function that takes a variant configuration dict (e.g., {"MODEL_NUMBER": "n1"})
    # and returns its ModalResourceSpec.
    resource_function: Callable[[dict[str, str]], ModalResourceSpec]

    # A flexible function to define all naming schemes.
    # It takes the base_model_slug and a variant config dict.
    # It MUST return a tuple: (modal_app_name, public_endpoint_slug).
    naming_function: Callable[[str, dict[str, str]], tuple[str, str]] = Field(
        default=lambda base_slug, cfg: (
            (
                f"{base_slug}-{'-'.join(str(v) for v in cfg.values())}"
                if cfg
                else base_slug
            ),
            (
                f"{base_slug}-{'-'.join(str(v) for v in cfg.values())}"
                if cfg
                else base_slug
            ),
        )
    )

    # A function to generate human-readable display names for variants.
    # It takes the base display_name and a variant config dict.
    # Default: appends variant values separated by spaces.
    display_naming_function: Callable[[str, dict[str, str]], str] = Field(
        default=lambda display_name, cfg: (
            f"{display_name} {' '.join(str(v) for v in cfg.values())}"
            if cfg
            else display_name
        )
    )

    # A list of variant config dicts to explicitly exclude from the final set.
    # Example: [{"MODEL_ACTION": "generate", "MODEL_DIRECTION": "fold2AA"}]
    excluded_variant_combos: list[dict[str, str]] = []

    @property
    def resolved_variants(self) -> list[ResolvedVariant]:
        """
        Automatically computes the full list of valid, specified variants.
        This is the "engine" of the framework. It performs a Cartesian product of all
        variant axes, filters out exclusions, and generates a complete spec for each one.
        """
        if not self.variant_axes:
            # Handle single-variant models (like esmfold)
            variant_config: dict[str, str] = {}
            modal_app_name, public_slug = self.naming_function(
                self.base_model_slug, variant_config
            )
            variant = ResolvedVariant(
                name="",
                modal_app_name=modal_app_name,
                public_endpoint_slug=public_slug,
                public_display_name=self.display_naming_function(
                    self.display_name, variant_config
                ),
                env_vars={},
                modal_resource_spec=self.resource_function(variant_config),
            )
            variant._variant_config = variant_config
            return [variant]

        axis_names = list(self.variant_axes.keys())
        axis_values = [self.variant_axes[name] for name in axis_names]

        all_combos = [
            dict(zip(axis_names, p))  # noqa: B905
            for p in itertools.product(*axis_values)
        ]

        valid_combos = [c for c in all_combos if c not in self.excluded_variant_combos]

        variants = []
        for combo in valid_combos:
            modal_app_name, public_slug = self.naming_function(
                self.base_model_slug, combo
            )
            variant = ResolvedVariant(
                name="-".join(str(v) for v in combo.values()),
                modal_app_name=modal_app_name,
                public_endpoint_slug=public_slug,
                public_display_name=self.display_naming_function(
                    self.display_name, combo
                ),
                env_vars={k: str(v) for k, v in combo.items()},
                modal_resource_spec=self.resource_function(combo),
            )
            variant._variant_config = combo
            variants.append(variant)

        return variants

    def find_variant(self, **env_vars: str) -> ResolvedVariant:
        """Find a variant by its environment variables.

        Args:
            **env_vars: Environment variables to match (e.g., MODEL_SIZE="300m")

        Returns:
            The matching ResolvedVariant

        Raises:
            ValueError: If no matching variant is found, with helpful error message

        Example:
            variant = MODEL_FAMILY.find_variant(MODEL_SIZE="300m")
        """
        try:
            return next(v for v in self.resolved_variants if v.env_vars == env_vars)
        except StopIteration:
            available_variants = [v.env_vars for v in self.resolved_variants]
            raise ValueError(
                f"No variant found matching {env_vars}. "
                f"Available variants for {self.base_model_slug}: {available_variants}"
            ) from None

    def get_app_config(self, **env_vars: str) -> tuple[str, ModalResourceSpec]:
        """Get app name and resource spec for a variant in one call.

        Args:
            **env_vars: Environment variables to match (e.g., MODEL_SIZE="300m")

        Returns:
            Tuple of (modal_app_name, modal_resource_spec)

        Raises:
            ValueError: If no matching variant is found

        Example:
            app_name, resource_spec = MODEL_FAMILY.get_app_config(MODEL_SIZE="300m")
        """
        variant = self.find_variant(**env_vars)
        return variant.modal_app_name, variant.modal_resource_spec
