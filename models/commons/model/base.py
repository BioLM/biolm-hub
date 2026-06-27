from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelParams:
    """Base class for defining model parameters.

    Define model names with same spelling as found in the publications.
    """

    display_name: (
        str  # Full, human-readable name of the model (eg: "ESM Inverse Folding")
    )
    base_model_slug: str  # Identifier used in API URLs (eg: "esm-if1")
    log_identifier: str  # Identifier used in logs and print statements (eg: "ESM-IF1")

    """ Define model checkpoint parameters """
    params_version: str

    """ Define model parameters """
    batch_size: int
    max_sequence_len: Optional[int]
    # add other model parameters to your inheriting class
