from models.commons.model.base import ModelParams
from models.commons.model.pydantic import RequestModel, ResponseModel

### Dummy Params


class DummyParams(ModelParams):
    params_version = "v1"
    display_name = "Dummy"
    base_model_slug = "dummy"
    log_identifier = "Dummy"


### Dummy Request


class DummyModelInput(RequestModel):
    """
    Payload for the model
    => Example of schema shared between the Ray endpoint and the static app endpoint
    """

    dummy_model_input_field: str


class DummySvcRequest(RequestModel):
    """
    Request to the static service's main endpoint
    """

    items: list[DummyModelInput]


### Dummy Response


class DummySvcResponseResult(ResponseModel):
    """
    Response from the static service's main endpoint
    """

    dummy_svc_resp_field: str
    data_file_content: str


class DummySvcResponse(ResponseModel):
    """
    Response from the static service's main endpoint
    """

    results: list[DummySvcResponseResult]
