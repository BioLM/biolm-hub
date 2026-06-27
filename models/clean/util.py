import csv
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn


class LayerNormNet(nn.Module):
    """
    CLEAN projection network.

    Takes ESM-1b embeddings (1280-dim) and projects them to a 128-dim
    learned embedding space where Euclidean distance reflects functional similarity.

    Architecture from: https://github.com/tttianhao/CLEAN
    """

    def __init__(
        self,
        hidden_dim: int = 512,
        out_dim: int = 128,
        drop_out: float = 0.1,
    ):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.out_dim = out_dim
        self.drop_out = drop_out

        # Input: ESM-1b mean representation (1280-dim)
        self.fc1 = nn.Linear(1280, hidden_dim)
        self.ln1 = nn.LayerNorm(hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.ln2 = nn.LayerNorm(hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, out_dim)
        self.dropout = nn.Dropout(p=drop_out)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: ESM-1b embeddings of shape (batch_size, 1280)

        Returns:
            CLEAN embeddings of shape (batch_size, 128)
        """
        x = self.dropout(self.ln1(self.fc1(x)))
        x = torch.relu(x)
        x = self.dropout(self.ln2(self.fc2(x)))
        x = torch.relu(x)
        x = self.fc3(x)
        return x


def load_ec_id_mapping(csv_path: Path) -> tuple[dict, dict]:
    """
    Load EC-ID mappings from split100.csv.

    Args:
        csv_path: Path to split100.csv file

    Returns:
        Tuple of (id_ec, ec_id_dict):
        - id_ec: Dict mapping protein ID to list of EC numbers
        - ec_id_dict: Dict mapping EC number to set of protein IDs
    """
    id_ec: dict[str, list[str]] = {}
    ec_id_dict: dict[str, set[str]] = {}

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for i, row in enumerate(reader):
            if i == 0:  # Skip header
                continue
            protein_id = row[0]
            ec_numbers = row[1].split(";")

            id_ec[protein_id] = ec_numbers

            for ec in ec_numbers:
                if ec not in ec_id_dict:
                    ec_id_dict[ec] = set()
                ec_id_dict[ec].add(protein_id)

    return id_ec, ec_id_dict


def compute_cluster_centers(
    model_emb: torch.Tensor,
    ec_id_dict: dict[str, set[str]],
) -> dict[str, torch.Tensor]:
    """
    Compute EC cluster centers from embeddings.

    For each EC number, computes the mean of all embeddings belonging to that EC.

    Args:
        model_emb: Tensor of shape (n_sequences, embedding_dim) containing
                   all training embeddings in EC order
        ec_id_dict: Dict mapping EC number to set of protein IDs

    Returns:
        Dict mapping EC number to cluster center tensor (embedding_dim,)
    """
    cluster_centers: dict[str, torch.Tensor] = {}
    id_counter = 0

    with torch.no_grad():
        for ec in ec_id_dict.keys():
            n_sequences = len(ec_id_dict[ec])
            emb_cluster = model_emb[id_counter : id_counter + n_sequences]
            cluster_center = emb_cluster.mean(dim=0)
            cluster_centers[ec] = cluster_center.cpu()
            id_counter += n_sequences

    return cluster_centers


def maximum_separation(dist_lst: np.ndarray) -> int:
    """
    Maximum separation algorithm for EC number selection.

    Finds the cutoff point where predicted EC numbers have maximum separation
    from other candidates. This is the greedy approach from the CLEAN paper.

    Args:
        dist_lst: Array of distances to top EC candidates (sorted ascending)

    Returns:
        Index of cutoff (predictions 0..index should be included)
    """
    # Pad with last distance value
    gamma = np.append(dist_lst[1:], np.repeat(dist_lst[-1], 10))

    # Compute separation scores
    sep_lst = np.abs(dist_lst - np.mean(gamma))

    # Compute gradient of separation
    sep_grad = np.abs(sep_lst[:-1] - sep_lst[1:])

    # Find max separation index by largest gradient
    max_sep_i = int(np.argmax(sep_grad))

    # If no clear separation found, just return first EC
    if max_sep_i >= 5:
        max_sep_i = 0

    return max_sep_i


def compute_gmm_confidence(
    distance: float,
    gmm_ensemble: list,
) -> float:
    """
    Compute confidence score using GMM ensemble.

    Uses a trained Gaussian Mixture Model to estimate the probability
    that a given distance corresponds to a true positive prediction.

    Args:
        distance: Euclidean distance to EC cluster center
        gmm_ensemble: List of trained GMM models

    Returns:
        Mean confidence score across ensemble (0-1)
    """
    confidences = []

    for gmm in gmm_ensemble:
        # Get means of the two Gaussian components
        a, b = gmm.means_
        # True positives have smaller distances
        true_model_index = 0 if a[0] < b[0] else 1
        # Get probability of belonging to true positive component
        certainty = gmm.predict_proba([[distance]])[0][true_model_index]
        confidences.append(certainty)

    return float(np.mean(confidences))
