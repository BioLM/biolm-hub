import json
import os
import subprocess
import threading
import time
import uuid
from contextlib import contextmanager
from typing import Optional

import redis

from models.commons.billing.redis_client import (
    close_redis_client,
    initialize_redis_client,
    logger,
)

"""
Modal billing service for tracking container resource usage.

This module provides the ModalBillingService class that handles continuous
billing with precise timing, prevents double billing, and provides robust
error handling with offline accumulation.
"""

# --- Billing Configuration Defaults ---
DEFAULT_BILLING_INTERVAL_SECONDS = 0.45
DEFAULT_SCALEDOWN_PENALTY_SECONDS = 1.0
REDIS_KEY_EXPIRATION_DAYS = 7
CONTAINER_INACTIVITY_TIMEOUT_SECONDS = 120.0

# --- Detection & Validation Thresholds ---
# Threshold for detecting "large gaps" between billing increments (seconds).
# Gaps exceeding this indicate potential container suspension/migration.
LARGE_GAP_THRESHOLD_SECONDS = 10.0
# Threshold for detecting host PID 1 uptime vs container PID 1 (seconds).
HOST_PID_DETECTION_THRESHOLD_SECONDS = 30.0
# Maximum container startup time cap to prevent over-billing (seconds).
MAX_STARTUP_TIME_SECONDS = 300.0
# Interval between container validity checks in the billing loop (seconds).
CONTAINER_VALIDITY_CHECK_INTERVAL_SECONDS = 5.0

# --- Operational Constants ---
PS_COMMAND_TIMEOUT_SECONDS = 2.0
REDIS_RETRY_INTERVAL_SECONDS = 3.0
BILLING_STATS_LOG_INTERVAL_SECONDS = 30


SNAPSHOT_UPTIME_FILE = "/var/snapshot_uptime"


def parse_snapshot_uptime_file() -> Optional[dict]:
    """Parse the snapshot uptime file, returning structured data or None if not found.

    Handles both JSON format (new) and plain float (old) formats.

    Returns:
        dict with keys: uptime_seconds (float), container_id (str|None),
        timestamp_utc (float|None), format ("json"|"plain")
        or None if file doesn't exist or can't be parsed.
    """
    if not os.path.exists(SNAPSHOT_UPTIME_FILE):
        return None
    try:
        with open(SNAPSHOT_UPTIME_FILE) as f:
            content = f.read().strip()
        try:
            data = json.loads(content)
            return {
                "uptime_seconds": data.get("uptime_seconds"),
                "container_id": data.get("container_id"),
                "timestamp_utc": data.get("timestamp_utc"),
                "format": "json",
            }
        except (json.JSONDecodeError, ValueError, AttributeError, TypeError):
            return {
                "uptime_seconds": float(content),
                "container_id": None,
                "timestamp_utc": None,
                "format": "plain",
            }
    except (FileNotFoundError, ValueError) as e:
        logger.warning(f"Could not read snapshot uptime file: {e}")
        return None


class BillingService:
    """
    Thread-safe background billing service for Modal containers.

    Handles continuous billing with precise timing, prevents double billing,
    and provides robust error handling with offline accumulation.
    """

    def __init__(
        self,
        app_name: str,
        class_name: str,
        username: str = "default_user",
        resource_metadata: Optional[dict] = None,
    ):
        """
        Initialize billing service.

        Args:
            app_name: Name of the Modal app
            class_name: Name of the container class
            username: Username for billing tracking
            resource_metadata: Optional metadata about resources (GPU, memory, etc.)
        """
        self.app_name = app_name
        self.class_name = class_name
        self.username = username
        self.resource_metadata = resource_metadata or {}

        # Thread synchronization
        self._state_lock = threading.RLock()  # Re-entrant lock for nested operations
        self._redis_lock = threading.RLock()  # Separate lock for Redis operations
        self._stop_event = threading.Event()

        # Billing state - protected by _state_lock
        self._billing_thread: Optional[threading.Thread] = None
        self._is_started = False
        self._is_stopped = False
        self._container_id: Optional[str] = None
        self._start_time: Optional[float] = None
        self._container_start_time: Optional[float] = (
            None  # Actual container start (before Redis)
        )
        self._last_billing_time: Optional[float] = None

        # Redis state - protected by _redis_lock
        self._redis_client: Optional[redis.Redis] = None
        self._last_successful_redis_time: Optional[float] = None

        # Billing configuration
        self.billing_interval = DEFAULT_BILLING_INTERVAL_SECONDS
        self.scaledown_penalty = DEFAULT_SCALEDOWN_PENALTY_SECONDS
        self.key_expiration_days = REDIS_KEY_EXPIRATION_DAYS

        # Offline accumulation - protected by _state_lock
        self._accumulated_usage = 0.0

        # Track total billed time for debugging over-billing issues
        self._total_billed_time = 0.0

        # Thread-safe storage for current action and protocol/analysis ID
        # Uses thread ID as key so billing thread can see actions from method execution threads
        self._action_context: dict[int, dict[str, Optional[str]]] = {}
        self._action_context_lock = threading.RLock()

        # Persistent "last active" fields that persist even after methods complete
        # This ensures the billing thread can still retrieve actions after method cleanup
        self._last_active_action: Optional[str] = None
        self._last_active_protocol_id: Optional[str] = None

        # Unique tracking file per instance
        self._tracking_file = "/billing_started.touch"

        # Container validity and timeout tracking
        self._last_activity_time: Optional[float] = None
        self._container_timeout_seconds = CONTAINER_INACTIVITY_TIMEOUT_SECONDS

    @contextmanager
    def _get_redis_client(self):
        """Thread-safe Redis client context manager."""
        with self._redis_lock:
            if self._redis_client is None:
                self._initialize_redis()
            yield self._redis_client

    def _initialize_redis(self) -> bool:
        """Initialize Redis connection using Modal secrets. Must be called with _redis_lock held."""
        redis_client, success = initialize_redis_client()
        self._redis_client = redis_client
        if success:
            self._last_successful_redis_time = time.time()
        return success

    def _parse_ps_etime(self, etime_str: str) -> Optional[float]:
        """
        Parse ps -o etime= output into seconds.

        Handles formats:
        - "HH:MM:SS" (e.g., "01:23:45" = 5025 seconds)
        - "MM:SS" (e.g., "23:45" = 1425 seconds)
        - "SS" (e.g., "45" = 45 seconds)

        Returns:
            Elapsed time in seconds, or None if parsing fails
        """
        try:
            etime_str = etime_str.strip()
            parts = etime_str.split(":")

            if len(parts) == 3:
                # Format: HH:MM:SS
                hours, minutes, seconds = map(int, parts)
                total_seconds = hours * 3600 + minutes * 60 + seconds
                logger.debug(
                    f"Parsed ps etime '{etime_str}' as {total_seconds:.6f}s (HH:MM:SS format)"
                )
                return float(total_seconds)
            elif len(parts) == 2:
                # Format: MM:SS
                minutes, seconds = map(int, parts)
                total_seconds = minutes * 60 + seconds
                logger.debug(
                    f"Parsed ps etime '{etime_str}' as {total_seconds:.6f}s (MM:SS format)"
                )
                return float(total_seconds)
            elif len(parts) == 1:
                # Format: SS
                total_seconds = int(parts[0])
                logger.debug(
                    f"Parsed ps etime '{etime_str}' as {total_seconds:.6f}s (SS format)"
                )
                return float(total_seconds)
            else:
                logger.warning(f"Unexpected ps etime format: '{etime_str}'")
                return None
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse ps etime '{etime_str}': {e}")
            return None

    def _get_uptime_via_ps(self) -> Optional[float]:
        """
        Get container uptime using ps -o etime= -p 1 (PID 1 elapsed time).

        This queries the elapsed time of PID 1 (init process), which should
        represent the container's actual uptime from when the container started,
        regardless of whether it was created from scratch, restored from a snapshot, etc.

        Returns:
            Uptime in seconds, or None if ps command fails
        """
        try:
            result = subprocess.run(
                ["ps", "-o", "etime=", "-p", "1"],
                capture_output=True,
                text=True,
                timeout=PS_COMMAND_TIMEOUT_SECONDS,
                check=False,
            )

            if result.returncode == 0 and result.stdout.strip():
                etime_str = result.stdout.strip()
                uptime = self._parse_ps_etime(etime_str)
                if uptime is not None:
                    logger.info(
                        f"📊 Got container uptime via ps -o etime= -p 1: {uptime:.6f}s (output: '{etime_str}')"
                    )
                    return uptime
                else:
                    logger.warning(f"Failed to parse ps output: '{etime_str}'")
            else:
                logger.warning(
                    f"ps command failed (returncode={result.returncode}, stderr={result.stderr})"
                )
        except subprocess.TimeoutExpired:
            logger.warning("ps command timed out after 2 seconds")
        except FileNotFoundError:
            logger.warning("ps command not found in PATH")
        except Exception as e:
            logger.warning(f"Error running ps command: {e}")

        return None

    def _get_uptime_via_stat_proc1(self) -> Optional[float]:
        """
        Get container uptime using stat /proc/1/ (directory creation time).

        The /proc/1/ directory's creation time should reflect when PID 1 started,
        which corresponds to container creation time.

        Returns:
            Uptime in seconds, or None if stat fails
        """
        try:
            proc1_stat = os.stat("/proc/1/")
            # Get creation time (st_ctime on most systems, but st_birthtime on macOS)
            # For Linux containers, st_ctime is the last metadata change time,
            # which should be close to creation time for /proc/1/
            creation_time = proc1_stat.st_ctime

            current_time = time.time()
            uptime = current_time - creation_time

            if uptime < 0:
                logger.warning(
                    f"stat /proc/1/ returned negative uptime: {uptime:.6f}s (current={current_time:.6f}, creation={creation_time:.6f})"
                )
                return None

            logger.info(
                f"📊 Got container uptime via stat /proc/1/: {uptime:.6f}s (creation_time={creation_time:.6f}, current_time={current_time:.6f})"
            )
            return uptime
        except (FileNotFoundError, OSError) as e:
            logger.warning(f"Could not stat /proc/1/: {e}")
        except Exception as e:
            logger.warning(f"Error getting uptime via stat /proc/1/: {e}")

        return None

    def _get_uptime_via_proc_uptime(self) -> Optional[float]:
        """
        Get container uptime using /proc/uptime (system uptime).

        This is the original method, kept as a fallback. May be unreliable
        for memory snapshot containers or containers with long initialization.

        Returns:
            Uptime in seconds, or None if /proc/uptime cannot be read
        """
        try:
            with open("/proc/uptime") as f:
                current_uptime_seconds = float(f.read().split()[0])
            logger.info(
                f"📊 Got container uptime via /proc/uptime: {current_uptime_seconds:.6f}s"
            )
            return current_uptime_seconds
        except (FileNotFoundError, ValueError, IndexError) as e:
            logger.warning(f"Could not read /proc/uptime: {e}")
            return None

    def _read_snapshot_uptime_file(self) -> Optional[float]:
        """Read and parse snapshot uptime file, return uptime value if found."""
        snapshot_data = parse_snapshot_uptime_file()
        if snapshot_data is None:
            return None
        uptime = snapshot_data["uptime_seconds"]
        if snapshot_data["format"] == "json":
            logger.info(
                f"📸 Snapshot file found (JSON): uptime={uptime:.6f}s, "
                f"container_id={snapshot_data['container_id'][:50] if snapshot_data['container_id'] else None}, "
                f"timestamp={snapshot_data['timestamp_utc']:.6f}"
            )
        else:
            logger.info(f"📸 Snapshot file found (old format): uptime={uptime:.6f}s")
        return uptime

    def _try_all_uptime_methods(
        self,
    ) -> tuple[dict[str, Optional[float]], Optional[float], Optional[str]]:
        """
        Try all uptime methods and return results.

        Returns:
            Tuple of (method_results dict, raw_uptime, method_used)
        """
        uptime_methods = [
            ("ps -o etime= -p 1", self._get_uptime_via_ps),
            ("stat /proc/1/", self._get_uptime_via_stat_proc1),
            ("/proc/uptime", self._get_uptime_via_proc_uptime),
        ]

        # Try all methods and log their values for debugging
        method_results = {}
        raw_uptime = None
        method_used = None

        for method_name, method_func in uptime_methods:
            try:
                result = method_func()
                method_results[method_name] = result
                if result is not None and result >= 0:
                    logger.debug(f"📊 {method_name} returned: {result:.6f}s")
                    if raw_uptime is None:  # Use first valid result
                        raw_uptime = result
                        method_used = method_name
                else:
                    logger.debug(f"❌ {method_name} returned invalid value: {result}")
            except Exception as e:
                logger.warning(f"❌ {method_name} raised exception: {e}")
                method_results[method_name] = None
                continue

        # Log all method results for debugging
        logger.info(
            f"🔍 Uptime method results: {', '.join([f'{k}={v:.6f}s' if v is not None else f'{k}=None' for k, v in method_results.items()])}"
        )

        return method_results, raw_uptime, method_used

    def _select_best_uptime_value(
        self,
        method_results: dict[str, Optional[float]],
        raw_uptime: Optional[float],
        method_used: Optional[str],
        snapshot_uptime_value: Optional[float],
    ) -> float:
        """
        Select best uptime value from method results, handling snapshot restore cases.

        Returns:
            Selected uptime in seconds
        """
        if raw_uptime is None:
            logger.error("❌ All uptime methods failed, returning 0.0")
            return 0.0

        # Special handling for snapshot restores
        # If snapshot file exists and ps returned a very high value (>30s), it's likely host PID 1 uptime
        # In that case, use snapshot file value or a small default
        # Lowered threshold from 60s to 30s to catch more edge cases
        if snapshot_uptime_value is not None:
            # Check if uptime is significantly higher than snapshot file value (e.g., > 3x)
            # This catches cases where host PID 1 uptime is between 30-60s
            if raw_uptime > HOST_PID_DETECTION_THRESHOLD_SECONDS and (
                raw_uptime > snapshot_uptime_value * 3.0 or raw_uptime > 60.0
            ):
                logger.warning(
                    f"⚠️  Detected likely host PID 1 uptime: {raw_uptime:.6f}s (method: {method_used}). "
                    f"Snapshot file value: {snapshot_uptime_value:.6f}s (ratio: {raw_uptime / snapshot_uptime_value:.2f}x). "
                    f"Using snapshot file value as container uptime estimate."
                )
                # Use snapshot file value as a reasonable estimate of container startup time
                # This represents the time it took to create the snapshot originally
                raw_uptime = snapshot_uptime_value
                method_used = "snapshot_file (fallback)"
            else:
                logger.info(
                    f"✅ Snapshot file exists but ps returned reasonable value: {raw_uptime:.6f}s. "
                    f"Snapshot file value: {snapshot_uptime_value:.6f}s. Using ps value."
                )
        else:
            # No snapshot file - this is snapshot creation or fresh container
            # If ps returned a very high value (>30s), it's likely host PID 1 uptime, not container uptime
            # Cap it at a reasonable value to prevent over-billing
            if raw_uptime > HOST_PID_DETECTION_THRESHOLD_SECONDS:
                logger.warning(
                    f"⚠️  Detected likely host PID 1 uptime during snapshot creation: {raw_uptime:.6f}s "
                    f"(method: {method_used}). No snapshot file exists. Capping at {HOST_PID_DETECTION_THRESHOLD_SECONDS}s to prevent over-billing."
                )
                raw_uptime = HOST_PID_DETECTION_THRESHOLD_SECONDS
                method_used = (
                    f"{method_used} (capped at {HOST_PID_DETECTION_THRESHOLD_SECONDS}s)"
                )

        # Apply safety cap to prevent over-billing for unreasonably long uptimes
        if raw_uptime > MAX_STARTUP_TIME_SECONDS:
            logger.warning(
                f"⚠️  Capping uptime from {raw_uptime:.6f}s to {MAX_STARTUP_TIME_SECONDS:.1f}s "
                f"(method: {method_used}) to prevent over-billing"
            )
            raw_uptime = MAX_STARTUP_TIME_SECONDS

        logger.info(
            f"✅ Final container uptime: {raw_uptime:.6f}s (method: {method_used})"
        )
        return raw_uptime

    def _get_container_uptime(self) -> float:
        """
        Get container uptime in seconds using multiple methods for reliability.

        Tries methods in order:
        1. ps -o etime= -p 1 (PID 1 elapsed time - most reliable, gives actual container uptime)
        2. stat /proc/1/ (directory creation time - alternative, gives actual container start time)
        3. /proc/uptime (system uptime - fallback, may be less accurate)

        For snapshot restores, ps may return host PID 1 uptime instead of container uptime.
        In that case, we check the snapshot file and use a small default value.

        Returns:
            Uptime in seconds, or 0.0 if unable to determine
        """
        snapshot_uptime_value = self._read_snapshot_uptime_file()
        method_results, raw_uptime, method_used = self._try_all_uptime_methods()
        return self._select_best_uptime_value(
            method_results, raw_uptime, method_used, snapshot_uptime_value
        )

    def _get_restore_uptime(self) -> float:
        """
        Get accurate uptime for snapshot restore scenarios.

        For restores, do NOT use early_uptime (it's from creation phase).
        Use snapshot file value or current_uptime directly.

        Returns:
            Uptime in seconds, preferring snapshot file > _get_container_uptime()
        """
        is_snapshot_restore = getattr(self, "_is_snapshot_restore", False)

        # For restores, skip early_uptime (it's from creation, not restore)
        # early_uptime is only valid for creation phase
        if is_snapshot_restore:
            # Restore confirmed - don't use early_uptime from creation
            # Proceed directly to snapshot file or current_uptime
            pass
        else:
            # Not confirmed as restore yet - could be creation phase
            # early_uptime might be valid here, but this method shouldn't be called
            # for creation. Log a warning if early_uptime exists.
            early_uptime = getattr(self, "_early_uptime", None)
            if early_uptime is not None and early_uptime > 0:
                logger.warning(
                    f"⚠️  _get_restore_uptime() called but _is_snapshot_restore=False. "
                    f"early_uptime={early_uptime:.6f}s exists but may be from creation phase."
                )

        # Fall back to snapshot file value
        snapshot_data = parse_snapshot_uptime_file()
        if snapshot_data is not None:
            uptime = snapshot_data["uptime_seconds"]
            if uptime is not None:
                fmt = snapshot_data["format"]
                suffix = f" ({fmt} format)" if fmt == "plain" else ""
                logger.info(
                    f"📸 Using snapshot file value{suffix} for restore: {uptime:.6f}s"
                )
                return uptime

        # Last resort: use _get_container_uptime() (already handles host PID 1 detection)
        current_uptime = self._get_container_uptime()
        logger.info(
            f"📸 Using _get_container_uptime() for restore: {current_uptime:.6f}s"
        )
        return current_uptime

    def _create_unique_container_id(self) -> str:
        """Create unique container ID with UUID to prevent collisions."""
        # Use UUID + timestamp + process ID for absolute uniqueness
        unique_id = f"{uuid.uuid4().hex[:8]}-{int(time.time() * 1000000)}-{os.getpid()}"
        return f"{self.username}__{self.app_name}-{unique_id}__{self.class_name}"

    def set_current_action(self, action: Optional[str]) -> None:
        """
        Set the current action for this thread (called when method is invoked).

        Args:
            action: Action name (e.g., 'encode', 'predict', 'generate') or None to clear
        """
        thread_id = threading.get_ident()
        with self._action_context_lock:
            if thread_id not in self._action_context:
                self._action_context[thread_id] = {
                    "current_action": None,
                    "protocol_id": None,
                }
            old_action = self._action_context[thread_id].get("current_action")
            self._action_context[thread_id]["current_action"] = action
            # Update persistent "last active" field for billing thread fallback
            # This ensures the billing loop can read the action even after the method completes
            if action is not None:
                self._last_active_action = action
                logger.info(
                    f"[BILLING] [ACTION] Set current_action: {action} (was: {old_action}, container: {self._container_id})"
                )
            elif action != old_action:
                # Only log when clearing if it's a change (not on initial None)
                logger.debug(
                    f"[BILLING] [ACTION] Cleared current_action (was: {old_action}, container: {self._container_id})"
                )
                # If clearing an action, check if any other threads have active actions
                # If not, clear _last_active_action to stop billing after method completion
                has_other_active_action = False
                for tid, thread_data in self._action_context.items():
                    if tid != thread_id and thread_data.get("current_action"):
                        has_other_active_action = True
                        break
                if not has_other_active_action:
                    self._last_active_action = None
                    logger.debug(
                        f"[BILLING] [ACTION] Cleared _last_active_action (no other active actions, container: {self._container_id})"
                    )

    def get_current_action(self) -> Optional[str]:
        """
        Get the current action from any active thread.

        Returns the action from the most recently active thread (for billing thread access).
        If multiple threads have actions, returns the first non-None action found.
        Falls back to persistent "last active" field if no active thread action is found.

        This ensures that even if a method completes very quickly (< 1 second),
        the billing loop can still read the action that was executed.

        Returns:
            Current action name or None if no action is set
        """
        with self._action_context_lock:
            # Return first non-None action from any thread (most common case: single active method)
            for thread_data in self._action_context.values():
                action = thread_data.get("current_action")
                if action:
                    logger.debug(
                        f"[BILLING] [ACTION] Retrieved current_action: {action} (container: {self._container_id})"
                    )
                    return action
            # Fall back to persistent "last active" field for billing thread access after method cleanup
            # This is critical for fast method calls that complete before the billing loop reads them
            if self._last_active_action:
                logger.debug(
                    f"[BILLING] [ACTION] Using last_active_action: {self._last_active_action} (container: {self._container_id})"
                )
                return self._last_active_action
            logger.debug(
                f"[BILLING] [ACTION] No current_action found (returning None, container: {self._container_id})"
            )
            return None

    def set_protocol_id(self, protocol_id: Optional[str]) -> None:
        """
        Set the protocol/analysis/workflow ID for this thread (for billing slicing).

        This allows tracking billing by protocol/analysis ID without affecting container pooling.
        Unlike modal.parameter, this doesn't create separate container pools.

        Args:
            protocol_id: Protocol/analysis/workflow ID (e.g., 'analysis_123', 'protocol_abc') or None to clear
        """
        thread_id = threading.get_ident()
        with self._action_context_lock:
            if thread_id not in self._action_context:
                self._action_context[thread_id] = {
                    "current_action": None,
                    "protocol_id": None,
                }
            self._action_context[thread_id]["protocol_id"] = protocol_id
            # Update persistent "last active" field for billing thread fallback
            if protocol_id is not None:
                self._last_active_protocol_id = protocol_id

    def get_protocol_id(self) -> Optional[str]:
        """
        Get the protocol/analysis/workflow ID from any active thread.

        Returns the protocol_id from the most recently active thread (for billing thread access).
        Falls back to persistent "last active" field if no active thread protocol_id is found.

        Returns:
            Current protocol ID or None if not set
        """
        with self._action_context_lock:
            # Return first non-None protocol_id from any thread
            for thread_data in self._action_context.values():
                protocol_id = thread_data.get("protocol_id")
                if protocol_id:
                    return protocol_id
            # Fall back to persistent "last active" field for billing thread access after method cleanup
            return self._last_active_protocol_id

    def _cleanup_thread_context(self) -> None:
        """
        Clean up thread context when method execution completes.
        Removes the thread's entry from action context to prevent memory leaks.
        """
        thread_id = threading.get_ident()
        with self._action_context_lock:
            self._action_context.pop(thread_id, None)

    def _accumulate_offline(
        self, seconds: float, current_action: Optional[str]
    ) -> None:
        """Accumulate usage offline when Redis is unavailable."""
        with self._state_lock:
            self._accumulated_usage += seconds
        if current_action:
            logger.debug(
                f"📊 Accumulated offline: +{seconds:.6f}s (action={current_action}, total: {self._accumulated_usage:.6f}s)"
            )
        else:
            logger.info(
                f"📊 Accumulated offline: +{seconds:.6f}s (total: {self._accumulated_usage:.6f}s)"
            )

    def _add_action_tracking_to_redis(
        self,
        redis_client,
        usage_key: str,
        total_to_send: float,
        current_action: Optional[str],
        protocol_id: Optional[str] = None,
    ) -> None:
        """
        Add action-specific and protocol-specific usage tracking to Redis operations.

        Key structure (hierarchical for efficient billing queries):
        - usage:{username}:{app_name}:{class_name}:{container_id}:ACN_{action} - Value: uptime (seconds)
        - usage:{username}:{app_name}:{class_name}:{container_id}:ALY_{protocol_id} - Value: uptime (seconds)
        - usage:{username}:{app_name}:{class_name}:{container_id}:ALY_{protocol_id}:ACN_{action} - Value: uptime (seconds)

        Uses "no-action" as default action name for consistency.
        This allows efficient queries: user > model/class > container > action > uptime
        All data is stored as simple string values (uptime in seconds), not hashes.
        """
        if not self._container_id:
            return

        expiration_seconds = self.key_expiration_days * 24 * 60 * 60

        # Use "no-action" as default for consistency
        action_name = current_action if current_action else "no-action"

        # Log action tracking for debugging
        if current_action:
            logger.info(
                f"[BILLING] [ACTION] Writing action '{action_name}' to Redis (container: {self._container_id}, seconds: {total_to_send:.6f})"
            )
        else:
            logger.warning(
                f"[BILLING] [ACTION] No current_action set, using 'no-action' (container: {self._container_id}, seconds: {total_to_send:.6f})"
            )

        # Build hierarchical key: usage:{username}:{app_name}:{class_name}:{container_id}:ACN_{action}
        # Store as simple increment (not hash) - each key represents one container+action combination
        action_key = f"{usage_key}:{self._container_id}:ACN_{action_name}"
        redis_client.incrbyfloat(action_key, total_to_send)
        redis_client.expire(action_key, expiration_seconds)

        # Track by protocol if provided
        if protocol_id:
            protocol_key = f"{usage_key}:{self._container_id}:ALY_{protocol_id}"
            redis_client.incrbyfloat(protocol_key, total_to_send)
            redis_client.expire(protocol_key, expiration_seconds)

        # Track protocol+action combination if both provided
        if protocol_id:
            combo_key = (
                f"{usage_key}:{self._container_id}:ALY_{protocol_id}:ACN_{action_name}"
            )
            redis_client.incrbyfloat(combo_key, total_to_send)
            redis_client.expire(combo_key, expiration_seconds)

    def _add_action_tracking_to_pipeline(
        self,
        pipe,
        usage_key: str,
        total_to_send: float,
        current_action: Optional[str],
        protocol_id: Optional[str] = None,
    ) -> None:
        """
        Add action-specific and protocol-specific usage tracking to Redis pipeline.

        Key structure (hierarchical for efficient billing queries):
        - usage:{username}:{app_name}:{class_name}:{container_id}:ACN_{action} - Value: uptime (seconds)
        - usage:{username}:{app_name}:{class_name}:{container_id}:ALY_{protocol_id} - Value: uptime (seconds)
        - usage:{username}:{app_name}:{class_name}:{container_id}:ALY_{protocol_id}:ACN_{action} - Value: uptime (seconds)

        Uses "no-action" as default action name for consistency.
        All data is stored as simple string values (uptime in seconds), not hashes.
        """
        if not self._container_id:
            return

        expiration_seconds = self.key_expiration_days * 24 * 60 * 60

        # Use "no-action" as default for consistency
        action_name = current_action if current_action else "no-action"

        # Log action tracking for debugging
        if current_action:
            logger.info(
                f"[BILLING] [ACTION] Writing action '{action_name}' to Redis via pipeline (container: {self._container_id}, seconds: {total_to_send:.6f})"
            )
        else:
            logger.warning(
                f"[BILLING] [ACTION] No current_action set in pipeline, using 'no-action' (container: {self._container_id}, seconds: {total_to_send:.6f})"
            )

        # Build hierarchical key: usage:{username}:{app_name}:{class_name}:{container_id}:ACN_{action}
        action_key = f"{usage_key}:{self._container_id}:ACN_{action_name}"
        pipe.incrbyfloat(action_key, total_to_send)
        pipe.expire(action_key, expiration_seconds)

        # Track by protocol if provided
        if protocol_id:
            protocol_key = f"{usage_key}:{self._container_id}:ALY_{protocol_id}"
            pipe.incrbyfloat(protocol_key, total_to_send)
            pipe.expire(protocol_key, expiration_seconds)

        # Track protocol+action combination if both provided
        if protocol_id:
            combo_key = (
                f"{usage_key}:{self._container_id}:ALY_{protocol_id}:ACN_{action_name}"
            )
            pipe.incrbyfloat(combo_key, total_to_send)
            pipe.expire(combo_key, expiration_seconds)

    def _increment_usage_without_pipeline(
        self,
        redis_client,
        usage_key: str,
        total_to_send: float,
        current_action: Optional[str],
        protocol_id: Optional[str] = None,
    ) -> None:
        """Increment usage in Redis without pipeline (fallback method)."""
        logger.warning("Redis client missing pipeline method")
        if self._container_id:
            # Store total usage per container: usage:{username}:{app_name}:{class_name}:{container_id}
            container_total_key = f"{usage_key}:{self._container_id}"
            redis_client.incrbyfloat(container_total_key, total_to_send)
            expiration_seconds = self.key_expiration_days * 24 * 60 * 60
            redis_client.expire(container_total_key, expiration_seconds)

            # Track action/protocol breakdowns
            self._add_action_tracking_to_redis(
                redis_client, usage_key, total_to_send, current_action, protocol_id
            )

    def _increment_usage_with_pipeline(
        self,
        redis_client,
        usage_key: str,
        total_to_send: float,
        current_action: Optional[str],
        protocol_id: Optional[str] = None,
    ) -> None:
        """Increment usage in Redis using pipeline for atomic operations."""
        pipe = redis_client.pipeline()
        if self._container_id:
            # Store total usage per container: usage:{username}:{app_name}:{class_name}:{container_id}
            container_total_key = f"{usage_key}:{self._container_id}"
            pipe.incrbyfloat(container_total_key, total_to_send)
            expiration_seconds = self.key_expiration_days * 24 * 60 * 60
            pipe.expire(container_total_key, expiration_seconds)

            # Track action/protocol breakdowns
            self._add_action_tracking_to_pipeline(
                pipe, usage_key, total_to_send, current_action, protocol_id
            )
        pipe.execute()

    def _atomic_increment_usage(self, seconds: float) -> None:
        """
        Atomically increment usage with proper error handling and accumulation.
        Thread-safe and prevents double billing.
        Now tracks action context when available.
        """
        if seconds <= 0:
            return  # Ignore invalid increments

        # Get current action and protocol_id from thread-local context
        current_action = self.get_current_action()
        protocol_id = self.get_protocol_id()

        with self._get_redis_client() as redis_client:
            if redis_client is None:
                self._accumulate_offline(seconds, current_action)
                return

            # ATOMIC operation - hold lock through entire Redis operation to prevent race
            with self._state_lock:
                total_to_send = seconds + self._accumulated_usage
                previous_accumulated = self._accumulated_usage
                # Track total billed time for debugging
                self._total_billed_time += total_to_send

                try:
                    # Build hierarchical key: usage:{username}:{app_name}:{class_name}
                    # This allows efficient queries: user > model/class > container > action
                    usage_key = (
                        f"usage:{self.username}:{self.app_name}:{self.class_name}"
                    )

                    if not hasattr(redis_client, "pipeline"):
                        self._increment_usage_without_pipeline(
                            redis_client,
                            usage_key,
                            total_to_send,
                            current_action,
                            protocol_id,
                        )
                    else:
                        self._increment_usage_with_pipeline(
                            redis_client,
                            usage_key,
                            total_to_send,
                            current_action,
                            protocol_id,
                        )

                    # Only clear accumulated usage after ALL operations succeed
                    self._accumulated_usage = 0.0

                    if previous_accumulated > 0 and current_action:
                        logger.debug(
                            f"Sent accumulated: {previous_accumulated:.6f}s + current: {seconds:.6f}s = {total_to_send:.6f}s (action={current_action})"
                        )
                    elif previous_accumulated > 0:
                        logger.info(
                            f"Sent accumulated: {previous_accumulated:.6f}s + current: {seconds:.6f}s = {total_to_send:.6f}s"
                        )

                    with self._redis_lock:
                        self._last_successful_redis_time = time.time()

                except Exception as e:
                    logger.warning(f"Redis increment failed: {e}")
                    # Re-accumulate only the current usage (previous accumulated is still there)
                    self._accumulated_usage += seconds
                    logger.info(
                        f"📊 Re-accumulated: +{seconds:.6f}s (total: {self._accumulated_usage:.6f}s)"
                    )

    def _try_send_accumulated_usage(self) -> bool:
        """Try to send accumulated usage if Redis is available. Thread-safe."""
        with self._get_redis_client() as redis_client:
            if redis_client is None:
                return False

            # Get current action and protocol_id from thread-local context
            current_action = self.get_current_action()
            protocol_id = self.get_protocol_id()

            with self._state_lock:
                if self._accumulated_usage <= 0:
                    return True  # Nothing to send
                amount_to_send = self._accumulated_usage

                try:
                    # Build hierarchical key: usage:{username}:{app_name}:{class_name}
                    usage_key = (
                        f"usage:{self.username}:{self.app_name}:{self.class_name}"
                    )

                    # Use pipeline for atomic operations - defensive check
                    if not hasattr(redis_client, "pipeline"):
                        logger.warning("Redis client missing pipeline method")
                        return False

                    pipe = redis_client.pipeline()

                    if self._container_id:
                        # Store total usage per container
                        container_total_key = f"{usage_key}:{self._container_id}"
                        pipe.incrbyfloat(container_total_key, amount_to_send)
                        expiration_seconds = self.key_expiration_days * 24 * 60 * 60
                        pipe.expire(container_total_key, expiration_seconds)

                        # Track action/protocol breakdowns
                        self._add_action_tracking_to_pipeline(
                            pipe, usage_key, amount_to_send, current_action, protocol_id
                        )

                    # Execute atomically
                    pipe.execute()

                    # Only clear after all operations succeed
                    self._accumulated_usage = 0.0

                    if current_action:
                        logger.debug(
                            f"Successfully sent accumulated usage: {amount_to_send:.6f}s (action={current_action})"
                        )
                    else:
                        logger.info(
                            f"Successfully sent accumulated usage: {amount_to_send:.6f}s"
                        )

                    with self._redis_lock:
                        self._last_successful_redis_time = time.time()

                    return True

                except Exception as e:
                    logger.warning(f"Failed to send accumulated usage: {e}")
                    return False

    def _check_container_validity_if_needed(
        self,
        current_time: float,
        last_container_check_time: float,
        container_check_interval: float,
    ) -> tuple[bool, float]:
        """
        Check container validity periodically and before wait if needed.

        Returns:
            Tuple of (should_continue, updated_last_container_check_time)
        """
        # Check container validity periodically
        if current_time - last_container_check_time >= container_check_interval:
            if not self._is_container_still_valid():
                logger.warning(
                    f"🚨 Container no longer valid. Stopping billing loop for container: {self._container_id}"
                )
                self._stop_event.set()
                return False, last_container_check_time
            last_container_check_time = current_time

        # Also check container validity immediately before waiting if it's been a while
        # This helps catch container changes faster, especially for large gaps
        if self._last_billing_time is not None:
            time_since_last_billing = current_time - self._last_billing_time
            if time_since_last_billing > CONTAINER_VALIDITY_CHECK_INTERVAL_SECONDS:
                if not self._is_container_still_valid():
                    logger.warning(
                        f"🚨 Container no longer valid (detected before wait). Stopping billing loop for container: {self._container_id}"
                    )
                    self._stop_event.set()
                    return False, last_container_check_time

        return True, last_container_check_time

    def _check_billing_timeout(self, current_time: float) -> bool:
        """Check if billing thread should timeout due to inactivity. Returns True if should stop."""
        with self._state_lock:
            if self._last_activity_time is not None:
                time_since_activity = current_time - self._last_activity_time
                if time_since_activity > self._container_timeout_seconds:
                    logger.warning(
                        f"🚨 Billing thread timeout: no activity for {time_since_activity:.1f}s "
                        f"(timeout: {self._container_timeout_seconds}s). "
                        f"Stopping billing loop for container: {self._container_id}"
                    )
                    self._stop_event.set()
                    return True
        return False

    def _wait_for_billing_interval(self) -> tuple[float, float, float]:
        """
        Wait for billing interval and return timing information.

        Returns:
            Tuple of (actual_wait_duration, wait_start_time, wait_end_time)
        """
        wait_start_time = time.time()
        if self._stop_event.wait(timeout=self.billing_interval):
            # Stop signal received - return immediately
            wait_end_time = time.time()
            return wait_end_time - wait_start_time, wait_start_time, wait_end_time
        wait_end_time = time.time()
        actual_wait_duration = wait_end_time - wait_start_time
        return actual_wait_duration, wait_start_time, wait_end_time

    def _handle_large_gap_detection(
        self, actual_wait_duration: float, wait_start_time: float, wait_end_time: float
    ) -> bool:
        """
        Handle large gap detection. Returns False if should stop billing.
        """
        if actual_wait_duration <= LARGE_GAP_THRESHOLD_SECONDS:
            return True  # Not a large gap, continue normally

        is_valid = self._is_container_still_valid(strict_for_large_gap=True)

        if not is_valid:
            logger.warning(
                f"🚨 Large gap detected ({actual_wait_duration:.6f}s) but container is no longer valid or cannot be verified. "
                f"Stopping billing to prevent incorrect charges (container ID: {self._container_id[:50] if self._container_id else None})."
            )
            self._stop_event.set()
            return False

        return True  # Valid, continue but mark for double-check

    def _try_reconnect_redis_if_needed(
        self, current_time: float, last_redis_retry: float, redis_retry_interval: float
    ) -> float:
        """Try to reconnect to Redis if needed. Returns updated last_redis_retry."""
        if (current_time - last_redis_retry) > redis_retry_interval:
            with self._redis_lock:
                if self._redis_client is None or (
                    self._last_successful_redis_time
                    and current_time - self._last_successful_redis_time
                    > redis_retry_interval
                ):
                    logger.info("🔄 Attempting to reconnect to Redis...")
                    if self._initialize_redis():
                        self._try_send_accumulated_usage()
                    last_redis_retry = current_time
        return last_redis_retry

    def _process_single_billing_increment(
        self,
        actual_elapsed: float,
        actual_wait_duration: float,
        wait_end_time: float,
        loop_start_time: float,
        accumulated_billed: float,
        total_actual_time: float,
        should_skip_large_gap: bool,
    ) -> tuple[float, float, float]:
        """
        Process a single billing increment.

        Returns:
            Tuple of (updated_accumulated_billed, updated_total_actual_time, last_print_time)
        """
        last_print_time = time.time()  # Will be updated if needed

        with self._state_lock:
            if self._last_billing_time is None:
                # This shouldn't happen, but handle gracefully
                self._last_billing_time = wait_end_time
                return accumulated_billed, total_actual_time, last_print_time

            # Bill for the ACTUAL wait duration, not the time including processing overhead
            # This ensures we only bill for time that actually passes, not processing time
            # BUT: For large gaps, we'll verify again right before billing, so don't add to tracking yet
            actual_elapsed = max(0, actual_wait_duration)
            # Only add to total_actual_time if it's not a large gap that needs re-verification
            # (We'll add it after the second check passes)
            if not (
                should_skip_large_gap and actual_elapsed > LARGE_GAP_THRESHOLD_SECONDS
            ):
                total_actual_time += actual_elapsed

            # Update last billing time to the END of the wait (before processing)
            # This prevents double-counting processing time in the next iteration
            self._last_billing_time = wait_end_time

            # Log timing details for debugging
            if (
                actual_elapsed > self.billing_interval * 1.5
            ):  # Warn if significantly over expected
                logger.warning(
                    f"⏱️  Billing loop wait duration ({actual_elapsed:.6f}s) exceeds expected interval "
                    f"({self.billing_interval:.2f}s) by {actual_elapsed - self.billing_interval:.6f}s"
                )

        # CRITICAL: For large gaps, double-check container validity RIGHT BEFORE billing (using strict mode)
        # This prevents billing if container was restored between the initial check and billing
        if actual_elapsed > 0:
            if actual_elapsed > LARGE_GAP_THRESHOLD_SECONDS:
                if not self._is_container_still_valid(strict_for_large_gap=True):
                    logger.warning(
                        f"🚨 About to bill for large gap ({actual_elapsed:.6f}s) but container is no longer valid or cannot be verified. "
                        f"Skipping billing to prevent incorrect charges (container ID: {self._container_id[:50] if self._container_id else None})."
                    )
                    self._stop_event.set()
                    return accumulated_billed, total_actual_time, last_print_time
                # Large gap passed both checks - now add to total_actual_time (we skipped it earlier)
                with self._state_lock:
                    total_actual_time += actual_elapsed

            # Bill for this time increment (includes startup, execution, and idle time)
            # Modal bills for container uptime, which includes idle time between function calls
            self._atomic_increment_usage(actual_elapsed)
            accumulated_billed += actual_elapsed

            # Update activity time on successful billing
            with self._state_lock:
                self._last_activity_time = wait_end_time

            # Log each increment for debugging (with thread info for verification)
            thread_name = threading.current_thread().name
            logger.debug(
                f"💰 Billing loop increment: {actual_elapsed:.6f}s "
                f"(wait: {actual_wait_duration:.6f}s, total billed: {accumulated_billed:.6f}s, "
                f"total actual: {total_actual_time:.6f}s, loop runtime: {wait_end_time - loop_start_time:.6f}s) | "
                f"thread_name={thread_name}, container_id={self._container_id[:50] if self._container_id else None}"
            )

            current_time_for_print = time.time()
            if (
                current_time_for_print - last_print_time
                >= BILLING_STATS_LOG_INTERVAL_SECONDS
            ):
                logger.info(
                    f"📊 Billed {accumulated_billed:.6f}s in the last {current_time_for_print - last_print_time:.2f} seconds "
                    f"(total actual time: {total_actual_time:.6f}s, loop runtime: {current_time_for_print - loop_start_time:.6f}s)"
                )
                accumulated_billed = 0.0
                last_print_time = current_time_for_print

        return accumulated_billed, total_actual_time, last_print_time

    def _billing_loop(self) -> None:
        """Main billing loop with robust error handling and precise timing."""
        thread_name = threading.current_thread().name
        thread_id = threading.current_thread().ident
        logger.info(
            f"🚀 Starting billing loop for container: {self._container_id} | "
            f"thread_name={thread_name}, thread_id={thread_id}"
        )

        redis_retry_interval = REDIS_RETRY_INTERVAL_SECONDS
        last_redis_retry = 0
        last_container_check_time = 0.0
        container_check_interval = CONTAINER_VALIDITY_CHECK_INTERVAL_SECONDS

        accumulated_billed = 0.0
        last_print_time = time.time()
        loop_start_time = time.time()  # Track when loop actually started
        total_actual_time = 0.0  # Track total actual elapsed time

        while not self._stop_event.is_set():
            try:
                current_time = time.time()

                # Check container validity if needed
                should_continue, last_container_check_time = (
                    self._check_container_validity_if_needed(
                        current_time,
                        last_container_check_time,
                        container_check_interval,
                    )
                )
                if not should_continue:
                    break

                # Check timeout
                if self._check_billing_timeout(current_time):
                    break

                # Wait for billing interval
                actual_wait_duration, wait_start_time, wait_end_time = (
                    self._wait_for_billing_interval()
                )
                if self._stop_event.is_set():
                    break

                # Handle large gap detection
                should_skip_large_gap = False
                if actual_wait_duration > LARGE_GAP_THRESHOLD_SECONDS:
                    if not self._handle_large_gap_detection(
                        actual_wait_duration, wait_start_time, wait_end_time
                    ):
                        break
                    should_skip_large_gap = True

                # Try to reconnect to Redis if needed
                current_time = time.time()
                last_redis_retry = self._try_reconnect_redis_if_needed(
                    current_time, last_redis_retry, redis_retry_interval
                )

                # Process billing increment
                actual_elapsed = max(0, actual_wait_duration)
                accumulated_billed, total_actual_time, last_print_time = (
                    self._process_single_billing_increment(
                        actual_elapsed,
                        actual_wait_duration,
                        wait_end_time,
                        loop_start_time,
                        accumulated_billed,
                        total_actual_time,
                        should_skip_large_gap,
                    )
                )

                if self._stop_event.is_set():
                    break

            except Exception as e:
                logger.warning(f"Error in billing loop: {e}")
                continue  # Continue billing on errors

        loop_end_time = time.time()
        total_loop_runtime = loop_end_time - loop_start_time
        thread_name = threading.current_thread().name
        thread_id = threading.current_thread().ident

        # Calculate billing breakdown for debugging
        gap_time = total_loop_runtime - total_actual_time
        billing_efficiency = (
            (total_actual_time / total_loop_runtime * 100)
            if total_loop_runtime > 0
            else 0
        )

        logger.info(
            f"🛑 Billing loop stopped. Total loop runtime: {total_loop_runtime:.6f}s, "
            f"total actual time billed: {total_actual_time:.6f}s, "
            f"gap time (not billed): {gap_time:.6f}s, "
            f"billing efficiency: {billing_efficiency:.1f}% | "
            f"thread_name={thread_name}, thread_id={thread_id}, "
            f"container_id={self._container_id[:50] if self._container_id else None}"
        )

    def _check_and_stop_stale_billing_threads(self) -> None:
        """
        Check for and stop any stale billing threads from previous containers.
        This prevents old billing threads from continuing to run after container restore.
        """
        try:
            # Check if there's an existing billing thread that's still alive
            if self._billing_thread and self._billing_thread.is_alive():
                logger.warning(
                    f"🛑 Found existing billing thread '{self._billing_thread.name}' still running. "
                    f"Stopping it before starting new billing service..."
                )
                # Stop the old thread
                self._stop_event.set()
                # Wait for it to stop gracefully
                self._billing_thread.join(timeout=1.0)
                if self._billing_thread.is_alive():
                    logger.warning(
                        "Old billing thread didn't stop gracefully, forcing termination..."
                    )
                    self._force_terminate_billing_thread(self._billing_thread)
                # Reset stop event for new thread
                self._stop_event = threading.Event()
                self._billing_thread = None
                logger.info("✅ Stale billing thread stopped")
        except Exception as e:
            logger.warning(f"Error checking for stale billing threads: {e}")

    def _check_entry_file_exists(
        self, strict_for_large_gap: bool
    ) -> tuple[bool, Optional[str]]:
        """
        Check if entry file exists and read billing_container_id.

        Returns:
            Tuple of (should_continue, billing_container_id)
        """
        entry_touch_file = "/var/billing_entry.touch"
        if not os.path.exists(entry_touch_file):
            if strict_for_large_gap:
                logger.warning(
                    "⚠️  Entry file doesn't exist for large gap validation. "
                    "Treating as potentially invalid to prevent over-billing."
                )
                return False, None
            # For normal checks, assume valid if entry file doesn't exist (might be first run)
            return True, None

        try:
            with open(entry_touch_file) as f:
                entry_metadata = json.load(f)
            billing_container_id = entry_metadata.get("billing_container_id")
            return True, billing_container_id
        except Exception as e:
            logger.debug(f"Could not read entry file for container validation: {e}")
            if strict_for_large_gap:
                logger.warning(
                    "⚠️  Could not read entry file for large gap validation. "
                    "Treating as potentially invalid to prevent over-billing."
                )
                return False, None
            return True, None

    def _validate_container_id_from_entry_file(
        self, billing_container_id: Optional[str]
    ) -> bool:
        """Validate that container ID from entry file matches current container ID."""
        if billing_container_id and billing_container_id != self._container_id:
            logger.warning(
                f"🚨 Container ID mismatch detected! "
                f"Entry file has: {billing_container_id[:50]}, "
                f"current: {self._container_id[:50] if self._container_id else None}. "
                f"Container has changed, stopping billing thread."
            )
            return False
        return True

    def _check_entry_file_modification_time(
        self, entry_touch_file: str, billing_container_id: Optional[str]
    ) -> bool:
        """Check entry file modification time for strict mode validation. Returns False if invalid."""
        try:
            file_mtime = os.path.getmtime(entry_touch_file)
            time_since_modification = time.time() - file_mtime
            # If file was modified very recently (< 2 seconds ago), it might be from a new container
            # that just started, and we're seeing a race condition
            if time_since_modification < 2.0:
                logger.warning(
                    f"⚠️  Entry file was modified {time_since_modification:.2f}s ago (very recently). "
                    f"For large gap check, this might indicate a new container just started. "
                    f"Being conservative and treating as potentially invalid to prevent over-billing."
                )
                return False
            # If file was modified a long time ago (> 10 seconds) AND we're seeing a large gap,
            # this is suspicious - the container might have been restored and the file hasn't been updated yet
            # OR this is an old thread from a previous container that should have been stopped
            if time_since_modification > LARGE_GAP_THRESHOLD_SECONDS:
                logger.warning(
                    f"⚠️  Entry file was modified {time_since_modification:.2f}s ago (long time ago). "
                    f"For large gap check, this is suspicious - container may have been restored. "
                    f"Being conservative and treating as potentially invalid to prevent over-billing."
                )
                return False
            logger.debug(
                f"✅ Container IDs match for large gap check: {billing_container_id[:50] if billing_container_id else None}, "
                f"file modified {time_since_modification:.2f}s ago"
            )
            return True
        except Exception as e:
            logger.debug(f"Could not check entry file modification time: {e}")
            # If we can't check, be conservative for large gaps
            return False

    def _check_proc1_exists(self) -> bool:
        """Check if /proc/1 exists. Returns False if container process is gone."""
        try:
            proc1_exists = os.path.exists("/proc/1")
            if not proc1_exists:
                logger.warning(
                    "🚨 Container process (PID 1) no longer exists. Stopping billing thread."
                )
                return False
            return True
        except Exception as e:
            logger.debug(f"Could not check /proc/1: {e}")
            # If we can't check, assume valid to avoid false positives
            return True

    def _is_container_still_valid(self, strict_for_large_gap: bool = False) -> bool:
        """
        Check if the container is still valid by verifying:
        1. Container ID in entry file matches current container ID
        2. Container process (PID 1) still exists

        Args:
            strict_for_large_gap: If True, be more conservative - return False if we can't definitively verify
                                  (e.g., entry file doesn't exist or can't be read). Used for large gap checks.

        Returns:
            bool: True if container is still valid, False otherwise
        """
        try:
            entry_touch_file = "/var/billing_entry.touch"
            should_continue, billing_container_id = self._check_entry_file_exists(
                strict_for_large_gap
            )
            if not should_continue:
                return False

            if billing_container_id is not None:
                if not self._validate_container_id_from_entry_file(
                    billing_container_id
                ):
                    return False

                if strict_for_large_gap and billing_container_id == self._container_id:
                    if not self._check_entry_file_modification_time(
                        entry_touch_file, billing_container_id
                    ):
                        return False
            elif strict_for_large_gap:
                logger.warning(
                    "⚠️  Entry file exists but billing_container_id is missing. "
                    "For large gap check, treating as potentially invalid to prevent over-billing."
                )
                return False

            return self._check_proc1_exists()
        except Exception as e:
            logger.warning(f"Error checking container validity: {e}")
            # On error, for large gaps be conservative, otherwise assume valid to avoid false positives
            if strict_for_large_gap:
                return False
            return True

    def _initialize_billing_state(self) -> None:
        """Initialize billing state: create container ID, update entry file, set start time."""
        # Initialize Redis (non-blocking)
        with self._redis_lock:
            redis_available = self._initialize_redis()
            if not redis_available:
                logger.warning("Redis not available, will accumulate usage offline")

        # Create unique container ID and set start time
        self._container_id = self._create_unique_container_id()
        self._start_time = time.time()

        logger.info(f"📝 Container ID: {self._container_id}")

        # CRITICAL: Update entry file IMMEDIATELY after creating container ID
        # This ensures old threads can detect container change as soon as possible
        entry_touch_file = "/var/billing_entry.touch"
        if os.path.exists(entry_touch_file):
            try:
                with open(entry_touch_file) as f:
                    entry_metadata = json.load(f)
                logger.info(
                    f"📝 Billing entry metadata: {entry_metadata} (container_id will be added after creation)"
                )
                # Update entry metadata with container ID IMMEDIATELY
                entry_metadata["billing_container_id"] = self._container_id
                entry_metadata["billing_start_time"] = self._start_time
                with open(entry_touch_file, "w") as f:
                    json.dump(entry_metadata, f)
                logger.info(
                    f"📝 Updated billing entry metadata with container_id: {self._container_id[:50]}"
                )
            except Exception as e:
                logger.warning(f"Could not update billing entry metadata: {e}")

    def _calculate_first_increment_for_restore(self) -> float:
        """Calculate first increment for snapshot restore case. Returns 0.0 for restore."""
        is_snapshot_restore = getattr(self, "_is_snapshot_restore", False)
        if is_snapshot_restore:
            uptime = self._get_container_uptime()  # Get for logging/debugging
            logger.info(
                f"📸 Snapshot restore detected (via flag) - skipping initial increment "
                f"(calculated uptime: {uptime:.6f}s, but restore time is negligible)"
            )
            return 0.0
        return None  # Not a restore, continue with other logic

    def _calculate_first_increment_for_creation(self) -> Optional[float]:
        """
        Calculate first increment for snapshot creation case.
        Returns first_increment if calculated, None otherwise.
        """
        snapshot_data = parse_snapshot_uptime_file()
        if snapshot_data is None:
            return None

        try:
            snapshot_container_id = snapshot_data.get("container_id")
            if snapshot_data["format"] == "json" and snapshot_container_id:
                if snapshot_container_id != self._container_id:
                    # Different container ID = restore
                    self._is_snapshot_restore = True
                    logger.info(
                        f"📸 Snapshot restore detected via container ID comparison (fallback): "
                        f"snapshot_container_id={snapshot_container_id[:50]} != "
                        f"current_container_id={self._container_id[:50]}"
                    )
                    return 0.0
                else:
                    # Same container ID - this is creation
                    early_uptime = getattr(self, "_early_uptime", None)
                    if early_uptime is not None:
                        uptime = early_uptime
                        first_increment = uptime
                        self._container_start_time = time.time() - uptime
                        logger.info(
                            f"💰 First increment: {uptime:.6f}s (using early uptime from a_billing_enter) - snapshot creation"
                        )
                        return first_increment
                    else:
                        uptime = self._get_container_uptime()
                        first_increment = uptime
                        self._container_start_time = time.time() - uptime
                        logger.info(
                            f"💰 First increment: {uptime:.6f}s (uptime: {uptime:.6f}s, no penalty) - snapshot creation"
                        )
                        return first_increment
            elif snapshot_data["format"] == "plain":
                # Old format - assume restore
                self._is_snapshot_restore = True
                logger.info(
                    "📸 Snapshot restore detected (old format file exists - fallback)"
                )
                return 0.0
            else:
                # JSON format without container_id - this is creation
                early_uptime = getattr(self, "_early_uptime", None)
                if early_uptime is not None:
                    uptime = early_uptime
                    first_increment = uptime
                    self._container_start_time = time.time() - uptime
                    logger.info(
                        f"💰 First increment: {uptime:.6f}s (using early uptime from a_billing_enter) - snapshot creation"
                    )
                    return first_increment
                else:
                    uptime = self._get_container_uptime()
                    first_increment = uptime
                    self._container_start_time = time.time() - uptime
                    logger.info(
                        f"💰 First increment: {uptime:.6f}s (uptime: {uptime:.6f}s, no penalty) - snapshot creation"
                    )
                    return first_increment
        except Exception as e:
            logger.warning(
                f"Could not process snapshot file for restore detection: {e}"
            )
            # Fallback to normal uptime calculation
            early_uptime = getattr(self, "_early_uptime", None)
            if early_uptime is not None:
                uptime = early_uptime
                first_increment = uptime
                self._container_start_time = time.time() - uptime
                logger.info(
                    f"💰 First increment: {uptime:.6f}s (using early uptime from a_billing_enter)"
                )
                return first_increment
            else:
                uptime = self._get_container_uptime()
                first_increment = uptime
                self._container_start_time = time.time() - uptime
                logger.info(
                    f"💰 First increment: {uptime:.6f}s (uptime: {uptime:.6f}s, no penalty)"
                )
                return first_increment

    def _calculate_first_increment_for_fresh(self) -> float:
        """Calculate first increment for fresh container (no snapshot file)."""
        early_uptime = getattr(self, "_early_uptime", None)
        current_uptime = self._get_container_uptime()

        if early_uptime is not None:
            # Use the larger of current_uptime or early_uptime to ensure we don't underbill
            uptime = max(current_uptime, early_uptime)
            first_increment = uptime
            self._container_start_time = time.time() - uptime
            logger.info(
                f"💰 First increment: {uptime:.6f}s (current_uptime={current_uptime:.6f}s, "
                f"early_uptime={early_uptime:.6f}s, using max to account for pre-Redis time)"
            )
            return first_increment
        else:
            uptime = current_uptime
            first_increment = uptime
            self._container_start_time = time.time() - uptime
            logger.info(
                f"💰 First increment: {uptime:.6f}s (uptime: {uptime:.6f}s, no penalty)"
            )
            return first_increment

    def _adjust_for_restore_via_a_z_files(
        self,
        a_container_id_from_file: Optional[str],
        z_container_id_from_file: Optional[str],
        first_increment: float,
    ) -> Optional[float]:
        """Handle restore case when container IDs don't match. Returns adjusted increment or None."""
        if (
            a_container_id_from_file
            and z_container_id_from_file
            and (
                a_container_id_from_file != self._container_id
                or z_container_id_from_file != self._container_id
                or a_container_id_from_file != z_container_id_from_file
            )
        ):
            # This is a restore - use restore-specific uptime
            self._is_snapshot_restore = True
            restore_uptime = self._get_restore_uptime()
            if restore_uptime > first_increment:
                logger.info(
                    f"📸 Adjusting first increment for restore: {first_increment:.6f}s -> {restore_uptime:.6f}s "
                    f"(using restore-specific uptime calculation)"
                )
                return restore_uptime
            return first_increment
        return None

    def _adjust_for_creation_via_a_z_files(
        self,
        a_timestamp: Optional[float],
        z_timestamp: Optional[float],
        a_is_enter_context: Optional[bool],
        z_is_enter_context: Optional[bool],
        first_increment: float,
    ) -> Optional[float]:
        """Handle creation case when container IDs match. Returns adjusted increment or None."""
        if a_is_enter_context and z_is_enter_context:
            # Both in @modal.enter context - snapshot creation
            if a_timestamp and z_timestamp:
                current_time = time.time()
                total_time_from_a_enter = current_time - a_timestamp
                if total_time_from_a_enter > first_increment + 0.1:
                    logger.info(
                        f"📊 Adjusting first increment using a/z entry files: {first_increment:.6f}s -> {total_time_from_a_enter:.6f}s"
                    )
                    return total_time_from_a_enter
        return None

    def _adjust_for_a_enter_only(
        self,
        a_container_id: Optional[str],
        a_timestamp: Optional[float],
        first_increment: float,
    ) -> Optional[float]:
        """Handle case when only a_enter file exists. Returns adjusted increment or None."""
        early_uptime = getattr(self, "_early_uptime", None)
        if (
            a_container_id
            and a_container_id == self._container_id
            and a_timestamp
            and early_uptime is not None
        ):
            container_start_time = a_timestamp - early_uptime
            self._container_start_time = container_start_time
            current_time = time.time()
            total_time_from_start = current_time - container_start_time
            if total_time_from_start > first_increment + 0.1:
                logger.info(
                    f"📊 Adjusting first increment using a_enter file: {first_increment:.6f}s -> {total_time_from_start:.6f}s"
                )
                return total_time_from_start
        return None

    def _adjust_first_increment_with_a_z_files(self, first_increment: float) -> float:
        """
        Adjust first increment using a/z entry files for accurate billing.
        Returns adjusted first_increment.
        """
        a_enter_file = "/var/billing_a_enter.touch"
        z_enter_file = "/var/billing_z_enter.touch"

        # FIRST: Check if we're reading old files from a previous container (snapshot restore)
        if os.path.exists(a_enter_file) and os.path.exists(z_enter_file):
            try:
                with open(a_enter_file) as f:
                    a_enter_metadata = json.load(f)
                with open(z_enter_file) as f:
                    z_enter_metadata = json.load(f)

                a_container_id_from_file = a_enter_metadata.get("container_id")
                z_container_id_from_file = z_enter_metadata.get("container_id")
                a_timestamp = a_enter_metadata.get("timestamp_utc")
                z_timestamp = z_enter_metadata.get("timestamp_utc")
                a_is_enter_context = a_enter_metadata.get("is_enter_context", None)
                z_is_enter_context = z_enter_metadata.get("is_enter_context", None)

                # Check for restore case
                restore_adjustment = self._adjust_for_restore_via_a_z_files(
                    a_container_id_from_file, z_container_id_from_file, first_increment
                )
                if restore_adjustment is not None:
                    return restore_adjustment

                # Check for creation case
                creation_adjustment = self._adjust_for_creation_via_a_z_files(
                    a_timestamp,
                    z_timestamp,
                    a_is_enter_context,
                    z_is_enter_context,
                    first_increment,
                )
                if creation_adjustment is not None:
                    return creation_adjustment
            except Exception as e:
                logger.warning(
                    f"Could not calculate container start time from a/z entry files: {e}"
                )

        elif os.path.exists(a_enter_file) and not os.path.exists(z_enter_file):
            # Only a_enter file exists
            try:
                with open(a_enter_file) as f:
                    a_enter_metadata = json.load(f)
                a_container_id = a_enter_metadata.get("container_id")
                a_timestamp = a_enter_metadata.get("timestamp_utc")

                a_enter_adjustment = self._adjust_for_a_enter_only(
                    a_container_id, a_timestamp, first_increment
                )
                if a_enter_adjustment is not None:
                    return a_enter_adjustment
            except Exception as e:
                logger.warning(
                    f"Could not calculate container start time from a_enter file: {e}"
                )

        return first_increment

    def _apply_first_increment(self, first_increment: float) -> None:
        """Apply the first billing increment."""
        is_snapshot_restore = getattr(self, "_is_snapshot_restore", False)
        logger.info(
            f"💰 About to apply first increment: {first_increment:.6f}s "
            f"(container_id: {self._container_id[:50] if self._container_id else None}, "
            f"is_snapshot_restore: {is_snapshot_restore}, "
            f"phase: {'restore' if is_snapshot_restore else 'creation'})"
        )

        if first_increment > 0:
            # Safety check: warn if first increment is suspiciously large
            if first_increment > 60.0:
                logger.error(
                    f"🚨 WARNING: First increment is suspiciously large: {first_increment:.6f}s "
                    f"(container_id: {self._container_id[:50] if self._container_id else None}). "
                    f"This may indicate host PID 1 uptime was used instead of container uptime!"
                )
            self._atomic_increment_usage(first_increment)
            logger.info(
                f"✅ Applied first increment: {first_increment:.6f}s "
                f"(container_id: {self._container_id[:50] if self._container_id else None}, "
                f"phase: {'restore' if is_snapshot_restore else 'creation'})"
            )
        else:
            logger.debug("Skipping initial increment (snapshot restore detected)")

        # Set last billing time AFTER first increment to prevent timing gaps
        self._last_billing_time = time.time()
        self._last_activity_time = time.time()  # Initialize activity tracking

    def start_billing(self) -> bool:
        """
        Start the background billing service with thread safety and double-start prevention.

        Returns:
            bool: True if billing started successfully, False otherwise.
        """
        with self._state_lock:
            # Check for and stop any stale billing threads from previous containers
            self._check_and_stop_stale_billing_threads()

            # Prevent double-start
            if self._is_started:
                logger.warning("Billing already started")
                return True

            if self._is_stopped:
                logger.warning("Cannot restart stopped billing service")
                return False

            self._initialize_billing_state()

            # Calculate first increment based on tracking file and snapshot detection
            try:
                # FIRST check restore flag (set by a_billing_enter before we check tracking file)
                # This is critical because tracking file persists across restores
                first_increment = self._calculate_first_increment_for_restore()

                if first_increment is None:
                    # Not a restore, continue with other logic
                    if os.path.exists(self._tracking_file):
                        # Tracking file exists - subsequent call
                        first_increment = self.billing_interval
                        logger.info(
                            f"💰 First increment: {first_increment:.6f}s (subsequent call - container IDs match, not a restore)"
                        )
                    else:
                        # First method call - check snapshot file
                        creation_increment = (
                            self._calculate_first_increment_for_creation()
                        )
                        if creation_increment is not None:
                            first_increment = creation_increment
                        else:
                            # No snapshot file - fresh container
                            first_increment = (
                                self._calculate_first_increment_for_fresh()
                            )

                        # Create tracking file atomically
                        with open(self._tracking_file, "w") as f:
                            f.write(f"started:{time.time()}:{self._container_id}")

                # Adjust first increment with a/z files if needed
                if first_increment > 0 and not getattr(
                    self, "_is_snapshot_restore", False
                ):
                    first_increment = self._adjust_first_increment_with_a_z_files(
                        first_increment
                    )

            except Exception as e:
                logger.warning(f"Could not handle tracking file: {e}")
                first_increment = self.billing_interval

            # Apply first increment
            self._apply_first_increment(first_increment)

            # Start billing thread
            thread_name = f"BillingThread-{self._container_id[:8] if self._container_id and len(self._container_id) >= 8 else (self._container_id or 'unknown')}"
            self._billing_thread = threading.Thread(
                target=self._billing_loop,
                daemon=True,
                name=thread_name,
            )
            self._billing_thread.start()

            # Log thread start with details for verification
            logger.info(
                f"🧵 Started billing thread: name={thread_name}, "
                f"thread_id={self._billing_thread.ident}, "
                f"container_id={self._container_id[:50] if self._container_id else None}, "
                f"is_alive={self._billing_thread.is_alive()}"
            )

            self._is_started = True
            logger.info(
                f"Billing service started with {self.billing_interval}s intervals"
            )
            return True

    def _handle_thread_termination(self, billing_thread) -> bool:
        """Handle billing thread termination with graceful and forced approaches."""
        if not billing_thread or not billing_thread.is_alive():
            return True

        logger.warning(
            f"⏳ Waiting for billing thread {billing_thread.name} to stop..."
        )

        # First attempt: Graceful shutdown
        billing_thread.join(timeout=0.5)

        if not billing_thread.is_alive():
            logger.info("Thread stopped gracefully")
            return True

        # Force termination if still alive
        logger.warning(
            "Billing thread still alive after 0.5s, attempting force termination..."
        )
        return self._force_terminate_billing_thread(billing_thread)

    def _force_terminate_billing_thread(self, billing_thread) -> bool:
        """Force terminate billing thread using SystemExit injection."""
        try:
            import ctypes

            res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_long(billing_thread.ident), ctypes.py_object(SystemExit)
            )
            if res == 0:
                logger.warning("Thread ID not found for force kill")
                return False
            elif res > 1:
                ctypes.pythonapi.PyThreadState_SetAsyncExc(billing_thread.ident, None)
                logger.warning("Force kill affected multiple threads, rolled back")
                return False
            else:
                logger.info("Sent SystemExit to billing thread")

        except Exception as e:
            logger.warning(f"Thread force kill failed: {e}")
            return False

        # Final check
        billing_thread.join(timeout=0.2)
        if billing_thread.is_alive():
            logger.error("Thread still alive - container will delay shutdown")
            return False
        else:
            logger.info("Force kill successful")
            return True

    def _handle_final_billing_increment_with_cleanup(
        self, cleanup_elapsed: float
    ) -> None:
        """Calculate and apply final billing increment including cleanup time."""
        if not self._last_billing_time:
            logger.warning("ℹ️ No last billing time recorded, skipping final increment")
            return

        # Calculate time from last billing to when cleanup started
        cleanup_start_time = time.time() - cleanup_elapsed
        pre_cleanup_elapsed = max(0, cleanup_start_time - self._last_billing_time)

        # Total time includes pre-cleanup work + cleanup operations
        total_final_time = pre_cleanup_elapsed + cleanup_elapsed

        # If there's a large gap (>10s) between last billing and cleanup start,
        # this likely indicates the thread stopped due to a container change.
        # We should NOT bill for this gap time - it was correctly skipped by the billing loop.
        if pre_cleanup_elapsed > LARGE_GAP_THRESHOLD_SECONDS:
            logger.warning(
                f"⚠️  Large gap detected in final increment ({pre_cleanup_elapsed:.6f}s). "
                f"This likely indicates the thread stopped due to container change. "
                f"Skipping final increment to prevent over-billing. "
                f"(Only billing for cleanup time: {cleanup_elapsed:.6f}s if > 0.001s)"
            )
            # Only bill for cleanup time if it's significant (not the gap time)
            if cleanup_elapsed > 0.001:
                logger.info(
                    f"💰 FINAL increment (cleanup only): {cleanup_elapsed:.6f}s "
                    f"(skipped gap time: {pre_cleanup_elapsed:.6f}s)"
                )
                self._atomic_increment_usage(cleanup_elapsed)
                self._last_billing_time = time.time()
            else:
                logger.info(
                    f"🔄 Skipping final increment: gap={pre_cleanup_elapsed:.6f}s (container change), "
                    f"cleanup={cleanup_elapsed:.6f}s (too small)"
                )
            return

        # More precise double billing prevention
        min_billable_time = 0.001  # 1ms minimum
        if total_final_time > min_billable_time:
            logger.info(
                f"💰 FINAL increment: {total_final_time:.6f}s (pre-cleanup: {pre_cleanup_elapsed:.6f}s + cleanup: {cleanup_elapsed:.6f}s)"
            )
            self._atomic_increment_usage(total_final_time)
            self._last_billing_time = time.time()
        else:
            logger.info(
                f"🔄 Skipping final increment: {total_final_time:.6f}s (too small, likely already billed)"
            )

    def _send_final_accumulated_usage(self) -> None:
        """Send any remaining accumulated usage with multiple retry attempts."""
        if self._accumulated_usage <= 0:
            return

        logger.info(
            f"📊 Sending final accumulated usage: {self._accumulated_usage:.6f}s"
        )

        for attempt in range(2):
            try:
                timeout_changed, old_timeout = self._set_redis_timeout_temporarily(0.5)
                success = self._try_send_accumulated_usage()

                if timeout_changed:
                    self._restore_redis_timeout(old_timeout)

                if success:
                    break
                else:
                    logger.warning(f"Final send attempt {attempt + 1}/2 failed")

            except Exception as e:
                logger.warning(f"Final send attempt {attempt + 1}/2 error: {e}")
                if attempt == 1:  # Last attempt
                    logger.error(
                        f"💀 LOST {self._accumulated_usage:.6f}s accumulated usage due to Redis failure"
                    )

    def _set_redis_timeout_temporarily(
        self, timeout_seconds: float
    ) -> tuple[bool, float]:
        """Safely set Redis timeout temporarily, returning (changed, old_timeout)."""
        try:
            with self._redis_lock:
                if self._redis_client and hasattr(
                    self._redis_client, "connection_pool"
                ):
                    pool = self._redis_client.connection_pool
                    if (
                        hasattr(pool, "connection_kwargs")
                        and "socket_timeout" in pool.connection_kwargs
                    ):
                        old_timeout = pool.connection_kwargs.get("socket_timeout", 5)
                        pool.connection_kwargs["socket_timeout"] = timeout_seconds
                        return True, old_timeout
        except Exception as e:
            logger.warning(f"Could not set Redis timeout: {e}, using default")
        return False, 5.0

    def _restore_redis_timeout(self, old_timeout: float) -> None:
        """Safely restore Redis timeout to previous value."""
        try:
            with self._redis_lock:
                if self._redis_client and hasattr(
                    self._redis_client, "connection_pool"
                ):
                    pool = self._redis_client.connection_pool
                    if hasattr(pool, "connection_kwargs"):
                        pool.connection_kwargs["socket_timeout"] = old_timeout
        except Exception as e:
            logger.warning(f"Could not restore Redis timeout: {e}")

    def _cleanup_resources(self) -> None:
        """Clean up tracking files and Redis connections."""
        # Close Redis connection
        with self._redis_lock:
            if self._redis_client:
                close_redis_client(self._redis_client)
                self._redis_client = None

    def stop_billing(self) -> None:
        """
        Stop billing with proper cleanup, final increment handling, and forcible thread termination.

        Accurately bills for ALL container resource usage including cleanup operations by:
        1. Calculating final increment from last billing time to cleanup start
        2. Adding actual time spent on cleanup operations (network, file I/O, etc.)
        3. Ensuring no container usage time is missed or double-billed
        """
        with self._state_lock:
            if not self._is_started or self._is_stopped:
                return  # Already stopped or never started

            logger.info("🛑 Stopping billing service...")
            self._stop_event.set()
            billing_thread = self._billing_thread

        # Handle thread termination outside of lock
        thread_stopped_cleanly = self._handle_thread_termination(billing_thread)

        # Track cleanup time to bill accurately for it
        cleanup_start_time = time.time()

        # Handle cleanup operations that still consume container resources
        with self._state_lock:
            self._send_final_accumulated_usage()
            self._cleanup_resources()

            # Calculate actual time spent on cleanup operations
            cleanup_elapsed = time.time() - cleanup_start_time

            # Apply final increment that includes cleanup time
            self._handle_final_billing_increment_with_cleanup(cleanup_elapsed)

            # Final state cleanup
            self._is_stopped = True
            old_thread = self._billing_thread
            self._billing_thread = None

            status = "cleanly" if thread_stopped_cleanly else "forcibly"

            # Log total billing summary for debugging over-billing issues
            total_billed = getattr(self, "_total_billed_time", 0.0)

            # Calculate service lifetime from actual container start (accounts for pre-Redis time)
            # If we tracked container start time, use it; otherwise fall back to _start_time
            container_start = self._container_start_time or self._start_time
            if container_start:
                service_lifetime = time.time() - container_start
            else:
                service_lifetime = time.time() - (self._start_time or time.time())

            billing_efficiency = (
                (total_billed / service_lifetime * 100) if service_lifetime > 0 else 0
            )
            gap_time = service_lifetime - total_billed

            # Get phase information if available
            is_snapshot_restore = getattr(self, "_is_snapshot_restore", False)
            phase = "restore" if is_snapshot_restore else "creation"

            logger.info(
                f"📊 Billing service summary: total_billed={total_billed:.6f}s, "
                f"service_lifetime={service_lifetime:.6f}s, "
                f"gap_time={gap_time:.6f}s, "
                f"billing_efficiency={billing_efficiency:.1f}%, "
                f"phase={phase}, "
                f"container_id={self._container_id[:50] if self._container_id else None}"
            )

            if old_thread:
                logger.info(
                    f"Billing service stopped {status} | "
                    f"thread_name={old_thread.name}, thread_id={old_thread.ident}, "
                    f"is_alive={old_thread.is_alive()}"
                )
            else:
                logger.info(f"Billing service stopped {status}")

    def __del__(self):
        """Cleanup on object destruction with aggressive thread termination."""
        if hasattr(self, "_is_started") and self._is_started and not self._is_stopped:
            logger.debug("🧹 Emergency billing cleanup on object destruction")
            self.stop_billing()
