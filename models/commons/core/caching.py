import hashlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Optional

import modal
import orjson
from pydantic import BaseModel

from models.commons.core.logging import DebugLogger
from models.commons.data.serializer import serialize_model
from models.commons.model.schema import ModelActions
from models.commons.storage.cache import (
    fetch_from_r2,
    store_in_r2,
)
from models.commons.util.config import get_model_cache_name

logger = logging.getLogger(__name__)

### ------- Configuration and Helper Functions ------- ###


non_cacheable_actions = {ModelActions.GENERATE}  # Actions we never want to cache


def build_item_cache_key(
    model_slug: str,
    model_action: str,
    item_dict: dict,
    params: Optional[dict],
) -> str:
    """
    Creates a SHA256-based cache key incorporating model slug, action, item data, and params.

    This key is used for both short-term caching (Modal Dict) and long-term
    storage (Cloudflare R2). The item_dict and params are JSON-serialized with
    sorted keys before hashing.

    Args:
        model_slug (str): The model slug (e.g., "esmfold").
        model_action (str): The model action (e.g., "predict").
        item_dict (dict): The item data to include in the hash.
        params (Optional[dict]): Additional parameter data to include.

    Returns:
        str: A 64-character hex digest (SHA256).
    """

    hasher = hashlib.sha256()

    # Incorporate slug + action
    hasher.update(f"{model_slug}:{model_action}".encode())

    # Incorporate item
    item_bytes = orjson.dumps(item_dict, option=orjson.OPT_SORT_KEYS)
    hasher.update(item_bytes)

    # Incorporate params if present
    if params is not None:
        params_bytes = orjson.dumps(params, option=orjson.OPT_SORT_KEYS)
        hasher.update(params_bytes)

    return hasher.hexdigest()


def _result_item_is_cacheable(item_dict: dict) -> bool:
    """Return True only if item_dict contains at least one non-trivial output field.

    Input-only fields (sequence, id, heavy, light, nucleotide_sequence) are ignored.
    An item is *not* cacheable if every output field is None, an empty list, or an
    empty dict — those are error / null-embedding responses that should not be stored
    in the cache to avoid poisoning future lookups.
    """
    INPUT_FIELDS = {"sequence", "id", "heavy", "light", "nucleotide_sequence"}
    for key, value in item_dict.items():
        if key in INPUT_FIELDS:
            continue
        if value is None:
            continue
        if isinstance(value, list | dict) and len(value) == 0:
            continue
        # Found at least one non-trivial output field
        return True
    return False


### ------- Short-Term Cache (modal.Dict)


# Per-model cache registry with lazy initialization.
# Each model gets its own Modal Dict to prevent large models (e.g., ESM2-3B)
# from filling a shared cache and affecting other models.
_model_cache_registry: dict[str, modal.Dict] = {}

# Error patterns that indicate cache is full or experiencing memory issues.
# The exact error from Modal is: "modal.Dict exceeded max memory limit"
_CACHE_FULL_ERROR_PATTERNS = (
    "exceeded max memory limit",  # Exact Modal error message
    "exceeded max memory",
    "memory limit",
    "dict is full",
    "capacity exceeded",
)


def get_model_cache(model_slug: str) -> modal.Dict:
    """Get or create a model-specific cache Dict.

    Uses lazy initialization to create cache Dicts only when needed.
    Cache names follow the pattern "model-cache-{model_slug}".

    Args:
        model_slug: The model's slug identifier (e.g., "esm2-3b", "esmfold").

    Returns:
        A Modal Dict instance for the specified model.
    """
    if model_slug not in _model_cache_registry:
        cache_name = get_model_cache_name(model_slug)
        _model_cache_registry[model_slug] = modal.Dict.from_name(
            cache_name, create_if_missing=True
        )
    return _model_cache_registry[model_slug]


def _is_cache_full_error(error: Exception) -> bool:
    """Check if an exception indicates the cache is full or at memory limit."""
    error_str = str(error).lower()
    return any(pattern in error_str for pattern in _CACHE_FULL_ERROR_PATTERNS)


def _safe_cache_get(
    model_cache: modal.Dict, key: str, debug_logger: DebugLogger
) -> Optional[Any]:
    """Safely retrieve a value from the cache, returning None on any failure.

    Cache failures should never cause API errors - we gracefully degrade
    to recomputing the value.

    Args:
        model_cache: The Modal Dict to read from.
        key: The cache key to look up.
        debug_logger: Logger for debug messages.

    Returns:
        The cached value if found, None if not found or on any error.
    """
    try:
        return model_cache.get(key, None)
    except Exception as e:
        debug_logger.debug(f"Cache read failed for key {key}: {e}")
        logger.warning(f"Short-term cache read failed: {e}")
        return None


def _safe_cache_update(
    model_cache: modal.Dict,
    model_slug: str,
    updates: dict[str, Any],
    debug_logger: DebugLogger,
) -> bool:
    """Safely update the cache, handling full cache by clearing and retrying.

    If the cache write fails due to capacity issues, the cache is cleared
    and the write is retried once. If it still fails, the error is logged
    but not propagated - the API response is still returned to the user.

    Args:
        model_cache: The Modal Dict to write to.
        model_slug: The model slug (for logging and cache clearing).
        updates: Dictionary of key-value pairs to write.
        debug_logger: Logger for debug messages.

    Returns:
        True if the update succeeded, False if it failed (but was handled).
    """
    if not updates:
        return True

    try:
        model_cache.update(**updates)
        return True
    except Exception as e:
        if _is_cache_full_error(e):
            logger.warning(f"Cache full for {model_slug}, clearing and retrying: {e}")
            debug_logger.debug(f"Cache full, attempting clear and retry: {e}")

            # Attempt to clear and retry
            try:
                model_cache.clear()
                logger.info(f"Cleared full cache for {model_slug}")

                # Retry the update
                model_cache.update(**updates)
                logger.info(
                    f"Successfully wrote to cache after clearing for {model_slug}"
                )
                return True
            except Exception as retry_error:
                logger.error(
                    f"Cache write failed even after clearing for {model_slug}: {retry_error}"
                )
                debug_logger.debug(f"Cache write failed after clear: {retry_error}")
                return False
        else:
            # Non-capacity error - log and continue
            logger.warning(f"Cache write failed for {model_slug}: {e}")
            debug_logger.debug(f"Cache write failed: {e}")
            return False


async def _safe_cache_get_aio(
    model_cache: modal.Dict, key: str, debug_logger: DebugLogger
) -> Optional[Any]:
    """Async variant of _safe_cache_get for use inside async handlers (non-blocking)."""
    try:
        return await model_cache.get.aio(key, None)
    except Exception as e:
        debug_logger.debug(f"Cache read failed for key {key}: {e}")
        logger.warning(f"Short-term cache read failed: {e}")
        return None


async def _safe_cache_update_aio(
    model_cache: modal.Dict,
    model_slug: str,
    updates: dict[str, Any],
    debug_logger: DebugLogger,
) -> bool:
    """Async variant of _safe_cache_update for use inside async handlers (non-blocking)."""
    if not updates:
        return True

    try:
        await model_cache.update.aio(updates)
        return True
    except Exception as e:
        if _is_cache_full_error(e):
            logger.warning(f"Cache full for {model_slug}, clearing and retrying: {e}")
            debug_logger.debug(f"Cache full, attempting clear and retry: {e}")

            try:
                await model_cache.clear.aio()
                logger.info(f"Cleared full cache for {model_slug}")

                await model_cache.update.aio(updates)
                logger.info(
                    f"Successfully wrote to cache after clearing for {model_slug}"
                )
                return True
            except Exception as retry_error:
                logger.error(
                    f"Cache write failed even after clearing for {model_slug}: {retry_error}"
                )
                debug_logger.debug(f"Cache write failed after clear: {retry_error}")
                return False
        else:
            logger.warning(f"Cache write failed for {model_slug}: {e}")
            debug_logger.debug(f"Cache write failed: {e}")
            return False


def clear_short_term_model_cache(
    model_slug: Optional[str] = None, force: bool = False
) -> None:
    """Clear the short-term cache for a specific model or all cached models.

    By default, a confirmation flag is required. If `force` is set to True,
    the cache(s) will be cleared.

    Args:
        model_slug: If provided, clears only this model's cache. If None,
            clears all model caches in the registry.
        force: Whether to proceed with clearing without further checks.

    Returns:
        None
    """
    if not force:
        print("Not clearing cache. Set force=True to proceed.")
        return

    if model_slug:
        cache = get_model_cache(model_slug)
        cache.clear()
        print(f"Cleared short-term cache for model: {model_slug}")
    else:
        for slug, cache in _model_cache_registry.items():
            cache.clear()
            print(f"Cleared short-term cache for model: {slug}")
        if not _model_cache_registry:
            print("No model caches in registry to clear.")


### ------- Reusable Cache Handler


async def process_with_cache(
    items: list[BaseModel],
    params: Optional[dict[str, Any]],
    model_slug: str,
    model_action: str,
    compute_fn: Callable[[list[BaseModel], list[int]], Awaitable[BaseModel]],
    debug_logger: DebugLogger,
) -> tuple[dict[str, list[Any]], int]:
    """
    Handles the full cache-check -> compute -> cache-update workflow.
    This function is designed to be called by both the Gateway and the decorator.

    Args:
        items (list): The list of Pydantic items from the request.
        params (dict): The dictionary of parameters from the request.
        model_slug (str): The slug of the model being called.
        model_action (str): The action being performed.
        compute_fn (Callable): An awaitable function that takes (items_to_compute,
                              indices_to_compute) and returns the computed results.
        debug_logger: The logger instance.

    Returns:
        A dictionary containing the final, merged results.
    """
    # 1. PRE-PROCESS: check short-term → fallback R2 for each item
    final_results, indices_to_compute, items_to_compute = await _cache_check(
        items, params, model_slug, model_action, debug_logger
    )

    computed_item_count = len(items_to_compute)

    # 2. If it's a 100% cache hit, we are done.
    if not indices_to_compute:
        # We skip calling the underlying func entirely
        debug_logger.debug(
            f"All {len(items)} items found in cache; skipping underlying function call."
        )
        return {"results": final_results}, 0

    # 3. If not, compute the missing items by calling the provided function
    debug_logger.debug(
        f"{len(items_to_compute)} items require computation. Calling underlying function with partial payload."
    )
    try:
        partial_response_obj = await compute_fn(items_to_compute, indices_to_compute)
    except Exception as e:
        debug_logger.debug(f"Error computing items: {e}")
        # Re-raise the exception to propagate errors properly
        raise
    debug_logger.debug("Underlying function returned. Starting cache postprocessing.")

    # Successful responses must have a "results" attribute (Pydantic model).
    # If the backend returns a plain dict (e.g. response.model_dump()), hasattr(..., "results")
    # is False, so we do NOT run _cache_postprocess and do NOT merge cached items with the
    # newly computed ones. The client then receives only the partial response (results for
    # items_to_compute), i.e. a wrong/incomplete result on partial cache hit. Callers that
    # return dicts should use _skip_cache=True or return a Pydantic response model so that
    # merge happens here.
    if not hasattr(partial_response_obj, "results"):
        debug_logger.debug(
            "Response missing 'results' attribute - treating as error, skipping cache"
        )
        return serialize_model(partial_response_obj, debug_logger), 0

    # 4. POST-PROCESS: Merge new results into the final list and update caches
    complete_response_dict = await _cache_postprocess(
        partial_response_obj,
        final_results,
        indices_to_compute,
        items_to_compute,
        params,
        model_slug,
        model_action,
        debug_logger,
    )

    # Return the final dict and the count of computed items
    return complete_response_dict, computed_item_count


# --- Internal Helper Functions for the Handler ---


async def _cache_check(
    items: list,
    params: Optional[dict[str, Any]],
    model_slug: str,
    model_action: str,
    debug_logger: DebugLogger,
):
    """
    Checks each item against the short-term cache, then falls back to R2.

    Items found in cache are placed in the `final_results` list; items not
    found remain for computation. The cache keys are derived from:
    (model_slug, model_action, item_dict, params).

    Args:
        items (list): The request's items to check for caching.
        params (dict): An optional set of parameters from the payload.
        model_slug (str): A string identifying the model, e.g. "esmfold".
        model_action (str): The model action, e.g. "predict".
        debug_logger (DebugLogCollector): A logger for capturing debug messages.

    Returns:
        tuple:
            final_results (list): A list of the same length as `items`, with cached data or None.
            indices_to_compute (list): The indices of items that are not cached.
            items_to_compute (list): The actual item objects that need computation.
    """
    final_results = [None] * len(items)
    indices_to_compute = []
    items_to_compute = []

    short_term_cache_updates = {}

    # Get the model-specific cache
    model_cache = get_model_cache(model_slug)

    debug_logger.debug(f"Starting cache check for {len(items)} items.")
    for i, item_obj in enumerate(items):
        # Convert item to dict for hashing
        item_dict = serialize_model(item_obj, debug_logger)
        item_key = build_item_cache_key(model_slug, model_action, item_dict, params)
        debug_logger.debug(f"Checking cache for item index {i} with key: {item_key}")

        # 1) Check short-term cache modal.Dict (per-model)
        # Use async get - cache failures should never cause API errors
        cached = await _safe_cache_get_aio(model_cache, item_key, debug_logger)
        if cached:
            debug_logger.debug(f"Short-term cache hit for key {item_key}.")

        # 2) Fallback to R2 cache
        if not cached:
            cached = fetch_from_r2(model_slug, model_action, item_key)
            if cached:
                # re-store in short-term
                debug_logger.debug(
                    f"R2 cache hit for key {item_key}. Storing back to short-term cache."
                )
                short_term_cache_updates[item_key] = cached

        if cached:
            final_results[i] = cached
        else:
            indices_to_compute.append(i)
            items_to_compute.append(item_obj)

    # Use async update - cache write failures should not affect the API response
    await _safe_cache_update_aio(
        model_cache, model_slug, short_term_cache_updates, debug_logger
    )

    return final_results, indices_to_compute, items_to_compute


async def _cache_postprocess(
    partial_response_obj: BaseModel,
    final_results: list,
    indices_to_compute: list,
    items_to_compute: list,
    params: Optional[dict[str, Any]],
    model_slug: str,
    model_action: str,
    debug_logger: DebugLogger,
) -> dict[str, list[Any]]:
    """
    Merges partial model results back into the final_results and writes them to cache.

    Only items that were missing from the cache are updated. This function
    expects `partial_response_obj` to have a `.results` attribute with the
    newly computed items.

    Args:
        partial_response_obj (Any): The return value from the underlying function call
            on the missing items. Usually a Pydantic model with a `results` list.
        final_results (list): A list that parallels the original items; placeholders
            are overwritten by newly computed results.
        indices_to_compute (list): Indices in `final_results` that needed computation.
        items_to_compute (list): The item data used for the partial function call.
        params (dict): The optional params from the original payload.
        model_slug (str): Identifies the model, e.g. "esmfold".
        model_action (str): The action name, e.g. "predict".
        debug_logger (DebugLogCollector): A logger for capturing debug messages.

    Returns:
        dict: Typically {"results": <list>} containing the fully assembled results.
    """
    # Only Pydantic-style responses (with .results attribute) reach here. Dict responses
    # are handled in process_with_cache and are not merged, so partial cache hit would
    # return incomplete results for those backends.
    if not hasattr(partial_response_obj, "results"):
        debug_logger.debug(
            f"Response from {model_action} missing 'results' attribute. "
            f"Type: {type(partial_response_obj).__name__}"
        )
        return {"results": final_results}

    new_items = partial_response_obj.results

    # Validate response
    if not isinstance(new_items, list):
        debug_logger.debug(
            f"Response 'results' is not a list. Type: {type(new_items).__name__}"
        )
        return {"results": final_results}

    if len(new_items) != len(items_to_compute):
        debug_logger.debug(
            f"Response has {len(new_items)} results but expected {len(items_to_compute)}. "
            "Returning partial results."
        )
        # fallback
        return {"results": final_results}

    short_term_cache_updates = {}

    # Get the model-specific cache
    model_cache = get_model_cache(model_slug)

    # Insert each computed item, store in caches
    for offset, newly_computed_item in enumerate(new_items):
        if offset >= len(indices_to_compute):
            break  # Safety check

        original_index = indices_to_compute[offset]

        # Build the item_key for caching
        item_dict = serialize_model(items_to_compute[offset], debug_logger)
        item_key = build_item_cache_key(model_slug, model_action, item_dict, params)

        # Convert newly_computed_item into pure-JSON
        newly_computed_item_dict = serialize_model(newly_computed_item, debug_logger)

        # Update results list
        final_results[original_index] = newly_computed_item_dict

        # Skip caching items with empty/null output fields — these are error or
        # null-embedding responses that would poison the cache for future requests.
        if not _result_item_is_cacheable(newly_computed_item_dict):
            debug_logger.debug(
                f"Skipping cache for item at original index {original_index}: "
                "all output fields are empty or null."
            )
            continue

        debug_logger.debug(
            f"Caching computed item at original index {original_index} with key {item_key}."
        )
        # Store in short-term cache modal.Dict (per-model)
        short_term_cache_updates[item_key] = newly_computed_item_dict
        # Store in R2 cache (always succeeds independently of short-term cache)
        store_in_r2(model_slug, model_action, item_key, newly_computed_item_dict)

    # Use async update - cache write failures should not affect the API response.
    # R2 write above ensures data is persisted even if short-term cache fails.
    await _safe_cache_update_aio(
        model_cache, model_slug, short_term_cache_updates, debug_logger
    )

    # Return a consistent final dict
    return {"results": final_results}
