import os
from collections.abc import Iterable
from typing import Any, Optional, cast

import modal

from models.commons.core.logging import get_logger
from models.commons.util.config import (
    deployed_environment_names,
    prod_environment_name,
)

logger = get_logger(__name__)


class ModelVariantError(ValueError):
    """Custom exception for model variant configuration errors."""

    pass


def parse_variant(
    env_var_name: str,
    allowed_values: Iterable[str],
    default: Optional[str] = None,
    var_is_required: bool = False,
    case_insensitive: bool = True,
) -> dict[str, str]:
    """
    Gets and validates a single model variant from an environment variable.

    Args:
        env_var_name: Name of the environment variable (e.g., "MODEL_SIZE").
        allowed_values: An iterable of valid strings (e.g., an EnhancedStringEnum).
        default: The default value to use if the env var is not set.
        var_is_required: If True, raises error if the env var is not set.
        case_insensitive: If True, matches the value without regard to case.

    Returns:
        A dictionary with the env_var_name as key and validated value.
    """
    raw_value = os.getenv(env_var_name)
    final_value = raw_value or default

    if final_value is None:
        if var_is_required:
            raise ModelVariantError(
                f"Required environment variable '{env_var_name}' is not set. "
                f"Valid options: {', '.join(list(allowed_values))}"
            )
        return {}

    # Find the canonical-cased match from the allowed values
    canonical_match = None
    for v in allowed_values:
        val_to_check = str(v)
        if case_insensitive:
            if final_value.lower() == val_to_check.lower():
                canonical_match = val_to_check
                break
        elif final_value == val_to_check:
            canonical_match = val_to_check
            break

    if canonical_match is None:
        raise ModelVariantError(
            f"Invalid value '{final_value}' for '{env_var_name}'. "
            f"Valid options: {', '.join(list(allowed_values))}"
        )

    if raw_value is None and default is not None:
        logger.info(
            "✅ '%s' not set, using default: '%s'", env_var_name, canonical_match
        )
    else:
        logger.info("✅ Using variant '%s' for '%s'", canonical_match, env_var_name)

    return {env_var_name: canonical_match}


def parse_variants(variant_configs: list[dict[str, Any]]) -> dict[str, str]:
    """
    Gets and validates multiple model variant environment variables.

    Args:
        variant_configs: A list of configuration dictionaries, where each dict
                         is a set of kwargs for the parse_variant() function.

    Returns:
        A dictionary mapping environment variable names to their validated values.
    """
    results = {}
    for config in variant_configs:
        env_var = config["env_var_name"]
        try:
            variant_dict = parse_variant(**config)
            # parse_variant now returns a dict, merge it with results
            results.update(variant_dict)
        except ModelVariantError as e:
            # Re-raise with more context
            raise ModelVariantError(f"Configuration error for '{env_var}': {e}") from e

    logger.info("🔧 Model variant configuration:")
    for env_var, value in results.items():
        logger.debug("    %s: %s", env_var, value)

    return results


def get_environment_name() -> str:
    """
    Retrieves the current Modal environment name from config.

    Returns:
        str: The environment name (e.g., "biolm-hub-dev" or "biolm-hub").
    """

    return cast(str, modal.config.config.get("environment"))


def is_prod_environment() -> bool:
    """
    Checks if the current Modal environment is production.

    Compares the environment name to `prod_environment_name`.

    Returns:
        bool: True if environment is set to production, otherwise False.
    """
    current_environment = get_environment_name()
    logger.info("Current Modal environment: %s", current_environment)

    return current_environment == prod_environment_name


def is_production() -> bool:
    """
    Checks if the current Modal environment is one of the deployed environments.

    Compares the environment name to known deployed_environment_names such as
    "biolm-hub-dev" or "biolm-hub".

    Returns:
        bool: True if the environment is in the deployed list, otherwise False.
    """
    current_environment = get_environment_name()
    logger.info("Current Modal environment: %s", current_environment)

    return current_environment in deployed_environment_names
