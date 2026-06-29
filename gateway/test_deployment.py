import os
from dataclasses import dataclass

import pytest
import requests

from models.commons.model.schema import ModelActions
from models.commons.storage.r2 import read_json_from_r2
from models.commons.util.config import (
    r2_bucket_name,
    r2_test_data_dir,
)

# --- Test Configuration ---

# URL of the deployed gateway. Set BIOLM_GATEWAY_URL to the deployment's URL
# (Modal prints it on deploy, e.g. https://<workspace>--biolm-gateway-web.modal.run).
GATEWAY_URL = os.getenv("BIOLM_GATEWAY_URL", "")

# Skip all tests in this file if the gateway URL isn't set.
if not GATEWAY_URL:
    pytest.skip(
        "BIOLM_GATEWAY_URL environment variable not set, skipping gateway deployment tests.",
        allow_module_level=True,
    )


@dataclass
class GatewayTestCase:
    """Defines a single end-to-end test case for the gateway."""

    model_slug: str  # The public-facing slug in the URL, e.g., "dna-chisel"
    base_model_slug: str  # The slug for finding test data, e.g., "dna-chisel"
    model_action: str
    input_filename: str

    def __str__(self):
        """Used for generating descriptive test IDs in pytest output."""
        return f"{self.model_slug}/{self.model_action}"


gateway_test_cases = [
    GatewayTestCase(
        model_slug="dna-chisel",
        base_model_slug="dna-chisel",
        model_action=ModelActions.ENCODE,
        input_filename="encode_input_default.json",
    ),
    # Add more tests here
]


def execute_gateway_test_case(case: GatewayTestCase):
    """
    A reusable test runner that executes a single test case against the live gateway.
    """
    print(f"\n🧪 Running Gateway Test: {case}")

    # 1. Load test input data from R2
    r2_path = f"{r2_test_data_dir}/models/{case.base_model_slug}/{case.input_filename}"
    try:
        payload = read_json_from_r2(r2_bucket_name, r2_path)
        print(f"  - Loaded input from R2: {r2_path}")
    except Exception as e:
        pytest.fail(
            f"🔥 Failed to load input data from R2 path '{r2_path}'. Error: {e}"
        )

    # 2. Construct the full API URL for the endpoint
    url = f"{GATEWAY_URL}/api/v3/{case.model_slug}/{case.model_action}"
    print(f"  - Posting to URL: {url}")

    # 3. Make the HTTP request to the live gateway endpoint
    try:
        response = requests.post(url, json=payload, timeout=300)  # 5-minute timeout
        response.raise_for_status()  # Raise an HTTPError for 4xx or 5xx responses
        actual_output = response.json()
        print(f"  - Request successful, got {response.status_code} OK.")
    except requests.exceptions.RequestException as e:
        response_text = e.response.text if e.response else "N/A"
        pytest.fail(
            f"🔥 HTTP request to gateway failed. URL: {url}, Error: {e}\nResponse: {response_text}"
        )

    # 4. Perform basic validation on the output structure
    try:
        assert "results" in actual_output, "Response is missing 'results' key."
        assert isinstance(
            actual_output["results"], list
        ), "'results' key is not a list."
        assert len(actual_output["results"]) > 0, "'results' list is empty."
        print(f"✅ PASS: Response for {case} is well-formed.")

    except AssertionError as e:
        pytest.fail(
            f"❌ Validation Failed for {case}: {e}\n  - Actual Output: {actual_output}"
        )


@pytest.mark.deployment
@pytest.mark.parametrize("case", gateway_test_cases, ids=str)
def test_gateway_endpoints(case: GatewayTestCase):
    execute_gateway_test_case(case)


# To run this test:
#   pytest gateway/test_deployment.py -m deployment -n auto --no-cov -v -s
