import asyncio
import json
import logging
import os
import re
import threading
from collections import deque
from typing import Any, Optional, Union

# Try to import async Redis first, fall back to sync
try:
    import redis.asyncio as redis_async

    ASYNC_REDIS_AVAILABLE = True
except ImportError:
    ASYNC_REDIS_AVAILABLE = False

# Import redis - handle case where it's not installed yet (during image build)
try:
    import redis
except ImportError:
    redis = None  # type: ignore


class RedisPubSubService:
    """Light-weight Redis based Pub/Sub publisher.

    A very small wrapper around the Redis client that *only* supports
    publishing messages to a given ``channel_id``. The same Redis URL that
    is already used for billing (``REDIS_URL`` env var) is reused so no
    additional secrets are required.

    Uses async Redis client when available, falls back to sync client.
    """

    def __init__(self, channel_id: str, connection_pool=None):
        if redis is None:
            raise ImportError(
                "redis package is required for RedisPubSubService. "
                "Install it with: pip install redis>=5.1.1,<=6.2.0"
            )
        self.channel_id = channel_id
        self._redis_client: Optional[Union[redis.Redis, redis_async.Redis]] = None
        self._lock = threading.RLock()
        self._shared_pool = connection_pool  # Optional shared connection pool

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------
    def _get_client(self) -> Optional[Union[redis.Redis, redis_async.Redis]]:
        """(Re-)initialise and cache the Redis client lazily and thread-safely."""
        with self._lock:
            if self._redis_client is not None:
                return self._redis_client

            redis_url = os.environ.get("REDIS_URL")
            if not redis_url:
                print("❌ REDIS_URL env var not set – PubSub disabled")
                return None
            try:
                # Use shared connection pool if available, otherwise create new connection
                if self._shared_pool is not None:
                    self._redis_client = redis.Redis(connection_pool=self._shared_pool)
                    print("✅ PubSub using shared Redis connection pool")
                else:
                    # Always use sync Redis client for initialization to avoid async/sync context issues
                    # The async operations will use asyncio.to_thread for non-blocking behavior
                    self._redis_client = redis.from_url(
                        redis_url,
                        socket_connect_timeout=2,  # Shorter timeout to avoid hanging
                        socket_timeout=2,
                        retry_on_timeout=False,  # Don't retry to avoid hanging
                        health_check_interval=30,
                    )
                    print("✅ PubSub sync Redis connection established")

                # Test connection early so we can fallback to noop behaviour
                self._redis_client.ping()

            except Exception as e:  # pragma: no cover – extremely defensive
                print(f"⚠️  PubSub Redis connection failed: {e}")
                self._redis_client = None
            return self._redis_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def publish(self, data: Union[str, bytes, dict, list, Any]) -> bool:
        """Publish *data* to the configured channel.

        Non-string payloads are JSON-encoded automatically. Messages are
        compressed with zstd before transmission. The method is a
        *best-effort* fire-and-forget – it will never raise, but returns a
        ``bool`` indicating success so callers can decide whether they need
        to fallback to an alternative transport.
        """
        client = self._get_client()
        if client is None:
            return False
        try:
            # Convert to JSON if not already string/bytes
            if not isinstance(data, str | bytes):
                data = json.dumps(data, default=str, separators=(",", ":"))

            # Compress with zstd (if available) before publishing
            if isinstance(data, str):
                try:
                    import zstandard as zstd

                    json_bytes = data.encode("utf-8")
                    cctx = zstd.ZstdCompressor(level=16)
                    data = cctx.compress(json_bytes)
                except ImportError:
                    # If zstd not available, fall back to uncompressed
                    # (Bridge will handle both formats)
                    pass
                except Exception as e:
                    # Compression failed, send uncompressed
                    print(f"⚠️  PubSub compression failed (sending uncompressed): {e}")

            # Always use sync Redis client for this method
            client.publish(self.channel_id, data)
            return True
        except Exception as e:  # pragma: no cover – swallow all
            print(f"⚠️  PubSub publish failed: {e}")
            return False

    def close(self) -> None:
        """Close the underlying Redis connection (if any)."""
        with self._lock:
            if self._redis_client is not None:
                try:
                    self._redis_client.close()
                except Exception:
                    pass
                self._redis_client = None

    # ------------------------------------------------------------------
    # Async API
    # ------------------------------------------------------------------
    async def publish_async(self, data: Union[str, bytes, dict, list, Any]) -> bool:
        """Async wrapper around ``publish`` using ``asyncio.to_thread``.

        This allows non-blocking use of the synchronous Redis client from
        ``async`` code without introducing a hard dependency on an async
        Redis driver. The implementation simply delegates the call to the
        existing synchronous :pymeth:`publish` method in a background
        thread via :pyfunc:`asyncio.to_thread` and therefore preserves all
        existing behaviour including error handling and return semantics.
        """
        # Always use asyncio.to_thread with sync client for consistent behavior
        return await asyncio.to_thread(self.publish, data)

    async def close_async(self) -> None:
        """Async wrapper around :pymeth:`close`."""
        # Always use asyncio.to_thread with sync client for consistent behavior
        await asyncio.to_thread(self.close)


class _RedisLogHandler(logging.Handler):
    """Sync logging handler that mirrors log records to Redis Pub/Sub using sync Redis."""

    def __init__(
        self, channel_id: str, app_username: Optional[str] = None, connection_pool=None
    ):
        """Create a sync log handler that mirrors records to Redis.

        Parameters
        ----------
        channel_id:
            The Redis channel ID to publish to.
        app_username:
            Optional user identifier to attach to every published log payload.
        connection_pool:
            Optional shared Redis connection pool to use instead of creating a new connection.
        """
        super().__init__()
        self._channel_id = channel_id
        self._app_username = app_username or ""
        self._redis_client = None
        self._redis_available = False  # Track if Redis is actually available

        # Rate limiting to prevent overwhelming Redis under high load

        self._last_emit_time = 0
        self._min_emit_interval = (
            0.05  # Minimum 50ms between log emissions (more lenient)
        )
        self._dropped_count = 0

        # Connection reliability tracking
        self._connection_failures = 0
        self._max_connection_failures = 3
        self._last_failure_time = 0
        self._failure_backoff = 60  # Wait 60s after max failures before retrying

        # Message buffering for connection establishment edge cases
        self._message_buffer = deque(
            maxlen=50
        )  # Buffer up to 50 messages during connection issues
        self._buffer_lock = threading.Lock()  # Thread-safe buffer access
        self._flush_lock = threading.Lock()  # Atomic flush + send operations
        self._shared_pool = connection_pool  # Optional shared connection pool
        self._shutting_down = (
            False  # Shutdown flag to prevent new messages during cleanup
        )

        # Test Redis connection during initialization and keep it alive
        try:
            redis_url = os.environ.get("REDIS_URL")
            if redis_url:
                # Use shared connection pool if available, otherwise create new connection
                if self._shared_pool is not None:
                    self._redis_client = redis.Redis(connection_pool=self._shared_pool)
                    print("✅ RedisLogHandler: Using shared Redis connection pool")
                else:
                    # Create connection with same settings as _get_sync_client for consistency
                    self._redis_client = redis.from_url(
                        redis_url,
                        socket_connect_timeout=3,
                        socket_timeout=3,
                        retry_on_timeout=True,
                        health_check_interval=30,
                        max_connections=20,
                    )
                    print("✅ RedisLogHandler: Redis connection established and ready")

                self._redis_client.ping()
                self._redis_available = True
            else:
                print("❌ RedisLogHandler: REDIS_URL not set")
        except Exception as e:
            print(f"⚠️  RedisLogHandler: Redis connection test failed: {e}")
            self._redis_available = False

        # Use a simple, one-line JSON formatter so the frontend can parse it
        self.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s %(name)s – %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )

    def _sanitize_backend_terms(self, text: Any) -> Any:
        """Replace 'modal' tokens (not inside words) with 'backend', preserving case.

        Matches when surrounded by non-letter chars, so it catches cases like:
        - modal, Modal, MODAL
        - modal_app, _modal_, modal-foo, modal:telemetry
        but not 'modalities'.
        """
        if not isinstance(text, str):
            return text
        pattern = re.compile(r"(?<![A-Za-z])modal(?![A-Za-z])", re.IGNORECASE)

        def repl(m: re.Match) -> str:
            s = m.group(0)
            if s.isupper():
                return "BACKEND"
            if s[0].isupper():
                return "Backend"
            return "backend"

        return pattern.sub(repl, text)

    def _get_sync_client(self):
        """Get or create sync Redis client with improved reliability."""
        import time

        # Check if we're in backoff period after too many failures
        if (
            self._connection_failures >= self._max_connection_failures
            and time.time() - self._last_failure_time < self._failure_backoff
        ):
            return None

        # If we have a client, test if it's still healthy
        if self._redis_client is not None:
            try:
                self._redis_client.ping()
                return self._redis_client
            except Exception:
                # Connection is dead, close and recreate
                try:
                    self._redis_client.close()
                except Exception:
                    pass
                self._redis_client = None

        # Create new connection
        redis_url = os.environ.get("REDIS_URL")
        if redis_url:
            try:
                # Use shared connection pool if available, otherwise create new connection
                if self._shared_pool is not None:
                    self._redis_client = redis.Redis(connection_pool=self._shared_pool)
                else:
                    self._redis_client = redis.from_url(
                        redis_url,
                        socket_connect_timeout=3,  # Shorter timeout for faster failure detection
                        socket_timeout=3,
                        retry_on_timeout=True,
                        health_check_interval=30,
                        max_connections=20,  # Larger connection pool for high concurrency
                    )

                # Test connection to ensure it works
                self._redis_client.ping()
                # Reset failure count on successful connection
                self._connection_failures = 0
                return self._redis_client
            except Exception as e:
                print(f"⚠️  RedisLogHandler failed to connect to Redis: {e}")
                self._connection_failures += 1
                self._last_failure_time = time.time()
                self._redis_client = None
        return None

    def emit(self, record: logging.LogRecord) -> None:  # noqa: C901, D401
        # Check if we're shutting down - if so, don't emit new messages
        if self._shutting_down:
            return

        # Only try to publish if Redis is available
        if not self._redis_available:
            return

        # Check RUNTIME_PUBSUB_LEVEL for production mode filtering
        import os as _os

        pubsub_level = _os.getenv("RUNTIME_PUBSUB_LEVEL", "development").lower()

        if pubsub_level == "production":
            # In production mode, only publish WARNING and ERROR level logs
            # This filters out all INFO and DEBUG logs that scale with N
            if record.levelno < logging.WARNING:  # WARNING = 30, INFO = 20, DEBUG = 10
                return  # Suppress INFO and DEBUG logs in production

        # Rate limiting: Skip if too soon since last emit
        import time

        current_time = time.time()
        if current_time - self._last_emit_time < self._min_emit_interval:
            self._dropped_count += 1
            return

        try:
            msg = self.format(record)

            # If we dropped messages, include that info
            if self._dropped_count > 0:
                msg += f" [+{self._dropped_count} dropped]"
                self._dropped_count = 0

            # Sanitize backend-identifying terms before sending to PubSub
            msg = self._sanitize_backend_terms(msg)

            payload = {
                "type": "log",
                "payload": msg,
                "app_username": self._app_username,
            }

            # ATOMIC OPERATION: Flush buffer + send new message
            # This prevents race conditions between multiple threads
            with self._flush_lock:
                client = self._get_sync_client()
                if client is not None:
                    # First, flush any buffered messages
                    self._flush_message_buffer(client)

                    # Check if buffer flush failed (messages still in buffer)
                    with self._buffer_lock:
                        if self._message_buffer:
                            # Buffer flush failed - add new message to buffer and return
                            self._message_buffer.append(payload)
                            return

                    # Buffer is empty - safe to send new message immediately
                    try:
                        client.publish(
                            self._channel_id, json.dumps(payload, default=str)
                        )
                        self._last_emit_time = current_time
                    except Exception as pub_error:
                        # Mark connection as failed and try once more with new connection
                        print(f"⚠️  RedisLogHandler publish failed: {pub_error}")
                        self._redis_client = None  # Force reconnection on next attempt

                        # Try once more with new connection
                        try:
                            retry_client = self._get_sync_client()
                            if retry_client is not None:
                                retry_client.publish(
                                    self._channel_id, json.dumps(payload, default=str)
                                )
                                self._last_emit_time = current_time
                            else:
                                # Still no connection - buffer this message
                                self._buffer_message(payload)
                        except Exception as retry_error:
                            print(
                                f"⚠️  RedisLogHandler retry publish failed: {retry_error}"
                            )
                            # Buffer the message for later
                            self._buffer_message(payload)
                else:
                    # No client available - buffer the message if Redis should be available
                    if self._redis_available:
                        self._buffer_message(payload)

                    # Connection issues reporting
                    if self._connection_failures < self._max_connection_failures:
                        print(
                            f"⚠️  RedisLogHandler: No Redis connection available ({self._connection_failures}/{self._max_connection_failures} failures)"
                        )
                    elif self._connection_failures >= self._max_connection_failures:
                        # Only print this occasionally to avoid spam
                        import time

                        if (
                            time.time() - self._last_failure_time > 30
                        ):  # Every 30 seconds
                            print(
                                f"🚨 RedisLogHandler: In backoff mode after {self._connection_failures} failures - logs being dropped"
                            )
                            self._last_failure_time = time.time()

        except Exception as e:  # pragma: no cover – never break the app
            print(f"⚠️  RedisLogHandler failed to emit: {e}")

    def _buffer_message(self, payload: dict) -> None:
        """Buffer a message for later delivery when connection is restored."""
        with self._buffer_lock:
            self._message_buffer.append(payload)
            # If buffer is full, the deque will automatically drop the oldest message
            if (
                len(self._message_buffer) >= 50
            ):  # maxlen should handle this, but be explicit
                print(
                    "⚠️  RedisLogHandler: Message buffer full, oldest messages may be dropped"
                )

    def _flush_message_buffer(self, client) -> None:
        """Flush any buffered messages to Redis."""
        with self._buffer_lock:
            if not self._message_buffer:
                return

            buffer_size = len(self._message_buffer)
            flushed_count = 0

            # Try to publish all buffered messages
            while self._message_buffer:
                try:
                    buffered_payload = self._message_buffer.popleft()
                    client.publish(
                        self._channel_id, json.dumps(buffered_payload, default=str)
                    )
                    flushed_count += 1
                except Exception as e:
                    # If we can't publish, put the message back and stop trying
                    self._message_buffer.appendleft(buffered_payload)
                    print(f"⚠️  RedisLogHandler: Failed to flush buffered message: {e}")
                    break

            if flushed_count > 0:
                print(
                    f"✅ RedisLogHandler: Flushed {flushed_count}/{buffer_size} buffered messages"
                )

    def close(self):
        """Close the sync Redis client with aggressive cleanup."""
        # Set shutdown flag to prevent new messages during cleanup
        self._shutting_down = True

        # Clear message buffer immediately to prevent any further processing
        with self._buffer_lock:
            self._message_buffer.clear()

        # Close Redis client aggressively
        if self._redis_client:
            try:
                self._redis_client.close()
            except Exception as e:
                # Don't let close failures block shutdown
                print(f"⚠️ RedisLogHandler close error (non-blocking): {e}")
            finally:
                # Always set to None regardless of close() success
                self._redis_client = None

        # Mark Redis as unavailable
        self._redis_available = False


class PubSubMixin:  # pylint: disable=too-few-public-methods
    """Mixin that adds Redis-based Pub/Sub capabilities to Modal classes.

    Usage::

        class MyModalClass(PubSubMixin):
            @modal.enter()
            def setup(self):
                self.pubsub_enter(channel_id)

            @modal.exit()
            def cleanup(self):
                self.pubsub_exit()
    """

    # *Instance* attributes added at runtime. "type: ignore" silences mypy.
    pubsub_service: RedisPubSubService  # type: ignore[attr-defined]
    _pubsub_handler: logging.Handler  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Lifecycle helpers – must be called by the inheriting class
    # ------------------------------------------------------------------
    def pubsub_enter(self, channel_id: str) -> None:
        """Initialise Pub/Sub publishing for *channel_id*."""
        try:
            if not channel_id:
                print("ℹ️  PubSub channel_id not provided – skipping PubSub setup")
                return
            self.pubsub_service = RedisPubSubService(channel_id)
            # Forward the app_username attribute if present on the class
            app_username = getattr(self, "app_username", "")

            # Use async logging handler for better performance
            self._pubsub_handler = _RedisLogHandler(channel_id, app_username)

            # Attach to the class-level logger if available, else root logger
            target_logger = getattr(self, "logger", logging.getLogger())
            target_logger.addHandler(self._pubsub_handler)
            print(f"✅ PubSub initialised for channel '{channel_id}'")
        except Exception as e:  # pragma: no cover – defensive
            print(f"⚠️  PubSub initialisation failed: {e}")

    def pubsub_exit(self) -> None:
        """Tear down Pub/Sub resources and detach logging handler."""
        try:
            if hasattr(self, "_pubsub_handler") and self._pubsub_handler:
                target_logger = getattr(self, "logger", logging.getLogger())
                try:
                    target_logger.removeHandler(self._pubsub_handler)
                except Exception:
                    pass
                try:
                    self._pubsub_handler.close()
                except Exception:
                    pass
                self._pubsub_handler = None  # type: ignore[assignment]
            if hasattr(self, "pubsub_service") and self.pubsub_service:
                self.pubsub_service.close()
                self.pubsub_service = None  # type: ignore[assignment]
            print("✅ PubSub shut down")
        except Exception as e:  # pragma: no cover
            print(f"⚠️  PubSub shutdown encountered an error: {e}")
