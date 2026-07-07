# ChemBERTa

> **One-line summary**: A ~92M-parameter RoBERTa masked language model over SMILES strings that produces fixed-length small-molecule embeddings and a pseudo-log-likelihood plausibility score — opening the small-molecule modality for the catalog.

## Overview

**ChemBERTa** is a chemical language model developed by the DeepChem team. It applies the RoBERTa masked-language-modeling (MLM) paradigm to molecules represented as SMILES strings, producing dense molecular embeddings and pseudo-log-likelihood scores useful for property prediction, virtual screening, similarity search, and flagging unusual chemistry.

The checkpoint served here, [`DeepChem/ChemBERTa-100M-MLM`](https://huggingface.co/DeepChem/ChemBERTa-100M-MLM), was pretrained with the MLM objective on a 100M-molecule subset of the ZINC20 database. It is the direct descendant of the *ChemBERTa* (Chithrananda et al., 2020) and *ChemBERTa-2* (Ahmad et al., 2022) line of work, which showed that transformer models over SMILES scale with pretraining set size and are competitive with prior art on MoleculeNet. ChemBERTa is the first small-molecule model in the catalog: where the other sequence models target proteins, DNA, or RNA, ChemBERTa reads chemistry.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Transformer encoder (RoBERTa / `RobertaForMaskedLM`) |
| Parameters | ~92.1M |
| Hidden dimensions | 768 |
| Attention heads | 12 |
| Layers | 12 |
| Tokenization | Byte-level BPE over SMILES (`RobertaTokenizer`), vocab 7,924 |
| Max positions | 512 (usable input ~510 tokens after the RoBERTa position offset) |
| Training data | 100M-molecule subset of ZINC20 (MLM objective) |
| Precision | float32 |

See [MODEL.md](MODEL.md) for a full architecture and training deep-dive.

## Model Variants

Single variant — no size options. This deployment serves the `ChemBERTa-100M-MLM` checkpoint. DeepChem also publishes sibling checkpoints (5M / 10M / 77M / 100M pretraining sizes, and MLM vs. multi-task-regression objectives) on HuggingFace; only the 100M-MLM checkpoint is served here.

## Capabilities & Limitations

**CAN be used for:**
- Generating a fixed-length (768-dim) mean-pooled embedding for a small molecule from its SMILES (`encode`)
- Scoring a molecule's pseudo-log-likelihood under the model to rank or flag unusual/out-of-distribution SMILES (`log_prob`)
- Producing molecular features for downstream QSAR / property-prediction classifiers and regressors
- Similarity search, clustering, and deduplication over compound libraries

**CANNOT be used for:**
- Generating, optimizing, or designing novel molecules (encoder-only masked LM — no sampling head exposed)
- Predicting 3D structure or protein–ligand binding poses (use `chai1` or `boltzgen`, which consume SMILES ligands)
- Guaranteeing chemical validity or canonicalization of inputs (validation is a lightweight format check, not rdkit)
- Proteins, DNA, or RNA (use `esm2`/`esmc` for protein, `dnabert2`/`evo` for DNA)

**Other considerations:**
- Results can depend on the exact SMILES writing (canonicalization / kekulization) of the input; canonicalize upstream for consistency.
- The `log_prob` value is a pseudo-log-likelihood summed over byte-level BPE **tokens** (not per-atom), so it is not directly comparable across molecules of very different SMILES length.
- Very long SMILES are truncated to ~510 tokens; the training distribution is drug-like/purchasable ZINC20 chemistry, so exotic chemotypes are out-of-distribution.

## Actions / Endpoints

### `encode`

Compute one mean-pooled embedding vector per input molecule.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items` | list | - | 1–16 | Batch of molecules to embed |
| `items[].smiles` | str | - | 1–512 chars | A small molecule represented as a SMILES string |

**Response:**

```json
{
  "results": [
    { "embedding": [0.0123, -0.456, "... 768 floats"] }
  ]
}
```

### `log_prob`

Compute the pseudo-log-likelihood of each input molecule's SMILES under the masked LM.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items` | list | - | 1–16 | Batch of molecules to score |
| `items[].smiles` | str | - | 1–512 chars | A small molecule represented as a SMILES string |

**Response:**

```json
{
  "results": [
    { "log_prob": -18.07 }
  ]
}
```

## Usage Examples

```python
from models.chemberta.schema import (
    ChemBERTaEncodeRequest,
    ChemBERTaLogProbRequest,
)

# encode: SMILES -> 768-dim embedding
encode_request = ChemBERTaEncodeRequest.model_validate(
    {"items": [{"smiles": "CC(=O)Oc1ccccc1C(=O)O"}]}  # aspirin
)

# log_prob: pseudo-log-likelihood of a molecule
logprob_request = ChemBERTaLogProbRequest.model_validate(
    {"items": [{"smiles": "CCO"}, {"smiles": "Cn1cnc2c1c(=O)n(C)c(=O)n2C"}]}  # ethanol, caffeine
)
```

## Performance & Benchmarks

### Published Results

ChemBERTa's evaluations come from its two source papers, which report results on the **MoleculeNet** benchmark suite (Chithrananda et al., 2020; Ahmad et al., 2022). Key qualitative findings:

- Downstream property-prediction performance **scales with pretraining dataset size** (ChemBERTa, 2020).
- ChemBERTa-2 is **competitive with prior state-of-the-art** SMILES/graph models on MoleculeNet, and its **multi-task-regression (MTR) variant generally outperforms the MLM variant** on supervised property prediction (Ahmad et al., 2022). The checkpoint served here is the **MLM** variant.

Specific per-task metrics are tabulated in the papers; see the tables in Ahmad et al. (2022) rather than reproducing (potentially stale) numbers here.

### SOTA Status

Not state-of-the-art for supervised molecular property prediction. Independent benchmarking (Praski et al., 2025, arXiv:2508.06199) finds pretrained molecular embedding models frequently give negligible improvement over the classical ECFP fingerprint baseline — ChemBERTa is best treated as a fast, permissively licensed embedding baseline, not a guaranteed accuracy win. Verified July 2026.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | None (CPU) |
| Memory | 8 GB |
| CPU | 2 cores |
| Cold start | Fast (~92M params, ~369 MB weights; memory snapshot) |
| Dependencies | None (self-contained HuggingFace weights via `r2_then_hf`) |

## Implementation Notes

- **CPU deployment.** At ~92M parameters, ChemBERTa is small enough that a GPU is not worth it; it runs on CPU (`gpu=None`) with a Modal memory snapshot, mirroring the esm2 8m/35m CPU tier.
- **Weights.** Loaded from `DeepChem/ChemBERTa-100M-MLM` pinned to commit `f5c45f44d3061f0346888f5c09db17ec1146d29d` via the canonical `r2_then_hf` wrapper (R2 cache first, HuggingFace fallback). Standard `RobertaForMaskedLM` — no `trust_remote_code`.
- **Tokenization.** The byte-level BPE (`RobertaTokenizer`) is fed the **raw SMILES string** — it is *not* space-joined (that would be wrong for this tokenizer family). Character length ≠ token count.
- **Embeddings.** `encode` returns a mean-pooled embedding over non-padded token positions of the final hidden state (attention-mask-weighted), a robust default for RoBERTa-family encoders.
- **`log_prob`.** Each non-special token is masked in turn, and the log-softmax probability of the original token under the MLM head is summed — a pseudo-log-likelihood over BPE tokens.
- **Determinism.** `torch` seeds are set on load; the forward pass runs under `eval()` with no dropout, so outputs are deterministic.

### Implementation Verification

Loading the pinned checkpoint locally (real weights, transformers 4.48.1 / torch 2.6.0 CPU) confirmed: the tokenizer is `RobertaTokenizerFast` (byte-level BPE), SMILES are tokenized verbatim without space-joining (`"CCO"` → `['<s>', 'CCO', '</s>']`; aspirin → 13 BPE tokens), the mean-pooled embedding is 768-dimensional, `mask_token_id` is present, the `log_prob` masking loop runs, and repeated forward passes are bit-identical.

## License

- **Weights & code**: MIT — declared via the [HuggingFace model-card metadata tag](https://huggingface.co/DeepChem/ChemBERTa-100M-MLM) (`license: mit`). Upstream ships no standalone `LICENSE` file; the canonical MIT text is reproduced in this directory's [LICENSE](LICENSE).
- MIT is permissive (OSI-approved) — no commercial or academic-use restrictions.

## References & Citations

### Papers

1. Ahmad W., Simon E., Chithrananda S., Grand G., Ramsundar B. "ChemBERTa-2: Towards Chemical Foundation Models." *ELLIS Machine Learning for Molecule Discovery Workshop* (2022). [arXiv:2209.01712](https://arxiv.org/abs/2209.01712)
2. Chithrananda S., Grand G., Ramsundar B. "ChemBERTa: Large-Scale Self-Supervised Pretraining for Molecular Property Prediction." *ML4Molecules Workshop, NeurIPS* (2020). [arXiv:2010.09885](https://arxiv.org/abs/2010.09885)

### BibTeX

```bibtex
@article{ahmad2022chemberta2,
  title={ChemBERTa-2: Towards Chemical Foundation Models},
  author={Ahmad, Walid and Simon, Elana and Chithrananda, Seyone and Grand, Gabriel and Ramsundar, Bharath},
  journal={ELLIS Machine Learning for Molecule Discovery Workshop},
  year={2022},
  eprint={2209.01712},
  archivePrefix={arXiv}
}

@article{chithrananda2020chemberta,
  title={ChemBERTa: Large-Scale Self-Supervised Pretraining for Molecular Property Prediction},
  author={Chithrananda, Seyone and Grand, Gabriel and Ramsundar, Bharath},
  journal={ML4Molecules Workshop, NeurIPS},
  year={2020},
  eprint={2010.09885},
  archivePrefix={arXiv}
}
```

### Links

- **Paper (ChemBERTa-2)**: [arXiv:2209.01712](https://arxiv.org/abs/2209.01712)
- **Paper (ChemBERTa)**: [arXiv:2010.09885](https://arxiv.org/abs/2010.09885)
- **Code**: [github.com/deepchem/deepchem](https://github.com/deepchem/deepchem) · [bert-loves-chemistry](https://github.com/seyonechithrananda/bert-loves-chemistry)
- **Model weights**: [DeepChem/ChemBERTa-100M-MLM](https://huggingface.co/DeepChem/ChemBERTa-100M-MLM)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
