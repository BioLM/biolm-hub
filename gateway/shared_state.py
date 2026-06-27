import modal

from gateway.state_manager import StateManagedDict

# --- Shared State Objects ---
# These are imported by both app.py and auth.py to avoid circular imports

# Persistent, shared dictionary for passport data (token -> passport)
passport_cache = modal.Dict.from_name("passport-cache", create_if_missing=True)

# The main state manager for tracking usage counters atomically
user_usage_manager = StateManagedDict(
    dict_name="biolm-user-usage-state",
    queue_name="biolm-usage-update-queue",
)
