import pytest
from pydantic import ValidationError

from models.esm2.schema import (
    ESM2EncodeRequestItem,
    ESM2PredictRequestItem,
)


@pytest.mark.integration
def test_esm2_encode_valid_sequence():
    ok = ESM2EncodeRequestItem(sequence="ACD-EFG")
    assert ok.sequence == "ACD-EFG"


@pytest.mark.integration
def test_esm2_encode_type_mismatch():
    with pytest.raises((ValidationError, AttributeError)):
        ESM2EncodeRequestItem(sequence=123)  # type: ignore[arg-type]


@pytest.mark.integration
def test_esm2_predict_mask_token_present():
    ok = ESM2PredictRequestItem(sequence="ACD<mask>EFG")
    assert "<mask>" in ok.sequence


@pytest.mark.integration
def test_esm2_predict_mask_token_missing():
    with pytest.raises(ValidationError):
        ESM2PredictRequestItem(sequence="ACDEFG")


@pytest.mark.integration
def test_esm2_predict_wrong_type():
    with pytest.raises((ValidationError, AttributeError)):
        ESM2PredictRequestItem(sequence=456)  # type: ignore[arg-type]
