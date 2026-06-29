from pydantic import Field

from models.commons.model.base import ModelParams
from models.commons.model.pydantic import RequestModel, ResponseModel

### Dummy Params


class DummyParams(ModelParams):
    weights_version = "v1"
    display_name = "Dummy"
    base_model_slug = "dummy"
    log_identifier = "Dummy"


### Dummy Request


class DummyModelInput(RequestModel):
    """
    Payload for the model
    => Example of schema shared between the Ray endpoint and the static app endpoint
    """

    dummy_model_input_field: str = Field(
        description="Arbitrary string input processed by the dummy model."
    )


class DummySvcRequest(RequestModel):
    """
    Request to the static service's main endpoint
    """

    items: list[DummyModelInput] = Field(
        description="Batch of inputs to process in a single request."
    )


### Dummy Response


class DummySvcResponseResult(ResponseModel):
    """
    Response from the static service's main endpoint
    """

    dummy_svc_resp_field: str = Field(
        description="Processed version of the input field, with a dummy-model suffix appended."
    )
    data_file_content: str = Field(
        description="Content loaded from the container's test data file at inference time."
    )


class DummySvcResponse(ResponseModel):
    """
    Response from the static service's main endpoint
    """

    results: list[DummySvcResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )
