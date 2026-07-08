import types
import typing
from typing import Any, get_args, get_origin

from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic import BaseModel
from pydantic.fields import FieldInfo

from gateway.model_discovery import ModelMapper
from models.commons.core.logging import get_logger

logger = get_logger(__name__)


def _unwrap_optional(annotation: Any) -> Any:
    """Return the inner type of an ``Optional[T]`` / ``T | None`` annotation.

    A field declared ``params: Optional[SomeParams]`` (or ``SomeParams | None``)
    has an annotation of ``Union[SomeParams, None]`` — which is NOT a Pydantic
    model itself, so ``hasattr(annotation, "model_fields")`` is False and a naive
    introspection would treat it as a plain scalar and drop the whole params
    object. Unwrapping to the single non-``None`` member (only when there is
    exactly one) lets the list/enum/nested-model detectors see the real type, so
    ``Optional[Params]`` renders identically to a required ``Params``. Genuine
    multi-member unions (e.g. ``int | str``) are left untouched.
    """
    if get_origin(annotation) is typing.Union or isinstance(
        annotation, types.UnionType
    ):
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return annotation


def get_field_details(field: FieldInfo) -> dict[str, Any]:
    """Extracts relevant details from a Pydantic field."""
    details = _init_field_details(field)
    _detect_list_type(field, details)
    _detect_enum_type(field, details)
    _detect_nested_model(field, details)
    _process_metadata(field, details)
    return details


def _init_field_details(field: FieldInfo) -> dict[str, Any]:
    """Initialize basic field details."""
    return {
        "type": str(getattr(field, "annotation", "Unknown")),
        "default": _sanitize_value(getattr(field, "default", None)),
        "required": field.is_required() if hasattr(field, "is_required") else True,
        "description": _sanitize_value(getattr(field, "description", None)),
        "min_length": _sanitize_value(getattr(field, "min_length", None)),
        "max_length": _sanitize_value(getattr(field, "max_length", None)),
        "ge": _sanitize_value(getattr(field, "ge", None)),
        "le": _sanitize_value(getattr(field, "le", None)),
        "enum": None,
        "is_list": False,
        "is_multi_select": False,
        "is_nested_model": False,
        "nested_fields": None,
    }


def _sanitize_value(value: Any) -> Any:
    """Sanitize values to be JSON serializable, converting PydanticUndefined to None."""
    if value is None:
        return None

    # Handle PydanticUndefined types
    value_type = str(type(value))
    if "PydanticUndefined" in value_type or "Undefined" in value_type:
        return None

    # Convert other non-serializable types to strings
    try:
        # Test if value is JSON serializable
        import json

        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value) if value is not None else None


def _detect_list_type(field: FieldInfo, details: dict[str, Any]) -> None:
    """Detect if field is a list type."""
    annotation = _unwrap_optional(getattr(field, "annotation", None))
    if annotation is None:
        return

    type_str = str(annotation)
    if type_str.startswith("list["):
        details["is_list"] = True
        _detect_multi_select_enum(type_str, details)

        # Try to extract nested fields from list item type
        try:
            origin = getattr(annotation, "__origin__", None)
            if origin is list:
                args = getattr(annotation, "__args__", ())
                if args and len(args) > 0:
                    list_item_type = args[0]
                    # Check if the list item is a BaseModel
                    if hasattr(list_item_type, "model_fields"):
                        details["nested_fields"] = {
                            name: get_field_details(nested_field)
                            for name, nested_field in list_item_type.model_fields.items()
                        }
                        logger.debug(
                            "Extracted nested fields for list item %s: %s",
                            list_item_type,
                            list(details["nested_fields"].keys()),
                        )
        except Exception as e:
            logger.warning(
                "Could not extract nested fields from list type %s: %s", type_str, e
            )


def _detect_multi_select_enum(type_str: str, details: dict[str, Any]) -> None:
    """Detect if list contains enum types."""
    try:
        import re

        inner_match = re.search(r"list\[([^\]]+)\]", type_str)
        if inner_match:
            inner_type_name = inner_match.group(1)
            if "Options" in inner_type_name or "Enum" in inner_type_name:
                details["is_multi_select"] = True
    except Exception:
        pass


def _detect_enum_type(field: FieldInfo, details: dict[str, Any]) -> None:
    """Detect enum types."""
    annotation = _unwrap_optional(getattr(field, "annotation", None))
    if annotation is None:
        return

    # Handle direct enum types
    if hasattr(annotation, "__members__"):
        details["enum"] = [e.value for e in annotation]

    # Handle list of enums
    try:
        origin = getattr(annotation, "__origin__", None)
        if origin is list:
            args = getattr(annotation, "__args__", ())
            if args and hasattr(args[0], "__members__"):
                details["enum"] = [e.value for e in args[0]]
                details["is_multi_select"] = True
    except Exception:
        pass


def _detect_nested_model(field: FieldInfo, details: dict[str, Any]) -> None:
    """Detect nested BaseModel fields."""
    annotation = _unwrap_optional(getattr(field, "annotation", None))
    if annotation is None:
        return

    try:
        if hasattr(annotation, "model_fields"):
            details["is_nested_model"] = True
            details["nested_fields"] = {
                name: get_field_details(nested_field)
                for name, nested_field in annotation.model_fields.items()
            }
    except Exception:
        pass


def _process_metadata(field: FieldInfo, details: dict[str, Any]) -> None:
    """Process field metadata and extract validation hints."""
    validation_hints = []

    if hasattr(field, "metadata"):
        details["metadata"] = []
        for meta in field.metadata:
            if isinstance(meta, dict):
                details.update(meta)
            elif isinstance(meta, int | float | str):
                details["metadata"].append(meta)
            else:
                # Extract validation hints from validator instances
                hint = _extract_validator_hint(meta)
                if hint:
                    validation_hints.append(hint)

    if validation_hints:
        details["validation_hints"] = validation_hints


def _extract_validator_hint(validator: Any) -> str:
    """Extract human-readable hints from validator instances."""
    validator_name = validator.__class__.__name__

    # Handle class-based validators
    class_hint = _extract_class_validator_hint(validator_name, validator)
    if class_hint:
        return class_hint

    # Handle function validators
    return _extract_function_validator_hint(validator)


def _extract_class_validator_hint(validator_name: str, validator: Any) -> str:
    """Extract hints from class-based validators."""
    validators = {
        "SingleOccurrenceOf": lambda v: f"Must contain exactly one '{getattr(v, 'single_token', '')}' token",
        "SingleOrMoreOccurrencesOf": lambda v: f"Must contain at least one '{getattr(v, 'token', '')}' token",
        "UpToNNonConsecutiveOccurrencesOf": lambda v: f"Up to {getattr(v, 'max_count', 0)} '{getattr(v, 'token', '')}' separators allowed (non-consecutive)",
        "AAExtendedPlusExtra": lambda v: f"Protein sequence with allowed special tokens: {', '.join(getattr(v, 'extra', []))}",
        "AAUnambiguousPlusExtra": lambda v: f"Standard amino acids with special tokens: {', '.join(getattr(v, 'extra', []))}",
    }

    if validator_name in validators:
        try:
            return validators[validator_name](validator)
        except Exception:
            return ""
    return ""


def _extract_function_validator_hint(validator: Any) -> str:
    """Extract hints from function-based validators."""
    if not (callable(validator) and hasattr(validator, "__name__")):
        return ""

    function_hints = {
        "validate_aa_unambiguous": "Standard amino acid letters only (ACDEFGHIKLMNPQRSTVWY)",
        "validate_aa_extended": "Extended amino acid letters (ACDEFGHIKLMNPQRSTVWYXZUO)",
        "validate_dna_unambiguous": "DNA nucleotides only (ACTG)",
        "validate_pdb": "Valid PDB file content required",
    }

    return function_hints.get(validator.__name__, "")


def analyze_schema(schema: type[BaseModel] | None) -> dict[str, Any]:
    """Analyzes a Pydantic model class and returns a dictionary of its fields."""
    if schema is None:
        return {}

    # Handle different ways Pydantic might store model fields
    model_fields = getattr(schema, "model_fields", None) or getattr(
        schema, "__fields__", {}
    )

    if not model_fields:
        return {}

    try:
        field_details = {
            name: get_field_details(field) for name, field in model_fields.items()
        }
        # Sanitize the entire schema to ensure JSON serialization works
        return _sanitize_schema_dict(field_details)
    except Exception as e:
        # Debug logging for troubleshooting
        logger.warning("Failed to analyze schema %s: %s", schema.__class__.__name__, e)
        return {}


def _sanitize_schema_dict(schema_dict: dict[str, Any]) -> dict[str, Any]:
    """Recursively sanitize a schema dictionary to ensure JSON serialization."""
    if not isinstance(schema_dict, dict):
        return _sanitize_value(schema_dict)

    sanitized: dict[str, Any] = {}
    for key, value in schema_dict.items():
        if isinstance(value, dict):
            sanitized[key] = _sanitize_schema_dict(value)
        elif isinstance(value, list):
            sanitized[key] = [
                (
                    _sanitize_schema_dict(item)
                    if isinstance(item, dict)
                    else _sanitize_value(item)
                )
                for item in value
            ]
        else:
            sanitized[key] = _sanitize_value(value)

    return sanitized


def generate_catalog_data(
    app: FastAPI, model_mapper: ModelMapper
) -> dict[str, dict[str, Any]]:
    """Generates a structured dictionary of API endpoints from a FastAPI app.

    ``model_slug`` (the path segment right after ``/api/v1/``) is always a
    variant's ``public_endpoint_slug``, so ``model_mapper`` resolves the exact
    same config-driven ``base_model_slug`` and ``public_display_name`` that
    ``tooling/gen_model_catalog.py`` and ``docs/gen_pages.py`` render — never a
    title-cased guess derived from the slug text.
    """
    catalog: dict[str, dict[str, Any]] = {}
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/v1/"):
            # Correctly parse the model_slug from the path, not the tag
            path_parts = route.path.strip("/").split("/")
            if len(path_parts) >= 3:
                model_slug = path_parts[2]
            else:
                continue  # Skip routes that don't match the expected format

            if model_slug not in catalog:
                variant_info = model_mapper.get_variant_info(model_slug)
                if variant_info is not None:
                    base_model_slug = variant_info["base_model_slug"]
                    display_name = variant_info["display_name"]
                else:
                    # Should not happen (every registered route comes from a
                    # known variant), but degrade gracefully rather than 500.
                    logger.warning(
                        "No variant info for routed model slug '%s'; falling "
                        "back to a title-cased slug for its display name.",
                        model_slug,
                    )
                    base_model_slug = _extract_base_model_slug(model_slug)
                    display_name = model_slug.replace("-", " ").title()
                catalog[model_slug] = {
                    "display_name": display_name,
                    "base_model_slug": base_model_slug,
                    "endpoints": [],
                }

            body_schema = None
            if route.body_field is not None:
                # FastAPI's ModelField no longer exposes ``.type_`` (removed in the
                # pydantic-v2 compat layer). ``field_info`` is a real pydantic
                # ``FieldInfo``; its ``.annotation`` is the request body's model
                # class — the direct, stable replacement for the old ``.type_``.
                # Each gateway route has exactly one body param (``payload``,
                # ``embed=False``), so this annotation is the request model itself.
                body_schema = route.body_field.field_info.annotation

            # Starlette 1.x types ``APIRoute.methods`` as ``set[str] | None``; a
            # registered API route always has methods, so fall back to an empty
            # set only to satisfy the type checker.
            method = next(iter(route.methods or set()), "")

            endpoint_info = {
                "path": route.path,
                "method": method,
                "name": route.summary,
                "description": route.description,
                "request_schema": analyze_schema(body_schema) if body_schema else {},
            }
            catalog[model_slug]["endpoints"].append(endpoint_info)
    return catalog


def _extract_base_model_slug(model_slug: str) -> str:
    """Extract base model slug for grouping similar models."""
    # Handle common patterns like esm1v-n1, esm1v-n2, etc.
    if "-n" in model_slug and model_slug.split("-n")[-1].isdigit():
        return model_slug.split("-n")[0]

    # Handle patterns like esm2-650m, esm2-3b, etc.
    import re

    # Remove size suffixes like -650m, -3b, -15b, -all
    base = re.sub(r"-(\d+[bm]|all)$", "", model_slug)
    return base


def group_models_by_base(
    catalog: dict[str, dict[str, Any]],
    model_mapper: ModelMapper,
) -> dict[str, dict[str, Any]]:
    """Group models by their base model slug.

    The group title is the family's ``ModelFamily.display_name`` (e.g.
    "DNA-Chisel", "ThermoMPNN-D") — the same field the README/docs catalog
    generators read — never a title-cased ``base_model_slug``.
    """
    grouped: dict[str, dict[str, Any]] = {}

    for model_slug, model_info in catalog.items():
        base_slug = model_info.get("base_model_slug", model_slug)

        if base_slug not in grouped:
            family = model_mapper.get_model_family(base_slug)
            if family is not None:
                display_name = family.display_name
            else:
                # Fallback for the (unexpected) case of an unregistered base
                # slug; keeps the catalog rendering instead of erroring.
                logger.warning(
                    "No ModelFamily registered for base slug '%s'; falling "
                    "back to a title-cased slug for its group display name.",
                    base_slug,
                )
                display_name = base_slug.replace("-", " ").title()
            grouped[base_slug] = {
                "display_name": display_name,
                "variants": [],
            }

        grouped[base_slug]["variants"].append(
            {
                "slug": model_slug,
                "display_name": model_info["display_name"],
                "endpoints": model_info["endpoints"],
            }
        )

    # Sort variants within each group (stable, by slug) so families read sensibly.
    for group in grouped.values():
        group["variants"].sort(key=lambda x: x["slug"])

    # Order the groups themselves alphabetically by display name. Route-registration
    # order is arbitrary; a stable alphabetical ordering makes the index scannable.
    return dict(
        sorted(grouped.items(), key=lambda kv: kv[1]["display_name"].casefold())
    )
