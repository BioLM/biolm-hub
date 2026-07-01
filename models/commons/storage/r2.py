import functools
import json
import os
from typing import Any

from models.commons.core.logging import get_logger

logger = get_logger(__name__)


def r2_credentials_present() -> bool:
    """Return True if S3 credentials for R2 are configured in the environment.

    When False, the public OSS bucket can still be READ anonymously over HTTPS via
    its r2.dev public URL (see models/commons/storage/r2_http.py) — this is the
    credential-less happy path. Writes/self-population always require credentials.
    """
    return bool(os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"))


def get_r2_transfer_config() -> Any:
    """
    Returns a TransferConfig optimized for large file *downloads*.

    Tuned for downloading multi-GB model weight files. The 1GB multipart
    threshold is intentionally high because R2 download performance is best
    with single-stream GET for files under 1GB; multipart only helps above that.
    (Uploads use a lower 100MB threshold — see get_r2_upload_transfer_config.)

    Returns:
        boto3.s3.transfer.TransferConfig: Download-optimized transfer configuration
    """
    from boto3.s3.transfer import TransferConfig

    return TransferConfig(
        multipart_threshold=1024 * 1024 * 1024,  # 1GB - use multipart for files > 1GB
        max_concurrency=5,  # Reasonable concurrency for model downloads
        num_download_attempts=5,  # Retry downloads up to 5 times
        use_threads=True,  # Enable threaded transfers
        max_io_queue=50,  # Buffer for read operations
        io_chunksize=1024 * 1024,  # 1MB chunks for reading
    )


def get_r2_upload_transfer_config() -> Any:
    """
    Returns a TransferConfig optimized for large file *uploads*.

    Uses a 100MB multipart threshold (lower than downloads) because R2 upload
    reliability improves with multipart for files over ~100MB — individual parts
    can be retried independently and uploaded in parallel.

    Returns:
        boto3.s3.transfer.TransferConfig: Upload-optimized transfer configuration
    """
    from boto3.s3.transfer import TransferConfig

    return TransferConfig(
        multipart_threshold=100 * 1024 * 1024,  # 100MB: trigger multipart above this
        multipart_chunksize=50 * 1024 * 1024,  # 50MB chunks for parallel upload
        max_concurrency=5,
        use_threads=True,
    )


@functools.lru_cache
def get_r2_client() -> Any:
    """
    Returns a cached R2 client object for interacting with the R2 bucket.

    Uses credentials and region from environment variables:
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, R2_ENDPOINT.
    This is decorated with @functools.lru_cache to ensure only one client is created.

    Configured with extended timeouts for large file downloads (e.g., progen2 medium).

    Returns:
        botocore.client.S3: The R2 client for S3-compatible interactions.
    """
    import boto3
    from botocore.client import Config

    # Configure timeouts for large file downloads
    # - connect_timeout: Time to establish connection
    # - read_timeout: Time to read data from connection
    # - max_attempts: Retry failed operations
    config = Config(
        connect_timeout=30,  # 30 seconds to establish connection
        read_timeout=600,  # 10 minutes to read large files (e.g., pytorch_model.bin)
        retries={
            "max_attempts": 3,  # Retry up to 3 times
            "mode": "adaptive",  # Use adaptive retry mode for better handling
        },
    )

    return boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION"),
        endpoint_url=os.getenv("R2_ENDPOINT"),
        config=config,
    )


def read_json_from_r2(bucket_name: str, file_key: str) -> Any:
    """
    Reads a JSON file from the given R2 bucket and path, returning its parsed contents.

    Args:
        bucket_name (str): The name of the R2 bucket.
        file_key (str): The path/key to the file within the bucket.

    Returns:
        Any: The JSON-parsed content, usually a dictionary or list.

    Raises:
        FileNotFoundError: If the file is not found or cannot be retrieved.
    """
    client = get_r2_client()
    try:
        response = client.get_object(Bucket=bucket_name, Key=file_key)
        content = response["Body"].read().decode("utf-8")
        return json.loads(content)
    except Exception as e:
        raise FileNotFoundError(f"Error reading {file_key} from R2: {str(e)}") from e


def write_data_to_r2(bucket_name: str, file_key: str, data: Any) -> None:
    """
    Serializes data to JSON and writes it to the specified location in the R2 bucket.

    Args:
        bucket_name (str): The name of the R2 bucket.
        file_key (str): The path/key where the data should be stored.
        data (Any): The Python object to serialize and upload.

    Returns:
        None

    Raises:
        RuntimeError: If writing to R2 fails.
    """
    client = get_r2_client()
    try:
        content = json.dumps(data, indent=4)
        client.put_object(
            Bucket=bucket_name, Key=file_key, Body=content.encode("utf-8")
        )
        logger.info("Uploaded JSON to r2://%s/%s", bucket_name, file_key)
    except Exception as e:
        raise RuntimeError(f"Error writing {file_key} to R2: {str(e)}") from e
