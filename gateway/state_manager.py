import hashlib
from decimal import Decimal

import modal


class StateManagedDict:
    """
    Provides a safe, atomic interface for managing distributed state using
    a modal.Dict for storage and a modal.Queue for serializing writes.

    This pattern ensures that concurrent requests do not lead to race conditions
    when updating shared state counters. It handles key hashing internally.
    """

    def __init__(self, dict_name: str, queue_name: str):
        self._dict = modal.Dict.from_name(dict_name, create_if_missing=True)
        self._queue = modal.Queue.from_name(queue_name, create_if_missing=True)

    def _hash_key(self, key: str) -> str:
        """Hashes the raw key to avoid storing sensitive tokens."""
        return hashlib.sha256(key.encode()).hexdigest()

    # --- Public Methods for Gateway Logic ---

    def get(self, key: str, default=None):
        """
        Safely gets the current state for a given key. It converts all
        numeric string values back to Decimals.

        Args:
            key: The raw, unhashed key (e.g., API token).
            default: The value to return if the key is not found.

        Returns:
            The dictionary state for the given key with Decimal values.
        """
        hashed_key = self._hash_key(key)
        raw_state = self._dict.get(hashed_key, default)

        if not raw_state:
            return default

        # Convert string numbers back to Decimals for calculations
        hydrated_state = {}
        for k, v in raw_state.items():
            try:
                hydrated_state[k] = Decimal(v)
            except (ValueError, TypeError):
                hydrated_state[k] = v
        return hydrated_state

    def update(self, key: str, updates: dict):
        """
        Queues an incremental update to an item's state.

        Args:
            key: The raw, unhashed key.
            updates: A dictionary of counters to increment/decrement.
                     e.g., {'requests': 1, 'charges': Decimal('0.05')}
        """
        # Convert all values to strings to ensure serialization
        serializable_payload = {k: str(v) for k, v in updates.items()}
        self._queue.put(
            {
                "type": "update",
                "key": self._hash_key(key),
                "payload": serializable_payload,
            }
        )

    def force_set(self, key: str, new_state: dict):
        """
        Queues an operation to completely overwrite an item's state.

        Args:
            key: The raw, unhashed key.
            new_state: The new dictionary state to set.
        """
        # Convert all values to strings to ensure serialization
        serializable_payload = {k: str(v) for k, v in new_state.items()}
        self._queue.put(
            {
                "type": "set",
                "key": self._hash_key(key),
                "payload": serializable_payload,
            }
        )

    # --- Internal Method for the StateUpdater ---

    def _process_single_update(self, event: dict):
        """Processes a single event from the update queue."""
        key = event["key"]

        if event["type"] == "set":
            self._dict[key] = event["payload"]
        elif event["type"] == "update":
            current_state = self._dict.get(key, {})
            payload = event["payload"]
            for counter, delta_str in payload.items():
                delta = Decimal(delta_str)
                current_val = Decimal(current_state.get(counter, "0"))
                current_state[counter] = str(current_val + delta)
            self._dict[key] = current_state

    def run_processor_once(self, timeout: float = 1.0):
        """
        Pulls a batch of events from the queue and processes them.
        Returns the number of events processed.
        """
        try:
            # First, try non-blocking to process any available events quickly
            events = self._queue.get_many(count=100, block=False)
            if not events:
                # If no events available, do a short blocking wait
                events = self._queue.get_many(count=100, block=True, timeout=timeout)

            if not events:
                return 0

            for event in events:
                try:
                    self._process_single_update(event)
                except Exception as e:
                    print(f"Error processing event {event}: {e}")
                    # TODO: Add dead letter queue for failed events
            return len(events)
        except Exception as e:
            print(f"Error in queue processing: {e}")
            return 0
