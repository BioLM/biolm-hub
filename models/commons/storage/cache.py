import gzip
from typing import Optional

import orjson
from botocore.exceptions import ClientError

from models.commons.storage.r2 import get_r2_client
from models.commons.util.config import (
    cache_enabled,
    r2_bucket_name,
    r2_model_cache_dir,
)

"""
R2-specific cache operations for long-term storage.

This module handles the R2 (Cloudflare) layer of the caching system,
providing functions for building cache keys, fetching from R2, and storing to R2.
"""


def build_r2_key_for_item(
    model_slug: str, model_action: str, item_key: str, ext: str
) -> str:
    """
    Builds an R2 storage key path in a subfolder structure based on the item key.

    For example, if item_key is "f2bc8e123abc...", the resulting path would be:
    {r2_model_cache_dir}/{model_slug}/{model_action}/f/2/b/f2bc8e123abc...jsonbin

    Args:
        model_slug (str): The slug identifying the model, e.g. "ablang2".
        model_action (str): The action name, e.g. "predict" or "encode".
        item_key (str): The SHA256-based unique key for the item.
        ext (str): The file extension to use, e.g. ".jsonbin".

    Returns:
        str: The constructed R2 key path.
    """
    sub1 = item_key[0]
    sub2 = item_key[1]
    sub3 = item_key[2]
    filename = f"{item_key}{ext}"

    # e.g. r2://my-bucket/biolm-modal/model-cache/<slug>/<action>/f/2/b/<sha><ext>
    return (
        f"{r2_model_cache_dir}/{model_slug}/{model_action}/"
        f"{sub1}/{sub2}/{sub3}/{filename}"
    )


def fetch_from_r2(model_slug: str, model_action: str, item_key: str) -> Optional[dict]:
    """
    Fetch the item from {item_key}.jsonbin and auto-detect
    if it's gzip-compressed by magic bytes (0x1F, 0x8B).

    If no object is found for the given key, returns None.

    Args:
        model_slug (str): The model slug, e.g., "ablang2".
        model_action (str): The model action, e.g., "encode" or "predict".
        item_key (str): The SHA256-based unique key for the item.

    Returns:
        Optional[dict]: The decompressed JSON object, or None if not found.
    """
    # R2 response-cache tier is opt-in (BIOLM_CACHE_ENABLED). Off => cache miss.
    if not cache_enabled():
        return None

    r2_client = get_r2_client()
    obj_key = build_r2_key_for_item(model_slug, model_action, item_key, ext=".jsonbin")

    try:
        response = r2_client.get_object(Bucket=r2_bucket_name, Key=obj_key)
        data = response["Body"].read()

        # Sniff for gzip
        # Gzip "magic number" is the bytes [0x1F, 0x8B]
        if len(data) >= 2 and data[0] == 0x1F and data[1] == 0x8B:
            # It's gzipped
            decompressed = gzip.decompress(data)
            return orjson.loads(decompressed)
        else:
            # It's plain JSON
            return orjson.loads(data)

    except r2_client.exceptions.NoSuchKey:
        return None
    except Exception as exc:
        print(f"[WARNING] fetch_from_r2: error reading {obj_key}. {exc}")
        return None


def store_in_r2(model_slug: str, model_action: str, item_key: str, value: dict) -> None:
    """
    Serialize `value` to JSON. If it's >= 2KB, gzip it.
    Store everything as *.jsonbin, so we only need one extension.

    Args:
        model_slug (str): The model slug, e.g., "ablang2".
        model_action (str): The action name, e.g., "predict" or "encode".
        item_key (str): The SHA256-based unique key for the item.
        value (dict): The data to be compressed and stored.

    Returns:
        None
    """
    # R2 response-cache tier is opt-in (BIOLM_CACHE_ENABLED). Off => no write.
    if not cache_enabled():
        return

    r2_client = get_r2_client()

    # Serialize to JSON bytes
    json_bytes = orjson.dumps(value)

    # Decide whether to gzip
    if len(json_bytes) < 2000:
        body = json_bytes
    else:
        body = gzip.compress(json_bytes)

    # Use single extension, .jsonbin, for both plain and gzipped files
    obj_key = build_r2_key_for_item(model_slug, model_action, item_key, ext=".jsonbin")

    # Try uploading
    try:
        r2_client.put_object(
            Bucket=r2_bucket_name,
            Key=obj_key,
            Body=body,
            ContentType="application/json",
        )
    except Exception as exc:
        print(f"[WARNING] store_in_r2: failed storing {obj_key}. {exc}")


def clear_r2_cache(
    model_slug: Optional[str] = None,
    model_action: Optional[str] = None,
    force: bool = False,
) -> None:
    """
    Deletes matching cached objects from Cloudflare R2.

    If both model_slug and model_action are omitted, clears everything under
    the r2_model_cache_dir. If only model_slug is provided, clears that slug,
    and if both are provided, clears only the given action.

    Args:
        model_slug (Optional[str]): The slug identifying the model.
        model_action (Optional[str]): The action name within that model.
        force (bool): If True, proceed without prompting for confirmation.

    Returns:
        None
    """
    if not force:
        print("Not deleting from R2 cache. Set force=True to proceed.")
        return

    base_prefix = f"{r2_model_cache_dir}"
    if model_slug:
        base_prefix += f"/{model_slug}"
        if model_action:
            base_prefix += f"/{model_action}"

    r2_client = get_r2_client()
    paginator = r2_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=r2_bucket_name, Prefix=base_prefix)
    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            print(f"Deleting from R2: {key}")
            try:
                r2_client.delete_object(Bucket=r2_bucket_name, Key=key)
            except ClientError as exc:
                print(f"[WARNING] clear_r2_cache: failed deleting {key}. {exc}")


def get_items_added_by_day(
    model_slug: Optional[str] = None,
    model_action: Optional[str] = None,
    n_days: int = 7,
) -> list[tuple[str, int]]:
    """
    Returns a list of (date_string, count) for how many objects
    were added (or last modified) each day within the last `n_days`.

    If `model_slug` or `model_action` are specified, we limit
    to only those subfolders. Otherwise, we scan all items
    under r2_model_cache_dir.
    """
    from datetime import datetime, timedelta

    r2_client = get_r2_client()

    # 1) Build the prefix (base folder)
    base_prefix = r2_model_cache_dir  # e.g. "model-cache"
    if model_slug:
        base_prefix += f"/{model_slug}"
        if model_action:
            base_prefix += f"/{model_action}"

    # 2) Determine date range
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=n_days - 1)

    # 3) Use a dict to collect counts, keyed by date
    day_counts = {}

    paginator = r2_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=r2_bucket_name, Prefix=base_prefix)

    for page in pages:
        for obj in page.get("Contents", []):
            # 'LastModified' is a datetime object (UTC) for S3/R2
            last_modified_dt = obj["LastModified"]  # e.g. 2023-09-07 12:34:56+00:00
            last_modified_date = last_modified_dt.date()

            # Only count it if it's within our (start_date..end_date) window
            if start_date <= last_modified_date <= end_date:
                day_counts[last_modified_date] = (
                    day_counts.get(last_modified_date, 0) + 1
                )

    # 4) Build a list of (day_str, count) in ascending date order
    results = []
    for i in range(n_days):
        day = start_date + timedelta(days=i)
        day_str = day.isoformat()  # e.g. "2023-09-07"
        count = day_counts.get(day, 0)
        results.append((day_str, count))

    return results
