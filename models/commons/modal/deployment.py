import argparse
import subprocess
import time
from typing import Optional

import modal

from models.commons.util.environment import get_environment_name, is_production


def run_or_deploy_modal_app(
    app: modal.App, model_cls: type, description: Optional[str] = None
) -> None:
    """
    A common entry-point for all model apps. Handles:
      - Parsing `--force-deploy`
      - Opening `app.run()` context
      - Checking environment + optionally prompting user to deploy

    Parameters:
      app         : The modal.App() instance defined in the `app.py`
      model_cls   : The main model @app.cls class that is normally instantiated
      description : Optional. A string describing the CLI usage
    """

    parser = argparse.ArgumentParser(
        description=description or "Run and optionally deploy a Modal model app."
    )
    parser.add_argument(
        "--force-deploy",
        action="store_true",
        help="Force deploy even if environment is 'qa' or 'main'",
    )

    args = parser.parse_args()

    current_env = get_environment_name()
    if current_env in ("qa", "main"):
        print(f"Production Modal environment detected: {current_env}")
    else:
        print(f"Local or dev Modal environment: {current_env}")

    with modal.enable_output():

        MAX_ATTEMPTS = 2  # Total of 2 attempts: 1 initial + 1 retry
        for attempt in range(MAX_ATTEMPTS):
            try:
                with app.run():
                    _model = model_cls()  # instantiate so build/setup is invoked
                    print(f"✓ App '{app.name}' running successfully")
                break  # If successful, exit the retry loop

            except modal.exception.RemoteError as e:
                is_image_build_error = "Image build for" in str(e) and "failed" in str(
                    e
                )
                if is_image_build_error and (attempt + 1) < MAX_ATTEMPTS:
                    print(
                        "  - ⚠️ WARNING: Modal image build failed. Retrying in 5 seconds..."
                    )
                    time.sleep(5)
                    # Continue to the next iteration of the loop to retry
                    continue
                else:
                    # If it's a different error or the retry also failed, fail the process.
                    print(
                        f"❌ App '{app.name}' failed to run after {MAX_ATTEMPTS} attempts."
                    )
                    raise e

        should_deploy = True
        if is_production():
            print(f"⚠️  Warning: Deploying to production environment '{current_env}'.")
            if not args.force_deploy:
                confirm = input("Continue deployment? [y/N] ")
                should_deploy = confirm.lower().strip() in ("y", "yes")

        if should_deploy:
            print(f"Deploying app '{app.name}' to environment '{current_env}'")

            # Run make clean before deployment to ensure clean state
            print("🧹 Running 'make clean' to ensure clean deployment state...")
            try:
                subprocess.run(
                    ["make", "clean"], check=True, capture_output=True, text=True
                )
                print("✓ Cleanup completed successfully")
            except subprocess.CalledProcessError as e:
                print(f"⚠️  Warning: 'make clean' failed: {e}")
                print("Continuing with deployment anyway...")

            app.deploy()
            print(f"✅  App '{app.name}' deployed successfully")
