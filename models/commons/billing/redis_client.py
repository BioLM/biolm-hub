import logging
import os
import socket
import sys
from typing import Optional

import redis

"""
Redis connection utilities for Modal billing service.

This module provides Redis client initialization and connection management
with proper error handling and connection pooling.
"""

BILLING_PREFIX = "[💰 BILLING]"

logger = logging.getLogger("biolm.billing")
if not logger.handlers:  # avoid duplicate handlers in tests
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(
        logging.Formatter(
            f"{BILLING_PREFIX} [%(asctime)s] [%(levelname)s] %(message)s",
            "%H:%M:%S",
        )
    )
    logger.addHandler(h)
    logger.setLevel(logging.INFO)  # use DEBUG only when troubleshooting billing
    logger.propagate = False  # keep messages from bubbling to root logger


def initialize_redis_client() -> tuple[Optional[redis.Redis], bool]:
    """
    Initialize Redis connection using Modal secrets.

    Returns:
        tuple: (redis_client, success) - Redis client instance and success flag
    """
    try:
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            logger.error("REDIS_URL environment variable not found")
            return None, False

        # Create new client with single connection (no pool needed for sequential billing operations)
        # TCP keepalive: probe every 3 seconds as safety net (connection actively used every 0.45s)
        # With up to 1k containers, this reduces keepalive overhead while still detecting dead connections
        connection_kwargs = {
            "socket_connect_timeout": 5,
            "socket_timeout": 5,
            "socket_keepalive": True,
            "max_connections": 1,  # Single connection per BillingService (sequential operations)
            "retry_on_timeout": True,
            "health_check_interval": 20,
        }

        # Add keepalive options if socket constants are available (platform-specific)
        # Use socket constants instead of hardcoded integers to avoid Error 22
        # Note: Even if constants exist, they may not be valid for the platform
        # redis-py will handle invalid options gracefully, but we check availability first
        keepalive_options = {}
        if hasattr(socket, "TCP_KEEPIDLE"):
            keepalive_options[socket.TCP_KEEPIDLE] = (
                4  # Start keepalive after 4 seconds idle
            )
        if hasattr(socket, "TCP_KEEPINTVL"):
            keepalive_options[socket.TCP_KEEPINTVL] = (
                3  # Send keepalive every 3 seconds
            )
        if hasattr(socket, "TCP_KEEPCNT"):
            keepalive_options[socket.TCP_KEEPCNT] = (
                3  # Send 3 probes before considering dead (~9s total)
            )

        # Only add keepalive options if we found any valid constants
        # If none are available, just use basic socket_keepalive=True
        if keepalive_options:
            connection_kwargs["socket_keepalive_options"] = keepalive_options
        else:
            logger.debug(
                "Socket keepalive constants not available on this platform, using basic keepalive"
            )

        redis_client = redis.from_url(redis_url, **connection_kwargs)

        # Test connection
        redis_client.ping()
        logger.info("Redis connection established")
        return redis_client, True

    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        return None, False


def close_redis_client(redis_client: redis.Redis) -> None:
    """
    Safely close a Redis client connection.

    Args:
        redis_client: Redis client to close
    """
    if redis_client:
        try:
            redis_client.close()
        except Exception:
            pass  # Ignore errors during cleanup
