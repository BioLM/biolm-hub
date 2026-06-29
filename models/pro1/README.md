# Pro-1

> **Reasoning language model for protein stability engineering** — takes a protein sequence + biological context + prior mutagenesis history and proposes stability-improving mutations with biochemical rationale.

## Overview

Pro-1 is an open-source protein reasoning model developed by Michael Hla (March 2025). It fine-tunes Llama-3.1-8B and Llama-3.3-70B with GRPO reinforcement learning against a Rosetta REF2015 physics-based reward, producing a model that reasons about protein engineering in natural language.

Unlike embedding or structure-prediction models, Pro-1 generates a chain-of-thought explaining *why* each proposed mutation should improve stability — drawing on biochemical principles and the biological context provided. This makes it unique among protein design tools in supporting truly iterative, interpretable rational design.

**Wet-lab validated:** K116E on FGF-1 achieved +24°C melting temperature improvement over wild-type while maintaining FGFR-1 binding — comparable to literature-optimized multi-mutation variants (Adaptyv Bio, 2025).

## Architecture

| Property | Value |
|---|---|
| Base model | Llama-3.1-8B-Instruct |
| Adapter | LoRA, 4-bit quantized via unsloth |
| Training | SFT on synthetic reasoning traces + GRPO (Rosetta REF2015 reward) + creativity reward |
| Max context | 32,768 tokens |
| Input | Protein sequence (plain AA string) + freeform text context |
| Output | Chain-of-thought reasoning trace + proposed mutation list |
| License | Apache-2.0 |

## Model Variants

| Variant | Checkpoint | Description | GPU |
|---|---|---|---|
| `8b` (default) | `all-lm-grpo-mega-run/checkpoints/checkpoint-20250225-025056-step40` | 8B + creativity + specificity reward | A10G |
| `8b-grpo` | `best-checkpoint` | 8B base GRPO only | A10G |

The 70B SFT-only variant is implemented upstream but not deployed here (gated `meta-llama/Llama-3.3-70B-Instruct` repo + A100 80 GB GPU required).

## Capabilities & Limitations

**CAN be used for:**
- Proposing stability-improving point mutations, insertions, and deletions for globular proteins
- Iterative design: incorporates results from prior mutagenesis rounds
- Interpretable engineering: each mutation comes with a biochemical rationale
- Enzyme engineering (primary training distribution — BRENDA database)
- Any single-chain protein where thermostability is the target property

**CANNOT be used for:**
- Structure prediction (use ESMFold or Boltz)
- Metalloproteins (metal coordination not modeled in training reward)
- Binding affinity optimization (stability reward only — no affinity signal in v1)
- Membrane proteins (poorly supported by ESMFold, used in training loop)

**Other considerations:**
- **Reasoning traces frequently hallucinate citations** — never trust paper references in outputs without independent verification
- Stochastic outputs — different runs may propose different mutations
- May "hack" Rosetta REF2015 — always validate proposals with independent scoring or experiment
- Author disclaimer: "the model is often quite dumb" — treat as a proposal generator, not an oracle

## Actions / Endpoints

### `generate`

Proposes stability-improving mutations for a protein sequence, with a reasoning trace explaining the biochemical rationale.

**Request Parameters (per item):**

| Parameter | Type | Default | Range | Description |
|---|---|---|---|---|
| `sequence` | str | required | 10–2000 AA | Amino acid sequence (standard 1-letter codes) |
| `name` | str | `""` | — | Protein name (used in prompt context) |
| `ec_number` | str | `""` | — | EC number for enzymes (e.g., `"4.2.1.1"`) |
| `reaction` | list[dict] | `[]` | — | List of `{substrates, products}` dicts (only first entry used) |
| `general_information` | str | `""` | — | Freeform biological context, literature notes, special considerations |
| `metal_ions` | list[str] | `[]` | — | Metal ions or cofactors present (e.g., `["Zn2+", "Mg2+"]`) |
| `active_site_residues` | list[str] | `[]` | — | Active site residues that must not be modified (e.g., `["H64", "H119"]`) |
| `known_mutations` | list[dict] | `[]` | — | Prior results: list of `{mutation, effect}` dicts |

**Generation Parameters (`params`):**

| Parameter | Type | Default | Range | Description |
|---|---|---|---|---|
| `max_iterations` | int | `3` | 1–10 | Max generation iterations |
| `max_new_tokens` | int | `8192` | 128–16384 | Max new tokens per iteration |
| `temperature` | float | `0.95` | (0, 2] | Sampling temperature |
| `top_p` | float | `0.95` | (0, 1] | Nucleus-sampling cutoff |
| `seed` | int | `null` | — | Random seed for reproducibility |

> Variant selection is via the gateway (each variant has its own deployed app), not a request body field.

**Response:**

```json
{
  "results": [
    {
      "reasoning": "<think>...</think> The proposed mutations target...",
      "mutations": [
        {
          "mutation": "K116E",
          "rationale": "Introduces salt bridge with R119, stabilizing the C-terminal helix"
        }
      ],
      "modified_sequence": "MSLSR...E...VKQT"
    }
  ]
}
```

## Usage Examples

```python
from models.pro1.schema import (
    Pro1GenerateRequest,
    Pro1GenerateParams,
    Pro1ProteinData,
)

request = Pro1GenerateRequest(
    params=Pro1GenerateParams(
        max_iterations=5,
        seed=42,
    ),
    items=[
        Pro1ProteinData(
            sequence="MSHHWGYGKHNGPEHWHKDFPIAKGERQSPVDIDTH",
            name="Human Carbonic Anhydrase II",
            ec_number="4.2.1.1",
            reaction=[{
                "substrates": ["Carbon dioxide", "Water"],
                "products": ["Bicarbonate", "H+"]
            }],
            general_information="""
            Relevant for industrial carbon capture. Key stability bottleneck
            is the C-terminal region. Previous studies show disulfide engineering
            at C205-C206 improves Tm by ~10°C (Smith et al. 2019).
            """,
            known_mutations=[
                {"mutation": "W5A", "effect": "destabilizes by 3°C, avoid"},
            ],
        )
    ],
)
```

## Performance & Benchmarks

### Published Results

#### Enzyme Benchmark (40 diverse enzymes, in silico, blog post 2025)

| Model | Success Rate ↑ |
|---|---|
| **Pro-1 8B (creativity+specificity, default)** | **47%** |
| Pro-1 8B (GRPO only) | 43% |
| ProteinMPNN | ~43% |
| EvoProtGrad | ~42% |

#### Wet-Lab Validation — FGF-1 Thermostability (Adaptyv Bio, 2025)

| Metric | Result |
|---|---|
| Sequences tested | 19 |
| Maintained binding | 6/19 (32%) |
| Improved Tm | 3/19 (16%) |
| Best single result | K116E: **+24°C Tm** vs wild-type |
| Literature comparison | Matched Q40P/S47I/H93G/K112N (multi-mutation variant) |

### SOTA Status

First open-source protein reasoning model as of March 2025. Competitive with ProteinMPNN and EvoProtGrad on enzyme stability benchmark. Unique in its interpretability and iterative feedback capabilities.

## Implementation Verification

### Verification Method

Option B (Known Extremes): test on FGF-1 K116E — published result is +24°C Tm, maintained FGFR-1 binding. Run Pro-1 on FGF-1 sequence and verify K116E appears in top proposals with a salt bridge rationale.

### Verification Status

Not yet run — requires initial deployment to execute inference.

## Resource Requirements

| Resource | 8B Variant |
|---|---|
| GPU | A10G (24 GB) |
| GPU Memory | ~12 GB |
| CPU | 4 cores |
| RAM | 16 GB |
| Storage (weights) | ~60 GB |
| Cold start | ~3 min (snapshots disabled) |
| Inference P50 | ~45 s per request |

## Implementation Notes

- Weights are LoRA adapters stored on HuggingFace (`mhla/pro-1`); loaded via `unsloth.FastLanguageModel` in 4-bit quantization
- Memory snapshots disabled — unsloth's in-place model patching and bitsandbytes 4-bit quantization are not snapshot-compatible; cold start is ~3 min
- Stochastic outputs — responses are not cached
- The optional "LM sequence applier" step (applies generated mutations back to the sequence via an LLM) requires an OpenAI API key — we implement a deterministic sequence applier instead

## License

- **Model weights**: Apache-2.0 ([HuggingFace mhla/pro-1](https://huggingface.co/mhla/pro-1))
- **Code**: Apache-2.0 ([GitHub michaelhla/pro-1](https://github.com/michaelhla/pro-1))
- No non-commercial restrictions.

## References & Citations

### Papers / Sources

1. Hla, Michael. "Pro-1: A Reasoning Model for Protein Stability Engineering." Blog post (March 2025). [https://michaelhla.com/blog/pro1.html](https://michaelhla.com/blog/pro1.html)
2. Adaptyv Bio. "Protein Designer Spotlight: Can a language model reason about protein design?" Blog post (June 2025). [https://www.adaptyvbio.com/blog/pro1/](https://www.adaptyvbio.com/blog/pro1/)

### BibTeX

```bibtex
@misc{hla2025pro1,
  title={Pro-1: A Reasoning Model for Protein Stability Engineering},
  author={Hla, Michael},
  year={2025},
  url={https://michaelhla.com/blog/pro1.html},
  note={Blog post. GitHub: https://github.com/michaelhla/pro-1}
}
```

### Links

- **Blog post**: [michaelhla.com/blog/pro1.html](https://michaelhla.com/blog/pro1.html)
- **Code**: [GitHub michaelhla/pro-1](https://github.com/michaelhla/pro-1)
- **Model weights**: [HuggingFace mhla/pro-1](https://huggingface.co/mhla/pro-1)
- **Wet-lab validation**: [Adaptyv Bio spotlight](https://www.adaptyvbio.com/blog/pro1/)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
