from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import torch


def get_torch_device() -> "torch.device":
    """
    Determines an appropriate torch.device for computation.

    Checks if CUDA is available (then 'cuda'), otherwise defaults to 'cpu'.

    Returns:
        torch.device: The Torch device object (e.g., "cuda" or "cpu").
    """
    import torch

    if torch.cuda.is_available():
        print("CUDA detected. Using GPU.")
        device = torch.device("cuda")
    else:
        print("CUDA not detected. Using CPU.")
        device = torch.device("cpu")

    return device
