"""Deploy a biolm-hub gateway.

Run from the repo root:

    python -m gateway.deploy_gateway          # bare
    python -m gateway.deploy_gateway --cache  # cached

(``modal deploy gateway/server.py`` also works; this entrypoint just adds the
``--cache`` switch and clearer logging.)
"""

import argparse

import modal

from models.commons.core.logging import get_logger

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy a biolm-hub gateway.")
    parser.add_argument(
        "--cache",
        action="store_true",
        help="Deploy the cache-enabled gateway instead of the bare one.",
    )
    args = parser.parse_args()

    if args.cache:
        from gateway.server_with_cache import app
    else:
        from gateway.server import app

    logger.info("Deploying %s ...", app.name)
    with modal.enable_output():
        app.deploy()
    logger.info("Deployed %s successfully.", app.name)


if __name__ == "__main__":
    main()
