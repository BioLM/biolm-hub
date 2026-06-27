import io
import os
from typing import Any, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .utils import (  # re-use bucket default if set elsewhere
    get_r2_client,
)

DEFAULT_BUCKET = os.getenv("R2_BUCKET_NAME", "workflow-runs")


def _dict_to_table(row: dict[str, Any], schema: Optional[pa.Schema] = None) -> pa.Table:
    """Convert a single row dict to a pyarrow Table (single-row)."""
    df = pd.DataFrame([row])
    table = pa.Table.from_pandas(df, schema=schema, preserve_index=False)
    return table


def write_parquet_to_r2(
    key: str, row: dict[str, Any], bucket: Optional[str] = None
) -> None:
    """Write a single-row parquet file to R2."""
    bucket = bucket or DEFAULT_BUCKET
    table = _dict_to_table(row)
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="zstd")
    buf.seek(0)

    get_r2_client().put_object(
        Bucket=bucket,
        Key=key,
        Body=buf.getvalue(),
        ContentType="application/octet-stream",
    )


def write_parquet_local(path: str, row: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    table = _dict_to_table(row)
    pq.write_table(table, path, compression="zstd")
