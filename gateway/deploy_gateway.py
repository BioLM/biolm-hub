"""Deploy the bare BioLM Models gateway.

Equivalent to ``modal deploy gateway/gateway.py``. The cached variant is
deployed separately via ``modal deploy gateway/gateway_with_cache.py``.
"""

import asyncio

from gateway.gateway import app
from models.commons.core.logging import get_logger

logger = get_logger(__name__)


async def main():
    logger.info("Deploying biolm-gateway...")
    await app.deploy.aio(name="biolm-gateway")
    logger.info("Gateway deployed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
