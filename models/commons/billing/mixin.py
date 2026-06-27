import inspect
import json
import os
import threading
import time
from typing import Optional

import modal

from models.commons.billing.service import (
    BillingService,
    logger,
    parse_snapshot_uptime_file,
)

"""
Billing mixin classes for Modal containers.

This module provides mixin classes that add billing functionality to Modal
container classes with proper thread safety and cleanup.
"""


class BillingMixinBase:
    """
    Base mixin class with non-modal billing functionality.

    This class contains all the core billing logic without Modal decorators,
    making it suitable for use in non-Modal contexts like clustered classes.

    Usage:
        class MyClass(BillingMixinBase):
            def __init__(self):
                self.app_username = "my_user"

            def start_work(self):
                self._billing_enter()
                # Your work here

            def finish_work(self):
                self._billing_exit()
    """

    def _get_app_name_from_module(self) -> str:
        """Get app_name from the module where this class is defined."""
        try:
            # Get the module where this class is defined
            class_module = inspect.getmodule(self.__class__)
            if class_module and hasattr(class_module, "app_name"):
                return class_module.app_name
        except Exception as e:
            logger.warning(f"Could not get app_name from module: {e}")

        # Fallback: try to derive from file path
        return self._get_app_name_from_file_path()

    def _get_app_name_from_file_path(self) -> str:
        """Fallback: derive app name from file path."""
        try:
            class_module = inspect.getmodule(self.__class__)
            if class_module and hasattr(class_module, "__file__"):
                file_path = class_module.__file__
                # Extract model name from path like "models/antifold/app.py"
                path_parts = file_path.split("/")
                if "models" in path_parts:
                    model_index = path_parts.index("models")
                    if model_index + 1 < len(path_parts):
                        return path_parts[model_index + 1]
        except Exception as e:
            logger.warning(f"Could not derive app_name from file path: {e}")

        return "unknown-app"

    def _identify_background_threads(self) -> list:
        """Identify potentially problematic background threads."""
        problematic_threads = []
        main_thread = threading.main_thread()
        current_thread = threading.current_thread()

        for thread in threading.enumerate():
            # Skip main thread and current thread
            if thread in (main_thread, current_thread):
                continue

            # Skip our billing thread (handled separately)
            if hasattr(self, "billing_service") and self.billing_service:
                if (
                    hasattr(self.billing_service, "_billing_thread")
                    and thread == self.billing_service._billing_thread
                ):
                    continue

            # Identify potentially problematic threads
            is_problematic = (
                thread.is_alive()
                and not thread.daemon  # Non-daemon threads prevent shutdown
                and not thread.name.startswith("_")  # Skip private threads
            )

            if is_problematic or thread.name in [
                "ThreadPoolExecutor",
                "ProcessPoolExecutor",
                "TritonCompiler",
                "CUDAContext",
                "AsyncEventLoop",
                "RedisConnectionPool",
                "HTTPSConnectionPool",
            ]:
                problematic_threads.append(
                    {
                        "thread": thread,
                        "name": thread.name,
                        "daemon": thread.daemon,
                        "alive": thread.is_alive(),
                        "ident": thread.ident,
                    }
                )

        return problematic_threads

    def _should_terminate_thread(
        self, thread, thread_name: str, aggressive: bool
    ) -> bool:
        """Determine if a thread should be terminated based on its properties."""
        try:
            return not thread.daemon or (  # Non-daemon threads definitely block
                aggressive
                and any(
                    keyword in thread_name.lower()
                    for keyword in [
                        "pool",
                        "worker",
                        "executor",
                        "connection",
                        "compiler",
                    ]
                )
            )
        except Exception as e:
            logger.warning(
                f"Cannot determine if thread {thread_name} should terminate: {e}"
            )
            return not thread.daemon  # Conservative fallback

    def _process_single_background_thread(self, t_info: dict, aggressive: bool) -> bool:
        """Process a single background thread for cleanup. Returns True if successful."""
        try:
            thread = t_info["thread"]
            thread_name = t_info.get("name", "<unknown>")

            # Skip if thread is already dead
            try:
                if not thread.is_alive():
                    logger.info(f"Thread {thread_name} already dead, skipping")
                    return True
            except Exception as e:
                logger.warning(f"Cannot check if thread {thread_name} is alive: {e}")
                return False

            # Check if we should terminate this thread
            if self._should_terminate_thread(thread, thread_name, aggressive):
                return self._terminate_single_thread(thread, thread_name)
            else:
                logger.info(f"🔄 Skipping daemon thread: {thread_name}")
                return True

        except Exception as e:
            logger.warning(f"Error processing thread cleanup: {e}")
            return False

    def _force_cleanup_background_threads(self, aggressive: bool = False) -> None:
        """
        Cleanup background threads that might prevent container shutdown.
        Robust exception handling ensures this never prevents container exit.

        Args:
            aggressive: If True, also kills daemon threads and library threads
        """
        try:
            logger.debug(
                "🧹 Checking for background threads that might delay container shutdown..."
            )

            try:
                problematic_threads = self._identify_background_threads()
            except Exception as e:
                logger.warning(f"Failed to identify background threads: {e}")
                return

            if not problematic_threads:
                logger.info("No problematic background threads found")
                return

            logger.warning(
                f"Found {len(problematic_threads)} potentially problematic threads:"
            )
            for t_info in problematic_threads:
                try:
                    logger.info(
                        f"   - {t_info['name']} (daemon={t_info['daemon']}, alive={t_info['alive']})"
                    )
                except Exception as e:
                    logger.error(f"   - <thread info error: {e}>")

            # Process each thread independently
            threads_cleaned = 0
            threads_failed = 0

            for t_info in problematic_threads:
                if self._process_single_background_thread(t_info, aggressive):
                    threads_cleaned += 1
                else:
                    threads_failed += 1

            logger.debug(
                f"🧹 Thread cleanup complete: {threads_cleaned} cleaned, {threads_failed} failed"
            )

        except Exception as e:
            logger.warning(f"Critical error in background thread cleanup: {e}")
            logger.info(
                "🔄 Continuing with container exit despite thread cleanup failure"
            )

    def _try_graceful_thread_shutdown(self, thread, thread_name: str) -> bool:
        """Try graceful thread shutdown with short timeout. Returns True if successful."""
        try:
            if hasattr(thread, "join"):
                thread.join(timeout=0.1)
                try:
                    if not thread.is_alive():
                        logger.info(f"Thread {thread_name} stopped gracefully")
                        return True
                except Exception as e:
                    logger.warning(
                        f"Cannot verify if {thread_name} stopped gracefully: {e}"
                    )
        except Exception as e:
            logger.warning(f"Graceful join failed for {thread_name}: {e}")
        return False

    def _force_kill_thread_with_systemexit(self, thread, thread_name: str) -> bool:
        """Force kill thread using SystemExit injection. Returns True if successful."""
        try:
            import ctypes

            # Get thread identifier safely
            try:
                thread_ident = thread.ident
                if thread_ident is None:
                    logger.warning(
                        f"Thread {thread_name} has no identifier, cannot force kill"
                    )
                    return False
            except Exception as e:
                logger.warning(f"Cannot get identifier for thread {thread_name}: {e}")
                return False

            res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_long(thread_ident), ctypes.py_object(SystemExit)
            )

            if res == 1:
                logger.info(f"Sent SystemExit to thread: {thread_name}")
                return self._verify_thread_termination(thread, thread_name)
            elif res == 0:
                logger.warning(f"Thread ID not found for {thread_name}")
                return False
            else:
                # Too many threads affected, rollback
                try:
                    ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_ident, None)
                    logger.warning(
                        f"Force kill of {thread_name} affected multiple threads, rolled back"
                    )
                except Exception as rollback_e:
                    logger.warning(
                        f"Failed to rollback force kill for {thread_name}: {rollback_e}"
                    )
                return False

        except ImportError:
            logger.warning(f"ctypes not available, cannot force kill {thread_name}")
            return False
        except Exception as e:
            logger.warning(f"Force termination failed for {thread_name}: {e}")
            return False

    def _verify_thread_termination(self, thread, thread_name: str) -> bool:
        """Verify that thread termination was successful."""
        try:
            time.sleep(0.05)
            if not thread.is_alive():
                logger.info(f"Thread {thread_name} terminated successfully")
                return True
            else:
                logger.warning(f"Thread {thread_name} still alive after SystemExit")
                return False
        except Exception as e:
            logger.warning(f"Cannot verify termination of {thread_name}: {e}")
            return False

    def _terminate_single_thread(self, thread, thread_name: str) -> bool:
        """
        Terminate a single thread with comprehensive error handling.
        Returns True if successful, False otherwise.
        """
        try:
            logger.debug(f"🔥 Attempting to terminate thread: {thread_name}")

            # First try graceful shutdown
            if self._try_graceful_thread_shutdown(thread, thread_name):
                return True

            # Force termination if still alive
            return self._force_kill_thread_with_systemexit(thread, thread_name)

        except Exception as e:
            logger.warning(f"Critical error terminating thread {thread_name}: {e}")
            return False

    def _billing_enter(self, resource_metadata: Optional[dict] = None) -> None:
        """Start background billing for this container."""
        try:
            # Get app name and class name
            app_name = self._get_app_name_from_module()
            class_name = self.__class__.__name__
            username = getattr(self, "app_username", "default_user")

            # Get resource metadata if not provided
            if resource_metadata is None:
                resource_metadata = getattr(self, "resource_metadata", {})

            # Initialize billing service
            self.billing_service = BillingService(
                app_name=app_name,
                class_name=class_name,
                username=username,
                resource_metadata=resource_metadata,
            )

            # Pass early_uptime and restore flag to billing service if available
            if hasattr(self, "_early_uptime") and self._early_uptime is not None:
                self.billing_service._early_uptime = self._early_uptime
                logger.info(
                    f"📊 Passed early uptime to billing service: {self._early_uptime:.6f}s"
                )
            if hasattr(self, "_is_snapshot_restore"):
                self.billing_service._is_snapshot_restore = self._is_snapshot_restore

            # Start billing
            success = self.billing_service.start_billing()
            if not success:
                logger.warning("Failed to start billing service")
        except Exception as e:
            logger.warning(f"Error starting billing service: {e}")

    def _billing_exit(
        self, cleanup_other_threads: bool = True, aggressive_cleanup: bool = False
    ) -> None:
        """
        @modal.exit() method that cleans up resources and stops billing.

        Stop background billing and optionally cleanup other background threads.
        Designed to never fail - billing cleanup is prioritized over thread cleanup.
        Now tracks ALL cleanup time for accurate billing by delaying billing service shutdown.

        Args:
            cleanup_other_threads: Whether to check for and cleanup other background threads
            aggressive_cleanup: Whether to aggressively terminate daemon threads too
        """
        billing_success = False
        thread_cleanup_success = False
        total_exit_start_time = time.time()

        try:
            # Track overall cleanup time first - billing service stays active during cleanup
            if cleanup_other_threads:
                thread_cleanup_start = time.time()
                try:
                    logger.debug(
                        "🧹 Starting background thread cleanup (billing service still active)..."
                    )
                    self._force_cleanup_background_threads(
                        aggressive=aggressive_cleanup
                    )
                    thread_cleanup_elapsed = time.time() - thread_cleanup_start
                    thread_cleanup_success = True
                    logger.info(
                        f"Background thread cleanup completed in {thread_cleanup_elapsed:.6f}s"
                    )

                except Exception as e:
                    thread_cleanup_elapsed = time.time() - thread_cleanup_start
                    logger.error(
                        f"Error during background thread cleanup after {thread_cleanup_elapsed:.6f}s: {e}"
                    )
                    logger.info("🔄 Thread cleanup failed but container can still exit")
            else:
                logger.info("ℹ️ Background thread cleanup skipped")
                thread_cleanup_success = True

            # NOW stop the billing service - it will include all the cleanup time in its final increment
            logger.info("🛑 Stopping billing service (after all cleanup completed)...")
            try:
                if hasattr(self, "billing_service") and self.billing_service:
                    self.billing_service.stop_billing()
                    billing_success = True
                    logger.info("Billing service stopped successfully")
                else:
                    logger.info("ℹ️ No billing service to stop")
                    billing_success = True
            except Exception as e:
                logger.warning(f"Error stopping billing service: {e}")
                billing_success = False

        except Exception as e:
            total_elapsed = time.time() - total_exit_start_time
            logger.warning(
                f"Critical error during billing/thread cleanup after {total_elapsed:.6f}s: {e}"
            )
            logger.info("🔄 Continuing with container exit despite cleanup errors")

        # Final status report
        total_exit_time = time.time() - total_exit_start_time
        if billing_success and thread_cleanup_success:
            logger.info(
                f"All cleanup operations completed successfully in {total_exit_time:.6f}s"
            )
        elif billing_success:
            logger.warning(
                f"Billing cleanup succeeded, thread cleanup had issues (total: {total_exit_time:.6f}s)"
            )
        elif thread_cleanup_success:
            logger.warning(
                f"Thread cleanup succeeded, billing cleanup had issues (total: {total_exit_time:.6f}s)"
            )
        else:
            logger.warning(
                f"Both billing and thread cleanup had issues, but container can exit (total: {total_exit_time:.6f}s)"
            )

    def _check_for_orphaned_billing_threads(self) -> None:
        """Check for orphaned billing threads that might still be running."""
        try:
            all_threads = threading.enumerate()
            billing_threads = [
                t for t in all_threads if t.name and t.name.startswith("BillingThread-")
            ]

            current_thread = None
            if hasattr(self, "billing_service") and self.billing_service:
                if hasattr(self.billing_service, "_billing_thread"):
                    current_thread = self.billing_service._billing_thread

            if len(billing_threads) > 1:
                logger.warning(
                    f"⚠️  Found {len(billing_threads)} billing threads (expected 0-1): "
                    f"{[f'{t.name}(id={t.ident}, alive={t.is_alive()})' for t in billing_threads]}"
                )
                # Log which ones are orphaned
                for thread in billing_threads:
                    if thread != current_thread:
                        logger.warning(
                            f"⚠️  Potential orphaned billing thread: name={thread.name}, "
                            f"thread_id={thread.ident}, is_alive={thread.is_alive()}"
                        )
            elif len(billing_threads) == 1:
                thread = billing_threads[0]
                if thread == current_thread:
                    logger.debug(
                        f"✅ Found 1 billing thread (expected): name={thread.name}, "
                        f"thread_id={thread.ident}, is_alive={thread.is_alive()}"
                    )
                else:
                    logger.warning(
                        f"⚠️  Found 1 billing thread but it's not the current one! "
                        f"Found: name={thread.name}, thread_id={thread.ident}, "
                        f"Current: name={current_thread.name if current_thread else None}, "
                        f"thread_id={current_thread.ident if current_thread else None}"
                    )
            else:
                logger.debug(
                    "✅ No billing threads found (expected if billing not started)"
                )
        except Exception as e:
            logger.warning(f"Error checking for orphaned billing threads: {e}")

    def save_snapshot_uptime(self) -> None:
        """
        Save current container uptime, container ID, and timestamp to snapshot file for memory snapshot billing.
        This allows us to detect if we're restoring from a snapshot (different container ID) vs creating a new snapshot.
        Call this in your @modal.enter(snap=True) method to ensure accurate billing.
        """
        try:
            # Get container ID if billing service exists
            container_id = None
            if hasattr(self, "billing_service") and self.billing_service:
                container_id = getattr(self.billing_service, "_container_id", None)

            # Get uptime and current timestamp
            with open("/proc/uptime") as uptime_file:
                uptime_seconds = float(uptime_file.read().strip().split()[0])

            current_timestamp = time.time()

            # Save as JSON with container metadata
            snapshot_data = {
                "uptime_seconds": uptime_seconds,
                "container_id": container_id,
                "timestamp_utc": current_timestamp,
            }

            with open("/var/snapshot_uptime", "w") as f:
                json.dump(snapshot_data, f)

            logger.info(
                f"📸 Snapshot metadata saved: uptime={uptime_seconds:.6f}s, "
                f"container_id={container_id[:50] if container_id else None}, "
                f"timestamp={current_timestamp:.6f}"
            )
        except Exception as e:
            logger.warning(f"Failed to save snapshot uptime: {e}")

    @modal.enter(snap=False)
    def billing_enter(self) -> None:
        """Start billing service with Modal decorator."""
        try:
            modal_function_call_id = modal.current_function_call_id()
            modal_input_id = modal.current_input_id()
        except Exception:
            modal_function_call_id = None
            modal_input_id = None

        # For BillingMixinSnap: a_billing_enter(snap=True) bills for snap creation
        # When we restore, the old billing thread from a_billing_enter is still running
        # We need to stop it and start a new one for the restore phase
        # Check if this is BillingMixinSnap by checking class MRO (safer than hasattr with Modal proxies)
        is_billing_mixin_snap = any(
            cls.__name__ == "BillingMixinSnap" for cls in type(self).__mro__
        )

        if is_billing_mixin_snap:
            # Check if billing service already exists (from a_billing_enter during snap creation)
            if hasattr(self, "billing_service") and self.billing_service is not None:
                logger.info(
                    f"🔵 [BILLING_ENTER] billing_enter(snap=False) called for {self.__class__.__name__} | "
                    f"Stopping old billing thread from a_billing_enter (snap creation phase) and starting new one (restore phase)"
                )
                # Stop the old billing service (from snap creation)
                old_billing_service = self.billing_service
                old_thread = None
                if old_billing_service and hasattr(
                    old_billing_service, "_billing_thread"
                ):
                    old_thread = old_billing_service._billing_thread
                    old_thread_name = old_thread.name if old_thread else None
                    old_thread_id = old_thread.ident if old_thread else None
                    old_container_id = getattr(
                        old_billing_service, "_container_id", None
                    )
                    logger.info(
                        f"🛑 Stopping old billing service: thread_name={old_thread_name}, "
                        f"thread_id={old_thread_id}, container_id={old_container_id[:50] if old_container_id else None}, "
                        f"is_alive={old_thread.is_alive() if old_thread else False}"
                    )

                self._billing_exit(
                    cleanup_other_threads=False, aggressive_cleanup=False
                )

                # Verify old thread is actually stopped and check for orphaned threads
                if old_thread:
                    time.sleep(0.1)  # Give thread a moment to stop
                    is_still_alive = old_thread.is_alive()
                    logger.info(
                        f"✅ Verification: old billing thread stopped | "
                        f"thread_name={old_thread.name}, thread_id={old_thread.ident}, "
                        f"is_alive={is_still_alive} (should be False)"
                    )
                    if is_still_alive:
                        logger.warning(
                            f"⚠️  WARNING: Old billing thread is still alive after stop attempt! "
                            f"This may indicate an orphaned thread. thread_name={old_thread.name}, "
                            f"thread_id={old_thread.ident}"
                        )

                # Check for any orphaned billing threads
                self._check_for_orphaned_billing_threads()
            else:
                # Billing not started yet - this is a restore-only call
                logger.info(
                    f"🔵 [BILLING_ENTER] billing_enter(snap=False) called for {self.__class__.__name__} | "
                    f"Restore-only call, starting billing"
                )
        else:
            # Not BillingMixinSnap - just start billing normally
            logger.info(
                f"🔵 [BILLING_ENTER] billing_enter(snap=False) called for {self.__class__.__name__} | "
                f"function_call_id={modal_function_call_id}, input_id={modal_input_id}"
            )

        # Start billing (or restart after stopping old one)
        self._billing_enter()

        # After starting new billing, verify no orphaned threads
        if hasattr(self, "billing_service") and self.billing_service:
            self._check_for_orphaned_billing_threads()

    @modal.exit()
    def billing_exit(self) -> None:
        """Stop billing service with Modal decorator."""
        self._billing_exit()


class BillingMixin(BillingMixinBase):
    """
    Thread-safe mixin class to add billing functionality to Modal container classes.

    Usage:
        @app.cls(...)
        class MyModel(BillingMixin):
            app_username: str = modal.parameter(default="default_user")

            @modal.enter()
            def setup_model(self):
                # Start billing
                self.billing_enter()

                # Your existing setup code here
                ...

            @modal.exit()
            def cleanup_model(self):
                # Stop billing and optionally cleanup other threads
                self.billing_exit()

                # Your existing cleanup code here
                ...
    """

    @modal.method()
    def is_live(self) -> int:
        return 1

    @modal.method()
    def healthy(self) -> dict:
        """
        Health check endpoint for Modal containers.

        Returns:
            dict: Health status including billing service state, container info, and system metrics.
        """
        import time

        import psutil

        try:
            # Basic health indicators
            health_status = {
                "status": "healthy",
                "timestamp": time.time(),
                "container_id": (
                    getattr(self.billing_service, "_container_id", None)
                    if hasattr(self, "billing_service") and self.billing_service
                    else None
                ),
                "billing_active": hasattr(self, "billing_service")
                and self.billing_service
                and getattr(self.billing_service, "_is_started", False),
                "app_name": self._get_app_name_from_module(),
                "class_name": self.__class__.__name__,
                "username": getattr(self, "app_username", "default_user"),
            }

            # System metrics
            try:
                health_status["system"] = {
                    "cpu_percent": psutil.cpu_percent(interval=0.1),
                    "memory_percent": psutil.virtual_memory().percent,
                    "disk_percent": psutil.disk_usage("/").percent,
                    "load_avg": (
                        psutil.getloadavg() if hasattr(psutil, "getloadavg") else None
                    ),
                }
            except Exception as e:
                health_status["system"] = {"error": str(e)}

            # Billing service details
            if hasattr(self, "billing_service") and self.billing_service:
                billing_service = self.billing_service
                with billing_service._state_lock:
                    health_status["billing"] = {
                        "is_started": billing_service._is_started,
                        "is_stopped": billing_service._is_stopped,
                        "start_time": billing_service._start_time,
                        "last_billing_time": billing_service._last_billing_time,
                        "accumulated_usage": billing_service._accumulated_usage,
                        "billing_interval": billing_service.billing_interval,
                        "container_id": billing_service._container_id,
                        "thread_alive": (
                            billing_service._billing_thread.is_alive()
                            if billing_service._billing_thread
                            else False
                        ),
                    }

                # Redis connection status
                try:
                    with billing_service._get_redis_client() as redis_client:
                        if redis_client:
                            redis_client.ping()
                            health_status["redis"] = {"status": "connected"}
                        else:
                            health_status["redis"] = {"status": "disconnected"}
                except Exception as e:
                    health_status["redis"] = {"status": "error", "error": str(e)}
            else:
                health_status["billing"] = {"status": "not_initialized"}
                health_status["redis"] = {"status": "not_available"}

            # Container uptime
            try:
                with open("/proc/uptime") as f:
                    uptime_seconds = float(f.read().split()[0])
                health_status["uptime_seconds"] = uptime_seconds
            except Exception as e:
                health_status["uptime_error"] = str(e)

            return health_status

        except Exception as e:
            # Fallback health response
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time(),
                "class_name": self.__class__.__name__,
            }


class BillingMixinSnap(BillingMixin):
    """
    Billing mixin for Modal containers with memory snapshots.

    This class overrides billing_enter to prevent it from running,
    since it uses a_billing_enter and z_billing_enter instead.
    """

    def _get_modal_metadata_for_enter(self) -> dict:
        """Get Modal metadata for enter context (function_call_id, input_id, is_enter_context)."""
        try:
            modal_function_call_id = modal.current_function_call_id()
            modal_input_id = modal.current_input_id()
            is_enter_context = modal_function_call_id is None and modal_input_id is None
        except Exception:
            modal_function_call_id = None
            modal_input_id = None
            is_enter_context = None

        logger.info(
            f"🟢 [BILLING_ENTER] a_billing_enter(snap=True) called for {self.__class__.__name__} | "
            f"function_call_id={modal_function_call_id}, input_id={modal_input_id}, "
            f"is_enter_context={is_enter_context} (True=snap creation, False=snap restore)"
        )

        return {
            "modal_function_call_id": modal_function_call_id,
            "modal_input_id": modal_input_id,
            "is_enter_context": is_enter_context,
        }

    def _record_initial_billing_entry(self) -> None:
        """Record initial billing entry metadata to touch file."""
        entry_touch_file = "/var/billing_entry.touch"
        try:
            entry_timestamp = time.time()
            entry_metadata = {
                "timestamp": entry_timestamp,
                "app_name": self._get_app_name_from_module(),
                "class_name": self.__class__.__name__,
            }
            with open(entry_touch_file, "w") as f:
                json.dump(entry_metadata, f)
            logger.info(
                f"📝 Recorded billing entry metadata: {entry_metadata} (file: {entry_touch_file})"
            )
        except Exception as e:
            logger.warning(f"Could not write billing entry metadata: {e}")

    def _check_snapshot_file_for_restore(self) -> Optional[str]:
        """
        Check snapshot file to detect if this is a restore.

        Returns:
            snapshot_container_id if found, None otherwise. Sets self._is_snapshot_restore flag.
        """
        snapshot_data = parse_snapshot_uptime_file()
        if snapshot_data is None:
            return None

        snapshot_container_id = snapshot_data.get("container_id")
        uptime = snapshot_data.get("uptime_seconds")
        preliminary_restore_detected = False

        if snapshot_data["format"] == "json":
            logger.info(
                f"📸 Snapshot file found (JSON): container_id={snapshot_container_id[:50] if snapshot_container_id else None}, "
                f"uptime={uptime:.6f}s, timestamp={snapshot_data.get('timestamp_utc'):.6f}"
            )
            if snapshot_container_id:
                preliminary_restore_detected = True
                logger.info(
                    "📸 Snapshot file has container ID - will verify restore after billing starts"
                )
        else:
            logger.info(f"📸 Snapshot file found (old format): uptime={uptime:.6f}s")
            # Old format - assume restore (can't compare container IDs)
            preliminary_restore_detected = True
            logger.info(
                "📸 Old format snapshot file - assuming restore (will skip initial increment)"
            )

        if preliminary_restore_detected:
            self._is_snapshot_restore = True
            logger.info(
                "📸 Set preliminary restore flag on self - start_billing will check this first"
            )

        return snapshot_container_id

    def _get_and_store_early_uptime(self) -> None:
        """Get early uptime for fresh starts and store it, capped at 60s."""
        try:
            # Try to get uptime using the same methods as _get_container_uptime
            # We'll create a temporary billing service just to use its uptime method
            from models.commons.billing.service import BillingService

            temp_service = BillingService(
                app_name=self._get_app_name_from_module(),
                class_name=self.__class__.__name__,
                username=getattr(self, "app_username", "default_user"),
            )
            early_uptime = temp_service._get_container_uptime()

            # Safety check: cap early uptime at 60s to prevent over-billing
            # If uptime is > 60s, it's likely host PID 1 uptime, not container uptime
            if early_uptime > 60.0:
                logger.warning(
                    f"⚠️  Early uptime is suspiciously large: {early_uptime:.6f}s. "
                    f"This may be host PID 1 uptime. Capping at 60s to prevent over-billing."
                )
                early_uptime = 60.0

            # Store this uptime so start_billing can use it
            self._early_uptime = early_uptime
            logger.info(
                f"📊 Got early uptime in a_billing_enter: {early_uptime:.6f}s "
                f"(to account for time before Redis connects)"
            )
        except Exception as e:
            logger.warning(f"Could not get early uptime: {e}")
            self._early_uptime = None

    def _update_entry_file_with_container_id(
        self, current_container_id: Optional[str]
    ) -> None:
        """Update entry file with container ID and billing_container_id."""
        entry_touch_file = "/var/billing_entry.touch"
        try:
            if os.path.exists(entry_touch_file):
                with open(entry_touch_file) as f:
                    entry_metadata = json.load(f)
                entry_metadata["container_id"] = current_container_id
                # CRITICAL: Also update billing_container_id here so old threads can detect container change immediately
                if current_container_id:
                    entry_metadata["billing_container_id"] = current_container_id
                with open(entry_touch_file, "w") as f:
                    json.dump(entry_metadata, f)
                logger.info(
                    f"📝 Updated billing entry metadata with container_id and billing_container_id: {current_container_id[:50] if current_container_id else None}"
                )
        except Exception as e:
            logger.warning(
                f"Could not update billing entry metadata with container ID: {e}"
            )

    def _get_modal_process_metadata(self) -> dict:
        """Get Modal process metadata (process_id, task_id) from environment variables."""
        modal_process_id = None
        modal_task_id = None

        try:
            # Try to get container process info if available
            # Modal may expose process_id and task_id through environment variables
            modal_process_id = os.getpid()  # At least get the OS process ID

            # Try to get Modal's process_id and task_id from environment variables
            # These might be available in Modal containers
            try:
                # Check common Modal environment variable patterns
                modal_task_id = os.environ.get("MODAL_TASK_ID") or os.environ.get(
                    "_MODAL_TASK_ID"
                )
                modal_container_process_id = os.environ.get(
                    "MODAL_PROCESS_ID"
                ) or os.environ.get("_MODAL_PROCESS_ID")

                # Also check for other potential Modal environment variables
                # Log all MODAL_* env vars for debugging (first time only, to avoid spam)
                if not hasattr(self, "_modal_env_vars_logged"):
                    modal_env_vars = {
                        k: v for k, v in os.environ.items() if "MODAL" in k.upper()
                    }
                    if modal_env_vars:
                        logger.debug(
                            f"📊 Available Modal environment variables: {list(modal_env_vars.keys())}"
                        )
                    self._modal_env_vars_logged = True

                # If we found Modal's process_id, use it instead of os.getpid()
                if modal_container_process_id:
                    modal_process_id = modal_container_process_id
            except Exception:
                pass  # Environment variables might not be available
        except Exception as e:
            logger.debug(f"Could not get process ID in a_billing_enter: {e}")
            modal_process_id = None
            modal_task_id = None

        return {
            "modal_process_id": modal_process_id,
            "modal_task_id": modal_task_id,
        }

    def _record_billing_enter_metadata(
        self,
        file_path: str,
        label: str,
        current_container_id: Optional[str],
    ) -> None:
        """Write billing enter metadata file with container ID, UTC time, and Modal metadata.

        Args:
            file_path: Path to write the metadata file (e.g., /var/billing_a_enter.touch)
            label: Human-readable label for log messages (e.g., "a_billing_enter")
            current_container_id: Current billing container ID
        """
        try:
            modal_function_call_id = None
            modal_input_id = None

            try:
                modal_function_call_id = modal.current_function_call_id()
            except Exception as e:
                logger.debug(
                    f"Could not get modal.current_function_call_id in {label}: {e}"
                )

            try:
                modal_input_id = modal.current_input_id()
            except Exception as e:
                logger.debug(f"Could not get modal.current_input_id in {label}: {e}")

            process_metadata = self._get_modal_process_metadata()
            modal_process_id = process_metadata["modal_process_id"]
            modal_task_id = process_metadata["modal_task_id"]

            is_enter_context = modal_function_call_id is None and modal_input_id is None

            metadata = {
                "container_id": current_container_id,
                "timestamp_utc": time.time(),
                "modal_function_call_id": modal_function_call_id,
                "modal_input_id": modal_input_id,
                "process_id": modal_process_id,
                "modal_task_id": modal_task_id,
                "is_enter_context": is_enter_context,
            }
            with open(file_path, "w") as f:
                json.dump(metadata, f)
            logger.info(
                f"📝 Recorded {label}: container_id={current_container_id[:50] if current_container_id else None}, "
                f"timestamp_utc={metadata['timestamp_utc']:.6f}, "
                f"function_call_id={modal_function_call_id}, input_id={modal_input_id}, "
                f"process_id={modal_process_id}, task_id={modal_task_id}, "
                f"is_enter_context={is_enter_context} (file: {file_path})"
            )
        except Exception as e:
            logger.warning(f"Could not write {label} metadata: {e}")

    def _record_a_billing_enter_metadata(
        self, current_container_id: Optional[str]
    ) -> None:
        """Write a_billing_enter file with container ID, UTC time, and Modal metadata."""
        self._record_billing_enter_metadata(
            "/var/billing_a_enter.touch", "a_billing_enter", current_container_id
        )

    def _confirm_restore_via_container_id(
        self, snapshot_container_id: Optional[str], current_container_id: Optional[str]
    ) -> None:
        """Confirm restore by comparing snapshot container ID with current container ID."""
        if snapshot_container_id:
            if current_container_id:
                if snapshot_container_id != current_container_id:
                    # Confirmed restore - different container IDs
                    logger.info(
                        f"📸 Snapshot restore CONFIRMED: snapshot_container_id={snapshot_container_id[:50]} != "
                        f"current_container_id={current_container_id[:50]}"
                    )
                    # Ensure flag is set on billing service too
                    if hasattr(self, "billing_service") and self.billing_service:
                        self.billing_service._is_snapshot_restore = True
                else:
                    # Same container ID - this is creation, not restore
                    logger.info(
                        f"📸 Same container ID - this is snapshot CREATION, not restore: "
                        f"container_id={current_container_id[:50]}"
                    )
                    # Clear the flag since this is creation
                    if hasattr(self, "_is_snapshot_restore"):
                        delattr(self, "_is_snapshot_restore")
                    if hasattr(self, "billing_service") and self.billing_service:
                        if hasattr(self.billing_service, "_is_snapshot_restore"):
                            delattr(self.billing_service, "_is_snapshot_restore")

    @modal.enter(snap=True)
    def a_billing_enter(
        self,
    ):  # Run as first step for @modal.enter(snap=True) (alphabetical order)
        """Start billing before setup_model runs (for snapshot creation case)."""
        self._get_modal_metadata_for_enter()
        self._record_initial_billing_entry()

        # Check tracking file to see if this is a fresh start
        tracking_file = "/billing_started.touch"
        is_fresh_start = not os.path.exists(tracking_file)

        snapshot_container_id = self._check_snapshot_file_for_restore()

        # If this is a fresh start (no tracking file) and NOT a restore, get uptime NOW
        # This accounts for time between a_billing_enter() starting and Redis connecting
        if is_fresh_start and not getattr(self, "_is_snapshot_restore", False):
            self._get_and_store_early_uptime()

        # Start billing (start_billing will check the flag we just set and use early_uptime if available)
        # The early_uptime and restore flag will be passed in _billing_enter()
        self._billing_enter()

        # Record container ID after billing starts for comparison
        current_container_id = None
        if hasattr(self, "billing_service") and self.billing_service:
            current_container_id = getattr(self.billing_service, "_container_id", None)
            self._update_entry_file_with_container_id(current_container_id)
            self._record_a_billing_enter_metadata(current_container_id)

        # Now do full container ID comparison to confirm restore
        self._confirm_restore_via_container_id(
            snapshot_container_id, current_container_id
        )

    @modal.enter(snap=True)
    def z_billing_enter(self):  # Run as last step for @modal.enter(snap=True)
        """Save snapshot uptime and record z_billing_enter with container ID and UTC time."""
        logger.info(
            f"🟡 [BILLING_ENTER] z_billing_enter(snap=True) called for {self.__class__.__name__}"
        )
        # Get container ID if billing service exists
        current_container_id = None
        if hasattr(self, "billing_service") and self.billing_service:
            current_container_id = getattr(self.billing_service, "_container_id", None)

        self._record_billing_enter_metadata(
            "/var/billing_z_enter.touch", "z_billing_enter", current_container_id
        )

        self.save_snapshot_uptime()
