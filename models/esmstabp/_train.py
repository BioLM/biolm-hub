from typing import Any

import modal

from models.commons.modal.source import setup_source_layer
from models.commons.util.config import cloudflare_r2_secret, common_requirements

"""
ESMStabP Model Training Script

This script trains the Random Forest regressors for ESMStabP thermostability prediction.
It extracts ESM2 embeddings from protein sequences and trains 4 model variants based on
available metadata features.

Usage:
    # Run training (this can take 30-60 minutes due to ESM2 embedding extraction):
    python models/esmstabp/_train.py

    # Or deploy as a Modal function and run remotely:
    modal run models/esmstabp/_train.py

The script will:
1. Fetch training dataset from GitHub (marcusramos2024/ESMStabP)
2. Extract ESM2 layer 33 mean embeddings for all sequences
3. Train 4 Random Forest models with different feature configurations
4. Upload trained models to R2

Model Variants:
- 1.joblib: Embedding only (1280 features)
- 2.joblib: Embedding + growth_temp + thermophilic flags (1283 features)
- 3.joblib: Embedding + experimental_condition (1282 features)
- 4.joblib: All features (1286 features) - matches original paper feature order

Dataset Format (CSV):
    Protein,sequence,growth_temp,lysate,cell,label_tm,thermophilic,nonThermophilic

Dataset Source:
    Combined from DeepStabP, DeepTM, and TemBERTure datasets.
    Source: https://github.com/marcusramos2024/ESMStabP/blob/main/Dataset%20Assembly/Dataset.csv
"""

# Training-specific image with ESM2 and scikit-learn
train_image = (
    modal.Image.from_registry("pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime")
    .apt_install("procps")
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        # ESM2 from GitHub
        "https://github.com/facebookresearch/esm/archive/2b369911bb5b4b0dda914521b9475cad1656b2ac.zip",
        # scikit-learn for Random Forest
        "scikit-learn==1.3.2",
        # joblib for model serialization
        "joblib==1.3.2",
        # numpy and pandas for data handling
        "numpy==1.23.5",
        "pandas==2.0.3",
        # tqdm for progress bars
        "tqdm==4.66.1",
        # requests for fetching dataset from GitHub
        "requests==2.31.0",
    )
)

# Add source layer to make models.commons available in the container
train_image = setup_source_layer("esmstabp")(train_image)

app = modal.App("esmstabp-training", image=train_image)

# Constants
BASE_MODEL_SLUG = "esmstabp"
PARAMS_VERSION = "v1"
R2_BUCKET = "biolm-modal"
# Must use model-store prefix to match commons/storage/downloads.py expectations
MODEL_R2_PREFIX = f"model-store/{BASE_MODEL_SLUG}/{PARAMS_VERSION}/"

# Dataset is fetched directly from the ESMStabP GitHub repository
# This ensures reproducibility without requiring manual data uploads
DATASET_GITHUB_URL = (
    "https://raw.githubusercontent.com/marcusramos2024/ESMStabP/main/"
    "Dataset%20Assembly/Dataset.csv"
)


@app.function(
    gpu="T4",
    memory=16 * 1024,
    timeout=7200,  # 2 hours for full training
    secrets=[cloudflare_r2_secret],
)
def train_esmstabp_models() -> dict[str, str]:
    """Train ESMStabP Random Forest models and upload to R2.

    Returns:
        Dictionary mapping model names to R2 paths
    """
    import io
    import tempfile
    from pathlib import Path

    import esm
    import joblib
    import numpy as np
    import pandas as pd
    import requests
    import torch
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import cross_val_score
    from tqdm import tqdm

    from models.commons.storage.r2 import get_r2_client

    print("=" * 60)
    print("ESMStabP Training Pipeline")
    print("=" * 60)

    # Set random seeds for reproducibility
    np.random.seed(42)
    torch.manual_seed(42)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(42)

    # Get R2 client from commons (for uploading trained models)
    s3 = get_r2_client()

    # Fetch training dataset directly from GitHub
    # Source: https://github.com/marcusramos2024/ESMStabP
    print("\n[1/5] Fetching training dataset from GitHub...")
    print(f"  URL: {DATASET_GITHUB_URL}")
    try:
        response = requests.get(DATASET_GITHUB_URL, timeout=60)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text))
        print(f"  Loaded {len(df)} training samples from GitHub")
    except requests.RequestException as e:
        raise RuntimeError(
            f"Failed to fetch training dataset from GitHub. "
            f"URL: {DATASET_GITHUB_URL}\n"
            f"Error: {e}"
        ) from e

    # Validate dataset columns
    required_cols = [
        "Protein",
        "sequence",
        "growth_temp",
        "lysate",
        "cell",
        "label_tm",
        "thermophilic",
        "nonThermophilic",
    ]
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"Dataset missing required columns: {missing}")

    # Balance dataset: sample non-thermophilic proteins to match thermophilic count
    # Paper: "non-thermophilic proteins were randomly sampled to balance the dataset"
    print("\n  Balancing dataset...")
    thermophilic_df = df[df["thermophilic"] == 1]
    non_thermophilic_df = df[df["nonThermophilic"] == 1]
    print(
        f"    Before balancing: {len(thermophilic_df)} thermophilic, "
        f"{len(non_thermophilic_df)} non-thermophilic"
    )

    # Sample non-thermophilic to match thermophilic count
    if len(non_thermophilic_df) > len(thermophilic_df):
        non_thermophilic_sampled = non_thermophilic_df.sample(
            n=len(thermophilic_df), random_state=42
        )
        df = pd.concat([thermophilic_df, non_thermophilic_sampled], ignore_index=True)
    else:
        # If already balanced or more thermophilic, keep all
        df = pd.concat([thermophilic_df, non_thermophilic_df], ignore_index=True)

    # Shuffle the balanced dataset
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    print(f"    After balancing: {len(df)} total samples")

    # Load ESM2 model
    print("\n[2/5] Loading ESM2 model (esm2_t33_650M_UR50D)...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, alphabet = esm.pretrained.load_model_and_alphabet_hub("esm2_t33_650M_UR50D")
    model.eval()
    model.to(device)
    batch_converter = alphabet.get_batch_converter()
    print(f"  ESM2 loaded on {device}")

    # Extract embeddings for all sequences
    print(f"\n[3/5] Extracting ESM2 layer 33 embeddings for {len(df)} sequences...")
    embeddings = []
    max_seq_len = 1022  # ESM2 limit

    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Extracting embeddings"):
        sequence = row["sequence"][:max_seq_len]  # Truncate if needed

        # Prepare batch
        batch_labels, batch_strs, batch_tokens = batch_converter([(str(idx), sequence)])
        batch_tokens = batch_tokens.to(device)

        # Forward pass
        with torch.no_grad():
            results = model(batch_tokens, repr_layers=[33], return_contacts=False)

        # Extract layer 33 mean embedding
        representations = results["representations"][33]
        seq_len = min(len(sequence), max_seq_len)
        embedding = representations[0, 1 : seq_len + 1].mean(dim=0).cpu().numpy()
        embeddings.append(embedding)

    embeddings_array = np.array(embeddings)
    print(f"  Extracted embeddings shape: {embeddings_array.shape}")

    # Print dataset statistics for debugging
    print("\n  Dataset statistics:")
    print(f"    Total samples: {len(df)}")
    print(
        f"    label_tm range: {df['label_tm'].min():.2f} - {df['label_tm'].max():.2f}"
    )
    print(
        f"    label_tm mean: {df['label_tm'].mean():.2f}, std: {df['label_tm'].std():.2f}"
    )
    print(f"    growth_temp unique values: {df['growth_temp'].nunique()}")
    print(
        f"    thermophilic distribution: {df['thermophilic'].value_counts().to_dict()}"
    )
    print(
        f"    lysate/cell distribution: lysate={df['lysate'].sum()}, cell={df['cell'].sum()}"
    )

    # Prepare feature matrices for each model variant
    print("\n[4/5] Training Random Forest models...")

    y = df["label_tm"].values

    # Model 1: Embedding only (1280 features)
    X1 = embeddings_array

    # Model 2: Embedding + growth_temp + thermophilic flags (1283 features)
    # Order: embedding, growth_temp, thermophilic, nonThermophilic
    X2 = np.column_stack(
        [
            embeddings_array,
            df["growth_temp"].values,
            df["thermophilic"].values,
            df["nonThermophilic"].values,
        ]
    )

    # Model 3: Embedding + experimental_condition (1282 features)
    # Order: embedding, lysate, cell (matching original paper order)
    X3 = np.column_stack([embeddings_array, df["lysate"].values, df["cell"].values])

    # Model 4: All features (1286 features)
    # CRITICAL: Order must match original paper: embedding, growthTemp, lysate, cell,
    # thermophilic, nonThermophilic
    X4 = np.column_stack(
        [
            embeddings_array,
            df["growth_temp"].values,
            df["lysate"].values,
            df["cell"].values,
            df["thermophilic"].values,
            df["nonThermophilic"].values,
        ]
    )

    # Train models - list of (filename, feature_matrix, description)
    models_config: list[tuple[str, Any, str]] = [
        ("1.joblib", X1, "Embedding only"),
        ("2.joblib", X2, "Embedding + growth_temp"),
        ("3.joblib", X3, "Embedding + condition"),
        ("4.joblib", X4, "All features"),
    ]

    trained_models: dict[str, RandomForestRegressor] = {}
    with tempfile.TemporaryDirectory() as tmpdir:
        for model_name, X, description in models_config:
            print(
                f"\n  Training {model_name} ({description}, {X.shape[1]} features)..."
            )

            # Train Random Forest
            rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
            rf.fit(X, y)

            # Cross-validation score
            cv_scores = cross_val_score(rf, X, y, cv=5, scoring="r2")
            print(f"    CV R² scores: {cv_scores}")
            print(f"    Mean CV R²: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")

            # Save model locally
            model_path = Path(tmpdir) / model_name
            joblib.dump(rf, model_path)
            trained_models[model_name] = rf
            print(f"    Saved to {model_path}")

        # Upload models to R2
        print("\n[5/5] Uploading trained models to R2...")
        uploaded_paths = {}

        for model_name in trained_models:
            local_path = Path(tmpdir) / model_name
            r2_key = f"{MODEL_R2_PREFIX}{model_name}"

            with open(local_path, "rb") as f:
                s3.put_object(Bucket=R2_BUCKET, Key=r2_key, Body=f.read())

            uploaded_paths[model_name] = f"r2://{R2_BUCKET}/{r2_key}"
            print(f"  Uploaded {model_name} to {uploaded_paths[model_name]}")

    print("\n" + "=" * 60)
    print("Training complete!")
    print("=" * 60)
    print("\nUploaded models:")
    for name, path in uploaded_paths.items():
        print(f"  {name}: {path}")

    return uploaded_paths


@app.local_entrypoint()
def main() -> None:
    """Run training pipeline."""
    print("Starting ESMStabP training pipeline...")
    print("This will take 30-60 minutes depending on GPU availability.\n")

    result = train_esmstabp_models.remote()

    print("\n" + "=" * 60)
    print("Training Pipeline Complete")
    print("=" * 60)
    print("\nTrained models uploaded to R2:")
    for name, path in result.items():
        print(f"  {name}: {path}")
    print(
        "\nYou can now deploy ESMStabP with:"
        "\n  python models/esmstabp/app.py --force-deploy"
    )


if __name__ == "__main__":
    # python models/esmstabp/_train.py
    main()
