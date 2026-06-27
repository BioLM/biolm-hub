"""
Pure unit tests for DeepViscosity schema validation — no Modal, no GPU, no R2.

Run:
    pytest models/deepviscosity/test_unit.py -v
"""

import pytest
from pydantic import ValidationError

from models.deepviscosity.schema import (
    DeepViscosityParams,
    DeepViscosityPredictRequest,
    DeepViscosityPredictRequestItem,
)


class TestDeepViscositySchemaValidation:
    """Unit tests for DeepViscosity schema validation edge cases."""

    # Valid minimum-length sequence (50 amino acids)
    MIN_VALID_SEQ = "A" * DeepViscosityParams.min_sequence_len

    # Valid maximum-length sequence (200 amino acids)
    MAX_VALID_SEQ = "A" * DeepViscosityParams.max_sequence_len

    def test_valid_min_length_sequences(self) -> None:
        """Test that minimum-length sequences pass validation."""
        request = DeepViscosityPredictRequest(
            items=[
                DeepViscosityPredictRequestItem(
                    heavy_chain=self.MIN_VALID_SEQ,
                    light_chain=self.MIN_VALID_SEQ,
                )
            ]
        )
        assert len(request.items) == 1
        assert len(request.items[0].heavy_chain) == DeepViscosityParams.min_sequence_len

    def test_valid_max_length_sequences(self) -> None:
        """Test that maximum-length sequences pass validation."""
        request = DeepViscosityPredictRequest(
            items=[
                DeepViscosityPredictRequestItem(
                    heavy_chain=self.MAX_VALID_SEQ,
                    light_chain=self.MAX_VALID_SEQ,
                )
            ]
        )
        assert len(request.items) == 1
        assert len(request.items[0].heavy_chain) == DeepViscosityParams.max_sequence_len

    def test_sequence_too_short_rejected(self) -> None:
        """Test that sequences below minimum length are rejected."""
        too_short = "A" * (DeepViscosityParams.min_sequence_len - 1)
        with pytest.raises(ValidationError) as exc_info:
            DeepViscosityPredictRequest(
                items=[
                    DeepViscosityPredictRequestItem(
                        heavy_chain=too_short,
                        light_chain=self.MIN_VALID_SEQ,
                    )
                ]
            )
        assert "should have at least" in str(exc_info.value)

    def test_sequence_too_long_rejected(self) -> None:
        """Test that sequences above maximum length are rejected."""
        too_long = "A" * (DeepViscosityParams.max_sequence_len + 1)
        with pytest.raises(ValidationError) as exc_info:
            DeepViscosityPredictRequest(
                items=[
                    DeepViscosityPredictRequestItem(
                        heavy_chain=too_long,
                        light_chain=self.MIN_VALID_SEQ,
                    )
                ]
            )
        assert "should have at most" in str(exc_info.value)

    def test_invalid_amino_acid_rejected(self) -> None:
        """Test that sequences with invalid amino acids are rejected."""
        invalid_seq = "ACDEFGHIKLMNPQRSTVWYX"  # 'X' is ambiguous, not allowed
        with pytest.raises(ValidationError):
            DeepViscosityPredictRequest(
                items=[
                    DeepViscosityPredictRequestItem(
                        heavy_chain=invalid_seq + "A" * 30,  # Make it long enough
                        light_chain=self.MIN_VALID_SEQ,
                    )
                ]
            )

    def test_empty_items_rejected(self) -> None:
        """Test that empty items list is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DeepViscosityPredictRequest(items=[])
        assert "at least 1" in str(exc_info.value).lower()

    def test_batch_size_limit_enforced(self) -> None:
        """Test that batch size limit is enforced."""
        max_batch = DeepViscosityParams.batch_size
        items = [
            DeepViscosityPredictRequestItem(
                heavy_chain=self.MIN_VALID_SEQ,
                light_chain=self.MIN_VALID_SEQ,
            )
            for _ in range(max_batch + 1)
        ]
        with pytest.raises(ValidationError) as exc_info:
            DeepViscosityPredictRequest(items=items)
        assert "at most" in str(exc_info.value).lower()
