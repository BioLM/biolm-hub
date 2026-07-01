"""Schema-strictness unit tests for ESM1v.

ESM1v's defining input constraint is *exactly one* ``<mask>`` token per
sequence (``SingleOccurrenceOf``), which is stricter than the
``SingleOrMoreOccurrencesOf`` rule used by esm1b/esm2.  These tests assert
the constraint is enforced at validation time, without requiring a live
container or R2 fixtures.
"""

import pytest
from pydantic import ValidationError

from models.esm1v.schema import (
    ESM1vPredictRequest,
    ESM1vPredictRequestItem,
)

# ---------------------------------------------------------------------------
# Single-item helpers
# ---------------------------------------------------------------------------


def _item(seq: str) -> ESM1vPredictRequestItem:
    return ESM1vPredictRequestItem(sequence=seq)


def _request(seqs: list[str]) -> ESM1vPredictRequest:
    return ESM1vPredictRequest(items=[_item(s) for s in seqs])


# ---------------------------------------------------------------------------
# Valid inputs
# ---------------------------------------------------------------------------


def test_exactly_one_mask_is_accepted() -> None:
    item = _item("MKTAY<mask>NNKELSKDVR")
    assert "<mask>" in item.sequence


def test_mask_at_start_is_accepted() -> None:
    item = _item("<mask>KTAYVNNKELSKDVR")
    assert item.sequence.startswith("<mask>")


def test_mask_at_end_is_accepted() -> None:
    item = _item("MKTAYVNNKELSKDVR<mask>")
    assert item.sequence.endswith("<mask>")


def test_batch_of_five_with_one_mask_each() -> None:
    req = _request(
        [
            "<mask>KTAYVNNKELSKDVR",
            "M<mask>TAYVNNKELSKDVR",
            "MK<mask>AYVNNKELSKDVR",
            "MKT<mask>YVNNKELSKDVR",
            "MKTA<mask>VNNKELSKDVR",
        ]
    )
    assert len(req.items) == 5


# ---------------------------------------------------------------------------
# Zero masks rejected
# ---------------------------------------------------------------------------


def test_zero_masks_raises() -> None:
    with pytest.raises(ValidationError):
        _item("MKTAYVNNKELSKDVR")


# ---------------------------------------------------------------------------
# Two or more masks rejected
# ---------------------------------------------------------------------------


def test_two_masks_raises() -> None:
    with pytest.raises(ValidationError):
        _item("<mask>KTAY<mask>NNKELSKDVR")


def test_three_masks_raises() -> None:
    with pytest.raises(ValidationError):
        _item("<mask>KT<mask>AY<mask>NKE")


# ---------------------------------------------------------------------------
# Non-amino-acid characters rejected
# ---------------------------------------------------------------------------


def test_non_aa_character_rejected() -> None:
    with pytest.raises(ValidationError):
        _item("MKTAY<mask>1234")


# ---------------------------------------------------------------------------
# Type mismatch rejected
# ---------------------------------------------------------------------------


def test_integer_sequence_rejected() -> None:
    with pytest.raises((ValidationError, AttributeError)):
        _item(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Batch-size limits enforced
# ---------------------------------------------------------------------------


def test_empty_items_list_rejected() -> None:
    with pytest.raises(ValidationError):
        ESM1vPredictRequest(items=[])


def test_six_items_rejected() -> None:
    with pytest.raises(ValidationError):
        _request(["<mask>KTAYVNNKELSKDVR"] * 6)
