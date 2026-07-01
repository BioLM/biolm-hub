from typing import Any, Optional, Union

from pydantic import BaseModel

from models.commons.model.pydantic import (
    EnhancedStringEnum,
)
from models.commons.util.config import default_scaledown_window


class ModelActions(EnhancedStringEnum):
    PREDICT = "predict"
    FOLD = "fold"
    ENCODE = "encode"
    GENERATE = "generate"
    LOG_PROB = "log_prob"
    SCORE = "score"


class ModalGPU(EnhancedStringEnum):
    T4 = "t4"
    L4 = "l4"
    A100_40GB = "a100"
    A100_80GB = "a100-80gb"
    H100 = "h100"
    H200 = "h200"
    B200 = "b200"
    A10G = "a10g"
    L40S = "l40s"


class ModalResourceSpec(BaseModel):
    """
    Common resource specification used across all Modal Apps.
    CPI and Memory can either be a single value or a tuple (min, max).
    For GPU, we can store a str or None.
    """

    cpu: Union[float, tuple[float, float], None] = 2.0
    memory: Union[int, tuple[int, int], None] = 4096  # MB
    gpu: Optional[ModalGPU] = None
    gpu_count: Optional[int] = None
    timeout: Optional[int] = 20 * 60  # in seconds, defaults to 20 minutes
    startup_timeout: Optional[int] = (
        None  # separate from execution timeout (Modal 1.1.4+)
    )
    scaledown_window: Optional[int] = default_scaledown_window  # seconds
    max_containers: Optional[int] = None

    def to_modal_options(self) -> dict[str, Any]:
        """
        Return a dictionary that can be unpacked (**dict)
        in the @app.cls(...) or .with_options(...) call.
        """
        opts: dict[str, Any] = {
            "cpu": self.cpu,
            "memory": self.memory,
            "gpu": (self.gpu if not self.gpu_count else f"{self.gpu}:{self.gpu_count}"),
            "timeout": self.timeout,
            "scaledown_window": self.scaledown_window,
            "max_containers": self.max_containers,
        }
        if self.startup_timeout is not None:
            opts["startup_timeout"] = self.startup_timeout
        return opts
