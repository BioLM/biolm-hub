import random
import string
import time

import pytest

from models.commons.core.caching import get_model_cache
from models.commons.storage.cache import (
    clear_r2_cache,
    fetch_from_r2,
    store_in_r2,
)
from models.commons.storage.r2 import r2_credentials_present

# The R2-backed tests below need real R2 credentials; skip them in the
# creds-free unit environment (they run as integration where creds exist).
_needs_r2 = pytest.mark.skipif(
    not r2_credentials_present(), reason="requires R2 credentials"
)

# A test-specific model slug/action so we know what's safe to remove.
TEST_MODEL_SLUG = "z_test_model_slug"
TEST_MODEL_ACTION = "z_test_model_action"

# Get the test-specific cache (per-model architecture)
short_term_model_cache = get_model_cache(TEST_MODEL_SLUG)


def _safe_pop_from_short_term_model_cache(key: str):
    """
    A small helper to avoid errors with 'pop(key, default)'.
    modal.Dict.pop() doesn't allow a second argument, so check membership first.
    """
    if short_term_model_cache.contains(key):
        short_term_model_cache.pop(key)


@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown():
    """
    Runs ONCE before all tests in this file, and ONCE after.
    Ensures we clean up data in short-term and R2 that belongs to our test slug.

    Uses scope="module" (not "session") so teardown errors don't propagate to
    unrelated tests in other files when running with pytest-xdist.
    """
    print(
        "\n[setup_and_teardown] BEGIN: Clearing leftover data from any previous runs."
    )
    # 1) Clear the test model's short-term cache entirely.
    # With per-model caches, we have a dedicated cache for TEST_MODEL_SLUG
    # so we can safely clear() without affecting other models.
    try:
        short_term_model_cache.clear()
        print(f"  Cleared short-term cache for {TEST_MODEL_SLUG}")
    except Exception as e:
        print(f"  Warning: Could not clear short-term cache: {e}")

    # 2) Clear from R2 for just our slug
    try:
        clear_r2_cache(model_slug=TEST_MODEL_SLUG, model_action=None, force=True)
    except Exception as e:
        print(f"  Warning: Could not clear R2 cache during setup: {e}")
    print("[setup_and_teardown] DONE with initial cleanup.\n")

    yield  # run tests

    print("\n[setup_and_teardown] BEGIN: Final cleanup after tests.")
    # 1) Clear the test model's short-term cache
    try:
        short_term_model_cache.clear()
        print(f"  Cleared short-term cache for {TEST_MODEL_SLUG}")
    except Exception as e:
        print(f"  Warning: Could not clear short-term cache: {e}")

    # 2) Clear from R2 for just our slug
    try:
        clear_r2_cache(model_slug=TEST_MODEL_SLUG, model_action=None, force=True)
    except Exception as e:
        print(f"  Warning: Could not clear R2 cache during teardown: {e}")
    print("[setup_and_teardown] DONE with final cleanup.\n")


### 1) Basic short-term cache tests


def test_short_term_model_cache_crud():
    print("\n--- test_short_term_model_cache_crud ---")

    test_key = "z_test_short_term_crud"
    test_payload = {
        "slug": TEST_MODEL_SLUG,
        "msg": "Hello from short-term cache CRUD test.",
    }

    # Ensure no prior leftover
    _safe_pop_from_short_term_model_cache(test_key)

    # 1) Fetch should be None
    assert short_term_model_cache.get(test_key) is None

    # 2) Store
    short_term_model_cache[test_key] = test_payload

    # 3) Fetch should be present
    got = short_term_model_cache.get(test_key)
    assert got == test_payload, f"Expected {test_payload}, got {got}"

    # 4) Clear it manually
    _safe_pop_from_short_term_model_cache(test_key)
    # Double-check
    assert short_term_model_cache.get(test_key) is None, "Should be removed now"


### 2) Basic R2 cache tests


@_needs_r2
def test_r2_cache_crud():
    print("\n--- test_r2_cache_crud ---")
    # We'll store and fetch from the real R2.
    # We'll use our test slug + some random item_key

    item_key = "z_r2_test_crud"
    payload = {"slug": TEST_MODEL_SLUG, "msg": "Hello from R2 CRUD test."}

    # Ensure not present initially
    assert fetch_from_r2(TEST_MODEL_SLUG, TEST_MODEL_ACTION, item_key) is None

    # Store
    store_in_r2(TEST_MODEL_SLUG, TEST_MODEL_ACTION, item_key, payload)

    # Fetch with retry for eventual consistency (R2 may have slight delay)
    fetched = None
    for _attempt in range(5):
        fetched = fetch_from_r2(TEST_MODEL_SLUG, TEST_MODEL_ACTION, item_key)
        if fetched is not None:
            break
        time.sleep(0.5)  # Wait 0.5s between retries

    assert fetched == payload, f"Expected {payload}, got {fetched}"

    # Cleanup that item so subsequent tests don't see it
    clear_r2_cache(
        model_slug=TEST_MODEL_SLUG, model_action=TEST_MODEL_ACTION, force=True
    )
    # Verify cleared
    assert fetch_from_r2(TEST_MODEL_SLUG, TEST_MODEL_ACTION, item_key) is None


### 3) Performance / RPS tests


def random_string(length: int) -> str:
    """Generate a random string of given length."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


@pytest.mark.parametrize("payload_size", [100, 500, 2000])
def test_short_term_model_cache_performance(payload_size):
    """
    Measure raw writes/reads to short-term cache (Modal Dict) for the specified payload size.
    We'll do 100 writes and 100 reads, then print out RPS.
    """
    print(
        f"\n--- test_short_term_model_cache_performance with payload_size={payload_size} ---"
    )

    big_str = random_string(payload_size)
    payload = {"slug": TEST_MODEL_SLUG, "data": big_str}

    N = 5

    # -- WRITES --
    start = time.time()
    for i in range(N):
        key = f"z_perf_st_{payload_size}_{i}"
        short_term_model_cache[key] = payload
    end = time.time()
    write_duration = end - start
    write_rps = N / write_duration if write_duration else float("inf")

    # -- READS --
    start = time.time()
    for i in range(N):
        key = f"z_perf_st_{payload_size}_{i}"
        _ = short_term_model_cache.get(key)
    end = time.time()
    read_duration = end - start
    read_rps = N / read_duration if read_duration else float("inf")

    print(
        f"Short-term cache performance for payload={payload_size} chars => "
        f"writes: {write_rps:.2f} rps, reads: {read_rps:.2f} rps"
    )


@_needs_r2
@pytest.mark.parametrize("payload_size", [100, 500, 2000])
def test_r2_cache_performance(payload_size):
    """
    Measure raw writes/reads to R2 for the specified payload size.
    We'll do 100 writes and 100 reads, then print out RPS.
    """
    print(f"\n--- test_r2_cache_performance with payload_size={payload_size} ---")

    big_str = random_string(payload_size)
    payload = {"slug": TEST_MODEL_SLUG, "data": big_str}
    N = 5

    # -- WRITES --
    start = time.time()
    for i in range(N):
        item_key = f"z_perf_r2_{payload_size}_{i}"
        store_in_r2(TEST_MODEL_SLUG, TEST_MODEL_ACTION, item_key, payload)
    end = time.time()
    write_duration = end - start
    write_rps = N / write_duration if write_duration else float("inf")

    # -- READS --
    start = time.time()
    for i in range(N):
        item_key = f"z_perf_r2_{payload_size}_{i}"
        _ = fetch_from_r2(TEST_MODEL_SLUG, TEST_MODEL_ACTION, item_key)
    end = time.time()
    read_duration = end - start
    read_rps = N / read_duration if read_duration else float("inf")

    print(
        f"R2 cache performance for payload={payload_size} chars => "
        f"writes: {write_rps:.2f} rps, reads: {read_rps:.2f} rps"
    )


# Usage:
#   pytest models/commons/storage/test_cache.py -v -s
