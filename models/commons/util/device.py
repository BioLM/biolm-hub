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
