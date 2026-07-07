# ChemBERTa — Technical Details

Deep technical reference for the served `DeepChem/ChemBERTa-100M-MLM` checkpoint. For the API and a
high-level summary, see [README.md](README.md); for biological context, see [BIOLOGY.md](BIOLOGY.md).

## Architecture

ChemBERTa is a RoBERTa encoder (`RobertaForMaskedLM`) applied to molecules serialized as SMILES
strings. It is architecturally a standard BERT-family masked language model; the chemistry lives
entirely in the tokenizer vocabulary and the training corpus, not in any bespoke layers.

| Component | Specification |
|-----------|---------------|
| Base class | `RobertaForMaskedLM` (`model_type: roberta`) |
| Encoder layers | 12 |
| Hidden size | 768 |
| Attention heads | 12 |
| Intermediate (FFN) size | 3,072 |
| Activation | GELU |
| Position embeddings | Absolute, learned; `max_position_embeddings = 512`, `padding_idx = 1` |
| Vocabulary | 7,924 byte-level BPE tokens learned over SMILES |
| Tied embeddings | Yes (`tie_word_embeddings = true`) |
| Total parameters | 92,136,436 (~92.1M); encoder alone ~91.5M |
| Precision | float32 (~369 MB on disk, safetensors) |

**Tokenizer.** A byte-level BPE tokenizer (`RobertaTokenizer` / `RobertaTokenizerFast`) with special
tokens `<s>` (id 0), `<pad>` (id 1), `</s>` (id 2), `<unk>` (id 3), and `<mask>` (id 4). SMILES are
tokenized verbatim — the tokenizer segments the raw string into learned chemical subwords (whole
rings, functional groups, and atoms can each map to single tokens). Because BPE merges characters,
**token count is typically well below character count** (e.g. `"CCO"` → a single `CCO` token). This
is why the schema carries two separate limits: a 512-**character** cap on the request field and a
510-**token** truncation limit for the model (`max_position_embeddings` 512 minus RoBERTa's
position-id offset of 2).

**Objective.** Masked language modeling: during pretraining ~15% of SMILES tokens are masked and the
model predicts them from bidirectional context. This is the same MLM head reused at inference for the
`log_prob` action.

## Performance & Benchmarks

Benchmarks are drawn only from the source papers and independent evaluations; no numbers are
estimated here.

- **Scaling with data (Chithrananda et al., 2020).** The original ChemBERTa study varied the
  pretraining set from 100K to 10M molecules and showed downstream MoleculeNet performance improves
  with pretraining set size — motivating the larger checkpoints such as this 100M one.
- **MoleculeNet competitiveness (Ahmad et al., 2022).** ChemBERTa-2 reports competitiveness with
  contemporary state-of-the-art SMILES and graph models across the MoleculeNet suite. It compares two
  pretraining objectives — masked language modeling (MLM) and multi-task regression (MTR) — and finds
  the **MTR variant generally outperforms MLM** on supervised property-prediction tasks. The
  checkpoint served here is the **MLM** variant, chosen because it yields a general-purpose embedding
  and a well-defined pseudo-log-likelihood rather than being tuned to a fixed regression task set.
- **Applied demonstration (MolPROP, Rollins et al., 2024, *J. Cheminformatics*, DOI
  10.1186/s13321-024-00846-9).** Fuses ChemBERTa-2 embeddings with a graph neural network and
  evaluates on seven MoleculeNet datasets (FreeSolv, ESOL, Lipophilicity, QM7, BACE, BBBP, ClinTox)
  under scaffold splits.
- **Embedding-baseline caveat (Praski et al., 2025, arXiv:2508.06199).** A benchmark of pretrained
  molecular embedding models across 25 datasets reports that most neural embeddings give negligible
  improvement over the classical ECFP fingerprint — i.e., a frozen SMILES embedding is not
  automatically better than a cheap fingerprint. Validate the lift on your own task.

Consult the paper tables directly for exact per-task metrics (they vary by split and metric and are
best read in context).

## Strengths & Limitations

**Strengths.**
- Small (~92M params) and CPU-friendly; cheap for high-throughput embedding/scoring.
- Standard RoBERTa — no `trust_remote_code`, robust across `transformers` versions, easy to audit.
- Byte-level BPE tokenizes arbitrary SMILES without a hand-built atom vocabulary, capturing
  multi-character chemical motifs as single tokens.
- Broad self-supervised pretraining (100M ZINC20 molecules) over drug-like / purchasable space.
- MIT-licensed — unrestricted commercial and academic use.

**Limitations.**
- Encoder-only masked LM: no molecular generation/design.
- The MLM objective underperforms MTR on supervised property prediction (per ChemBERTa-2).
- 1D SMILES only — no explicit 3D conformer or graph; sensitive to SMILES canonicalization.
- Pseudo-log-likelihood is summed over BPE tokens (not per-atom), so it is length-dependent and not a
  normalized per-molecule quantity.
- 512-position context; very large molecules are truncated. ZINC20 distribution limits
  out-of-distribution chemotypes.
- Lightweight (non-rdkit) input validation does not guarantee chemical validity.

## Implementation Details

- **Deployment.** CPU (`gpu=None`), `ModelMixinSnap` with `enable_memory_snapshot=True`; the model is
  loaded to CPU inside a single `@modal.enter(snap=True)` and captured in the memory snapshot. Torch
  seeds are set for reproducibility; the forward pass runs under `eval()` (no dropout), so outputs are
  deterministic.
- **Image.** `debian_slim` + CPU torch wheel (`torch==2.6.0` from the PyTorch CPU index) +
  `transformers==4.48.1`, `tokenizers==0.21.0`, `safetensors==0.5.3`, `huggingface_hub==0.26.0`. No
  CUDA base image (CPU-only model).
- **Weights.** `r2_then_hf` from `DeepChem/ChemBERTa-100M-MLM` pinned to
  `f5c45f44d3061f0346888f5c09db17ec1146d29d`. R2 cache is the fast primary; HuggingFace is the
  guaranteed fallback (and self-populates R2 for maintainer deploys).
- **`encode`.** Batch-tokenizes SMILES (`padding=True, truncation=True, max_length=510`), runs the
  RoBERTa encoder (`model.base_model`), and mean-pools the final hidden state over non-padded
  positions (attention-mask-weighted) → one 768-dim vector per molecule.
- **`log_prob`.** For each molecule, every non-special token position is replaced with `<mask>` in a
  batched copy of the sequence; the MLM logits at each masked position are log-softmaxed and the
  probability of the original token is summed → a per-molecule pseudo-log-likelihood.
- **Batching.** Up to 16 molecules per request (`ChemBERTaParams.batch_size`).

## Versions & Changelog

| Date | Change |
|------|--------|
| 2026-07 | Initial implementation. Serves `DeepChem/ChemBERTa-100M-MLM` @ `f5c45f44d3061f0346888f5c09db17ec1146d29d`. Actions: `encode`, `log_prob`. CPU deployment. First small-molecule model in the catalog. |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
