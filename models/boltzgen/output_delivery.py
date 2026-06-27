"""
Long-running output delivery and checkpointing via R2.

NOTE: This module currently lives in models/boltzgen/ because BoltzGen is the
only consumer.  Move to models/commons/storage/output_delivery.py when a second
model adopts this pattern.

Provides helpers for models that produce large output directories and need:
  - Resumable checkpointing: tar the output dir and upload a manifest after each
    pipeline step so an interrupted run can be resumed from where it left off.
  - Optional final delivery: presigned download URLs for the full campaign zip
    (upload_and_get_url / upload_file_and_get_url) if the caller wants that too.

Typical usage (checkpointing only — results returned inline)::

    class MyModel(ModelMixinSnap, OutputDeliveryMixin):
        @modal.method()
        def generate(self, payload):
            job = self.create_output_job("mymodel")
            # ... run pipeline steps, writing output to output_dir ...
            manifest = CheckpointManifest(job_id=job.job_id, ...)
            job.upload_checkpoint(output_dir, manifest)   # resumable
            return MyResponse(results=[...], job_id=job.job_id, ...)

Usage standalone::

    job = OutputJob.create("mymodel")
    job.upload_checkpoint(output_dir, manifest)           # checkpoint
    url = job.upload_and_get_url(output_dir)              # optional zip delivery
"""

import datetime
import io
import json
import os
import tarfile
import tempfile
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from models.commons.core.logging import get_logger

logger = get_logger(__name__)

# Default presigned URL expiry: 24 hours
DEFAULT_URL_EXPIRY_SECONDS = 86400

# R2 key prefix for output deliveries
OUTPUT_PREFIX = "outputs"

# R2 key prefix for checkpoints
CHECKPOINT_PREFIX = "checkpoints"


@dataclass
class CheckpointManifest:
    """Tracks progress of a checkpointed pipeline run."""

    job_id: str
    model_slug: str
    completed_steps: list[str]
    remaining_steps: list[str]
    # The full ordered list of steps that were requested for this job.
    # Stored so that a resume call can restore the original pipeline intent
    # without requiring the caller to re-specify params.steps.
    requested_steps: list[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
        .isoformat()
        .replace("+00:00", "Z")
    )
    updated_at: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
        .isoformat()
        .replace("+00:00", "Z")
    )

    def to_json(self) -> str:
        return json.dumps(
            {
                "job_id": self.job_id,
                "model_slug": self.model_slug,
                "completed_steps": self.completed_steps,
                "remaining_steps": self.remaining_steps,
                "requested_steps": self.requested_steps,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> "CheckpointManifest":
        from dataclasses import fields as dc_fields

        known = {f.name for f in dc_fields(cls)}
        data = {k: v for k, v in json.loads(json_str).items() if k in known}
        return cls(**data)


class OutputJob:
    """Represents a single output delivery job with a unique ID."""

    def __init__(
        self,
        model_slug: str,
        job_id: Optional[str] = None,
        namespace: Optional[str] = None,
        bucket_name: Optional[str] = None,
    ):
        self.model_slug = model_slug
        self.job_id = job_id or str(uuid.uuid4())
        # Optional namespace prefix — use to separate test/prod data in R2.
        # e.g. namespace="test" → "test/boltzgen/outputs/..."
        #      namespace=None   → "boltzgen/outputs/..."  (production default)
        self.namespace = namespace
        # Optional bucket override — if None, falls back to r2_bucket_name from config.
        self._bucket_name = bucket_name

    @property
    def bucket(self) -> str:
        """R2 bucket name for this job.

        Priority: explicit override > PROTOCOLS_R2_BUCKET env var.
        The PROTOCOLS_R2_BUCKET env var is injected by the ``protocols-r2-bkt``
        Modal secret and controls dev vs prod bucket routing.
        """
        if self._bucket_name:
            return self._bucket_name
        env_bucket = os.environ.get("PROTOCOLS_R2_BUCKET")
        if not env_bucket:
            raise RuntimeError(
                "PROTOCOLS_R2_BUCKET env var not set. "
                "Ensure the 'protocols-r2-bkt' Modal secret is attached to the app."
            )
        return env_bucket

    @classmethod
    def create(
        cls,
        model_slug: str,
        namespace: Optional[str] = None,
        bucket_name: Optional[str] = None,
    ) -> "OutputJob":
        return cls(model_slug=model_slug, namespace=namespace, bucket_name=bucket_name)

    @property
    def _r2_base(self) -> str:
        """Root R2 prefix for this job, respecting namespace."""
        if self.namespace:
            return f"{self.namespace}/{self.model_slug}"
        return self.model_slug

    @property
    def r2_key(self) -> str:
        return f"{self._r2_base}/{OUTPUT_PREFIX}/{self.job_id}/output.zip"

    def upload_and_get_url(
        self,
        output_dir: Path,
        expiry_seconds: int = DEFAULT_URL_EXPIRY_SECONDS,
    ) -> Optional[str]:
        """Zip output_dir, upload to R2, return a presigned download URL.

        Args:
            output_dir: Directory containing output files to zip and upload.
            expiry_seconds: How long the presigned URL is valid (default 24h).

        Returns:
            Presigned URL string, or None if upload fails.
        """
        from models.commons.storage.r2 import get_r2_client

        bucket = self.bucket
        zip_path = None
        try:
            # Create zip on disk to avoid large in-memory buffers
            fd, _zip = tempfile.mkstemp(suffix=".zip", prefix=f"{self.job_id}_")
            os.close(fd)
            zip_path = Path(_zip)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in output_dir.rglob("*"):
                    if file_path.is_file():
                        zf.write(file_path, file_path.relative_to(output_dir))

            zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
            logger.info(f"[OutputJob {self.job_id}] Created zip: {zip_size_mb:.1f} MB")

            client = get_r2_client()
            with open(zip_path, "rb") as f:
                client.upload_fileobj(f, bucket, self.r2_key)
            logger.info(
                "[OutputJob %s] Uploaded to r2://%s/%s",
                self.job_id,
                bucket,
                self.r2_key,
            )

            url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": self.r2_key},
                ExpiresIn=expiry_seconds,
            )
            logger.info(
                "[OutputJob %s] Presigned URL generated (expires in %ss)",
                self.job_id,
                expiry_seconds,
            )
            return url
        except Exception as e:
            logger.error(
                "[OutputJob %s] Upload failed: %s", self.job_id, e, exc_info=True
            )
            import traceback

            traceback.print_exc()
            return None
        finally:
            if zip_path and zip_path.exists():
                zip_path.unlink()

    def upload_file_and_get_url(
        self,
        file_path: Path,
        r2_filename: Optional[str] = None,
        expiry_seconds: int = DEFAULT_URL_EXPIRY_SECONDS,
    ) -> Optional[str]:
        """Upload a single file to R2 and return a presigned download URL.

        Args:
            file_path: Path to the file to upload.
            r2_filename: Override filename in R2 (defaults to file_path.name).
            expiry_seconds: How long the presigned URL is valid (default 24h).

        Returns:
            Presigned URL string, or None if upload fails.
        """
        from models.commons.storage.r2 import get_r2_client

        bucket = self.bucket
        r2_key = f"{self._r2_base}/{OUTPUT_PREFIX}/{self.job_id}/{r2_filename or file_path.name}"

        try:
            client = get_r2_client()
            with open(file_path, "rb") as f:
                client.upload_fileobj(f, bucket, r2_key)
            logger.info(
                "[OutputJob %s] Uploaded %s to r2://%s/%s",
                self.job_id,
                file_path.name,
                bucket,
                r2_key,
            )

            url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": r2_key},
                ExpiresIn=expiry_seconds,
            )
            return url
        except Exception as e:
            logger.error(
                "[OutputJob %s] Upload failed: %s", self.job_id, e, exc_info=True
            )
            import traceback

            traceback.print_exc()
            return None

    @property
    def _checkpoint_r2_prefix(self) -> str:
        return f"{self._r2_base}/{CHECKPOINT_PREFIX}/{self.job_id}"

    def upload_checkpoint(self, output_dir: Path, manifest: CheckpointManifest) -> bool:
        """Tar.gz the output directory and upload it to R2 alongside a manifest JSON.

        Args:
            output_dir: Directory to checkpoint (archived as "output/" in the tar).
            manifest: Checkpoint manifest describing completed/remaining steps.

        Returns:
            True on success, False on failure (non-fatal — caller decides whether to raise).
        """
        from models.commons.storage.r2 import get_r2_client

        bucket = self.bucket
        manifest.updated_at = (
            datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
        )
        tar_path = None
        try:
            fd, _tar = tempfile.mkstemp(suffix=".tar.gz", prefix=f"{self.job_id}_ckpt_")
            os.close(fd)
            tar_path = Path(_tar)
            with tarfile.open(tar_path, "w:gz") as tf:
                tf.add(output_dir, arcname="output")

            tar_size_mb = tar_path.stat().st_size / (1024 * 1024)
            logger.info(
                f"[OutputJob {self.job_id}] Checkpoint tar: {tar_size_mb:.1f} MB"
            )

            client = get_r2_client()
            tar_key = f"{self._checkpoint_r2_prefix}/checkpoint.tar.gz"
            manifest_key = f"{self._checkpoint_r2_prefix}/manifest.json"

            with open(tar_path, "rb") as f:
                client.upload_fileobj(f, bucket, tar_key)
            logger.info(
                "[OutputJob %s] Checkpoint uploaded to r2://%s/%s",
                self.job_id,
                bucket,
                tar_key,
            )

            manifest_bytes = manifest.to_json().encode("utf-8")
            client.upload_fileobj(io.BytesIO(manifest_bytes), bucket, manifest_key)
            logger.info(
                "[OutputJob %s] Manifest uploaded (completed=%s)",
                self.job_id,
                manifest.completed_steps,
            )
            return True
        except Exception as e:
            logger.error(
                "[OutputJob %s] Checkpoint upload failed: %s",
                self.job_id,
                e,
                exc_info=True,
            )
            import traceback

            traceback.print_exc()
            return False
        finally:
            if tar_path and tar_path.exists():
                tar_path.unlink()

    def download_checkpoint(self, restore_dir: Path) -> CheckpointManifest:
        """Download and extract a checkpoint from R2 into restore_dir.

        Extracts the tar into restore_dir so that restore_dir/output/ becomes
        the restored output directory.

        Args:
            restore_dir: Parent directory to extract into. After extraction,
                the output directory lives at restore_dir / "output".

        Returns:
            The CheckpointManifest describing what steps have completed.

        Raises:
            Exception if download or extraction fails.
        """
        from models.commons.storage.r2 import get_r2_client

        bucket = self.bucket
        tar_path = None
        try:
            client = get_r2_client()
            tar_key = f"{self._checkpoint_r2_prefix}/checkpoint.tar.gz"
            manifest_key = f"{self._checkpoint_r2_prefix}/manifest.json"

            # Download and parse manifest first (fast — small JSON)
            manifest_obj = client.get_object(Bucket=bucket, Key=manifest_key)
            manifest = CheckpointManifest.from_json(
                manifest_obj["Body"].read().decode("utf-8")
            )
            logger.info(
                "[OutputJob %s] Checkpoint manifest: completed=%s, remaining=%s",
                self.job_id,
                manifest.completed_steps,
                manifest.remaining_steps,
            )

            # Download and extract the tar
            fd, _tar = tempfile.mkstemp(suffix=".tar.gz", prefix=f"{self.job_id}_ckpt_")
            os.close(fd)
            tar_path = Path(_tar)
            with open(tar_path, "wb") as f:
                client.download_fileobj(bucket, tar_key, f)

            tar_size_mb = tar_path.stat().st_size / (1024 * 1024)
            logger.info(
                f"[OutputJob {self.job_id}] Downloaded checkpoint: {tar_size_mb:.1f} MB"
            )

            restore_dir.mkdir(parents=True, exist_ok=True)
            with tarfile.open(tar_path, "r:gz") as tf:
                # filter="data" rejects path traversal, symlinks, and device files
                tf.extractall(restore_dir, filter="data")
            logger.info(
                "[OutputJob %s] Checkpoint extracted to %s",
                self.job_id,
                restore_dir / "output",
            )
            return manifest
        except Exception as e:
            logger.error(
                "[OutputJob %s] Checkpoint download failed: %s",
                self.job_id,
                e,
                exc_info=True,
            )
            import traceback

            traceback.print_exc()
            raise
        finally:
            if tar_path and tar_path.exists():
                tar_path.unlink()


class OutputDeliveryMixin:
    """Mixin for Modal model classes that need R2-based output delivery.

    Provides a convenience method to create OutputJob instances scoped to
    the model's slug.
    """

    def create_output_job(self, model_slug: Optional[str] = None) -> OutputJob:
        """Create a new OutputJob for this model.

        Args:
            model_slug: Override model slug. If None, attempts to derive it
                from the class module's app_name.
        """
        if model_slug is None:
            model_slug = self._get_output_model_slug()
        return OutputJob.create(model_slug)

    def _get_output_model_slug(self) -> str:
        """Derive model slug from the module where this class is defined."""
        import inspect

        try:
            class_module = inspect.getmodule(self.__class__)
            if class_module and hasattr(class_module, "app_name"):
                return class_module.app_name
        except Exception:
            pass
        return "unknown"
