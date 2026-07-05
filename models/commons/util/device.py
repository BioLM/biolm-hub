from typing import TYPE_CHECKING

from models.commons.core.logging import get_logger

if TYPE_CHECKING:
    import torch


logger = get_logger(__name__)


def get_torch_device() -> "torch.device":
    """
    Determines an appropriate torch.device for computation.

    Checks if CUDA is available (then 'cuda'), otherwise defaults to 'cpu'.

    Returns:
        torch.device: The Torch device object (e.g., "cuda" or "cpu").
    """
    import torch

    if torch.cuda.is_available():
        logger.info("CUDA detected. Using GPU.")
        device = torch.device("cuda")
    else:
        logger.info("CUDA not detected. Using CPU.")
        device = torch.device("cpu")

    return device


def seed_torch(seed: int = 42, deterministic: bool = True) -> None:
    """Seed Python, NumPy, and torch RNGs for reproducibility.

    Covers the seeding common to every model. Model-specific extras (e.g. a
    framework's own ``seed_everything`` or ``PYTHONHASHSEED``) stay in the model.

    Args:
        seed: Seed value.
        deterministic: If True, sets torch cuDNN flags for deterministic behavior.
    """
    import random

    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed)

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)  # for multi-GPU

    torch.backends.cudnn.deterministic = deterministic
    torch.backends.cudnn.benchmark = not deterministic
