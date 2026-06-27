import asyncio

from gateway.app import app


async def main():
    """
    Deploys the BioLM Gateway Modal application, which includes both the main
    FastAPI web endpoint and the persistent background worker for state management.
    """

    print(
        "⚠️  REMINDER: If you've changed any code in the `models/*` directory,"
        "    make sure you have redeployed those model apps first before proceeding.\n"
    )

    print("🚀 Deploying biolm-gateway...")
    print("   - Deploying main web endpoint...")
    print("   - Deploying persistent state updater worker...")

    # The `name` parameter is what the deployment will be called in Modal dashboard.
    # This single command deploys all functions attached to the `app` object.
    await app.deploy.aio(name="biolm-gateway")
    print("\n✅ Gateway and worker deployed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
