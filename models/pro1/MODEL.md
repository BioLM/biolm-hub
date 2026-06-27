# Pro-1 — Technical Details

## Architecture

### Model Type & Innovation

Pro-1 is a **reasoning language model** for protein stability engineering. Unlike structure-prediction or sequence-embedding models, Pro-1 frames protein engineering as a *reasoning task*: given a sequence, its biological context, and prior mutagenesis data, the model generates a chain-of-thought explaining *why* specific mutations should improve stability, then proposes the modifications.

Key innovation: combining RL fine-tuning (GRPO) with a physics-based reward (Rosetta REF2015) to align a general-purpose LLM toward protein stability optimization — without requiring large, curated wet-lab datasets.

### Parameters & Layers

| Component | 8B Variant |
|---|---|
| Base model | Llama-3.1-8B-Instruct |
| Adapter type | LoRA (4-bit quantized) |
| Quantization | 4-bit via unsloth |
| Max context length | 32,768 tokens |
| Storage (weights) | ~60 GB |

The upstream 70B SFT-only checkpoint is not deployed on BioLM (gated `meta-llama/Llama-3.3-70B-Instruct` repo + A100 80 GB requirement).

### Training Data

| Phase | Data | Details |
|---|---|---|
| SFT (Phase 1) | BRENDA enzyme database | Sequences perturbed via BLOSUM matrices + ESM3 mutations; LLM generates recovery reasoning traces |
| GRPO (Phase 2) | Same enzyme sequences | Reward: Rosetta REF2015 energy score of ESMFold-predicted structures |
| Creativity tuning (Phase 3) | Same + LLM judge | LLM scores novelty of proposed modifications |

Training focused on enzymes (BRENDA), but the model generalizes to arbitrary protein sequences.

### Loss Function & Objective

**Phase 1 — Supervised Fine-Tuning:**
Standard cross-entropy on (perturbed_sequence, context → reasoning_trace → recovered_sequence) triplets.

**Phase 2 — GRPO (Group Relative Policy Optimization):**
- Generate K candidate modifications per input
- Score each with Rosetta REF2015 via ESMFold structure prediction
- Reward signal: binary (positive if Rosetta energy improved)
- GRPO normalizes rewards within the group of K candidates to compute policy gradient

**Phase 3 — Creativity + Specificity Rewards:**
- LLM judge scores novelty of proposed modifications
- Encourages larger structural changes (insertions, deletions) not just point mutations
- Raises benchmark success from 43% → 47%

### Tokenization / Input Processing

Standard Llama tokenizer (SentencePiece, BPE). Protein sequences are passed as plain ASCII amino acid strings within a structured text prompt. No special protein tokenization.

Prompt structure (simplified):
```
<system>You are a protein engineering expert...</system>
<user>
Protein: {NAME}
EC Number: {EC}
Reaction: {REACTION}
Sequence: {SEQUENCE}
Previous mutations: {KNOWN_MUTATIONS}
Additional context: {GENERAL_INFORMATION}

Propose modifications to improve stability.
</user>
```

---

## Performance & Benchmarks

### Published Benchmarks

#### Enzyme Stability Benchmark (40 diverse enzymes, blog post)

| Model | Success Rate ↑ |
|---|---|
| **Pro-1 8B (creativity+specificity)** | **47%** |
| Pro-1 8B (GRPO only) | 43% |
| ProteinMPNN | ~43% |
| EvoProtGrad | ~42% |

*Success = Rosetta REF2015 energy improvement on held-out test sequences.*
*Note: Quantized 8B outperformed unquantized larger models in this benchmark.*

#### Wet-Lab Validation (Adaptyv Bio, FGF-1, June 2025)

| Variant | ΔTm vs WT | FGFR-1 Binding |
|---|---|---|
| **K116E** | **+24°C** | Maintained |
| 2 other Pro-1 variants | > WT Tm | Maintained |
| Literature best (Q40P/S47I/H93G/K112N) | ~+24°C | Maintained |
| Wild-type FGF-1 | baseline (~49°C) | Baseline |

*19 sequences tested; 6/19 maintained WT-level binding; 3/19 exceeded WT melting temperature.*

### BioLM Verification Results

<!-- TODO: Run verification once implementation is deployed — compare Pro-1 output on 3-5 known enzyme sequences against published examples from blog post -->

### Comparison to Alternatives

| Model | Task | Approach | When to prefer Pro-1 |
|---|---|---|---|
| ProteinMPNN | Inverse folding / sequence design | Structure-conditioned | Pro-1 when no structure available or when interpretability needed |
| EvoProtGrad | Directed evolution | Gradient-based sequence exploration | Pro-1 for iterative design with experimental context |
| ESM2 + downstream | Variant effect | Embedding-based | Pro-1 when reasoning traces help interpret results |
| Rosetta directly | Stability optimization | Physics-based energy minimization | Pro-1 for sequence proposals; Rosetta for scoring/refinement |

---

## Strengths & Limitations

### Pros

- **Interpretable**: reasoning traces explain biochemical rationale for each mutation
- **Iterative**: accepts prior mutagenesis results as input — improves with experimental feedback
- **Flexible input**: freeform text context, no structure required
- **Creative**: can propose insertions/deletions, not just point mutations
- **Competitive accuracy**: 47% success rate matches dedicated protein engineering tools
- **Fully open-source**: Apache-2.0, weights on HuggingFace

### Cons

- **Hallucinates citations**: reasoning traces frequently cite non-existent papers — never trust references without verification
- **Imperfect reward signal**: trained on Rosetta REF2015, which is an approximation of true stability
- **ESMFold limitation**: structure prediction quality degrades for point mutations (used in training loop)
- **Metalloprotein limitation**: poorly supported — no metal coordination in training reward
- **Preview quality**: author explicitly warns "the model is often quite dumb"
- **No structure output**: text-only — pair with ESMFold/Boltz for structural validation

### Known Failure Modes

- Mutations may be proposed but not correctly applied to the output sequence — always verify the final modified sequence
- May "hack" REF2015 (propose sequences that score well in silico but are biologically nonsensical)
- Performance degrades on non-enzyme proteins (trained primarily on BRENDA enzyme set)
- Very short (<20 AA) or very long (>500 AA) sequences may not work well

---

## Implementation Details

### Inference Pipeline

```
Request
  ├── 1. Validate: sequence, enzyme_data, model config
  ├── 2. Format prompt: sequence + context + known_mutations → structured text
  ├── 3. Load LoRA adapter on top of Llama base (4-bit, unsloth)
  ├── 4. Generate (streaming): up to 32,768 tokens
  │     └── <think>...</think> reasoning trace + proposed mutations
  └── 5. Parse output: extract mutation proposals from generated text
```

### Memory & Compute Profile

| Variant | GPU Memory | Min GPU | Inference Time (est.) |
|---|---|---|---|
| 8B (4-bit) | ~8–12 GB | A10G | 30–90 s per request |

### Determinism & Reproducibility

Stochastic — LLM generation with temperature sampling. Set `seed` in generation config for reproducibility. Reasoning traces will vary between runs even with same input.

### Caching Behavior

LLM text generation — not cached by default (outputs are stochastic and context-dependent).

---

## Versions & Changelog

| Version | Date | Changes |
|---|---|---|
| v1.0 | 2025-03-29 | Initial BioLM implementation — 8B default checkpoint |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
