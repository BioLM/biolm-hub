"""Unit tests for _coerce_to_json_native in models/commons/data/serializer.py."""

import datetime
import decimal
import pathlib
import uuid

import pytest

from models.commons.data.serializer import _coerce_to_json_native, serialize_model

# ---------------------------------------------------------------------------
# datetime / date
# ---------------------------------------------------------------------------


def test_datetime_isoformat() -> None:
    dt = datetime.datetime(2026, 4, 15, 12, 34, 56, 789012)
    result = _coerce_to_json_native(dt)
    assert result == "2026-04-15T12:34:56.789012"
    assert isinstance(result, str)


def test_date_isoformat() -> None:
    d = datetime.date(2026, 4, 15)
    result = _coerce_to_json_native(d)
    assert result == "2026-04-15"
    assert isinstance(result, str)


def test_datetime_with_timezone() -> None:
    dt = datetime.datetime(2026, 4, 15, 12, 0, 0, tzinfo=datetime.UTC)
    result = _coerce_to_json_native(dt)
    assert result == "2026-04-15T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Decimal
# ---------------------------------------------------------------------------


def test_decimal_becomes_float() -> None:
    result = _coerce_to_json_native(decimal.Decimal("3.14"))
    assert result == pytest.approx(3.14)
    assert isinstance(result, float)


def test_decimal_zero() -> None:
    result = _coerce_to_json_native(decimal.Decimal("0"))
    assert result == 0.0
    assert isinstance(result, float)


# ---------------------------------------------------------------------------
# UUID
# ---------------------------------------------------------------------------


def test_uuid_becomes_str() -> None:
    uid = uuid.UUID("12345678-1234-5678-1234-567812345678")
    result = _coerce_to_json_native(uid)
    assert result == "12345678-1234-5678-1234-567812345678"
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# pathlib.Path / PurePosixPath
# ---------------------------------------------------------------------------


def test_path_becomes_str() -> None:
    p = pathlib.Path("/tmp/model.joblib")
    result = _coerce_to_json_native(p)
    assert result == "/tmp/model.joblib"
    assert isinstance(result, str)


def test_pure_posix_path_becomes_str() -> None:
    p = pathlib.PurePosixPath("/data/output")
    result = _coerce_to_json_native(p)
    assert result == "/data/output"
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# pandas NA / NaT / Timestamp (skip if pandas not installed)
# ---------------------------------------------------------------------------

try:
    import pandas as pd  # noqa: F401

    _PANDAS_AVAILABLE = True
except ImportError:
    _PANDAS_AVAILABLE = False

pandas_only = pytest.mark.skipif(not _PANDAS_AVAILABLE, reason="pandas not installed")


@pandas_only
def test_pd_na_becomes_none() -> None:
    import pandas as pd

    result = _coerce_to_json_native(pd.NA)
    assert result is None


@pandas_only
def test_pd_nat_becomes_none() -> None:
    import pandas as pd

    result = _coerce_to_json_native(pd.NaT)
    assert result is None


@pandas_only
def test_pd_timestamp_isoformat() -> None:
    import pandas as pd

    ts = pd.Timestamp("2026-04-15T12:00:00")
    result = _coerce_to_json_native(ts)
    assert "2026-04-15" in result
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# numpy datetime64 (skip if numpy not installed)
# ---------------------------------------------------------------------------

try:
    import numpy as np  # noqa: F401

    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False

numpy_only = pytest.mark.skipif(not _NUMPY_AVAILABLE, reason="numpy not installed")


@numpy_only
def test_numpy_datetime64_isoformat() -> None:
    import numpy as np

    dt64 = np.datetime64("2026-04-15T12:00:00")
    result = _coerce_to_json_native(dt64)
    assert isinstance(result, str)
    assert "2026-04-15" in result


# ---------------------------------------------------------------------------
# pd.NA in a nested serialize_model call (regression: was returning "<NA>")
# ---------------------------------------------------------------------------


@pandas_only
def test_pd_na_in_dict_via_serialize_model() -> None:
    """pd.NA inside a dict must become None, not the truthy string '<NA>'."""
    import pandas as pd

    data = {"metric": pd.NA, "value": 1.0}
    result = serialize_model(data)
    assert result["metric"] is None
    assert result["value"] == 1.0


# ---------------------------------------------------------------------------
# Fallback warning for truly unknown types
# ---------------------------------------------------------------------------


def test_fallback_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    class _WeirdType:
        def __str__(self) -> str:
            return "weird"

    obj = _WeirdType()
    import logging

    with caplog.at_level(logging.WARNING, logger="models.commons.data.serializer"):
        result = _coerce_to_json_native(obj)
    assert result == "weird"
    assert any("serializer.fallback" in r.message for r in caplog.records)
