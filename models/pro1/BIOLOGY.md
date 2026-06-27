# Pro-1 — Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

Pro-1 is designed for **globular proteins**, with primary training on **enzymes** from the BRENDA database. It works on any protein expressible as a single amino acid sequence. Performance is best on:
- Soluble globular enzymes (the training distribution)
- Single-chain proteins with known catalytic function
- Proteins where stability is the bottleneck (not solubility, expression, or binding)

Performance degrades for:
- **Metalloproteins** — no metal coordination in training reward (Rosetta REF2015 does not fully model metal interactions)
- **Membrane proteins** — transmembrane regions are poorly modeled by ESMFold (used in training loop)
- **Intrinsically disordered regions** — stability concept less well-defined
- **Very short peptides** (<20 AA) or very long sequences (>500 AA)

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|---|---|---|---|
| Enzymes | **High** | Training distribution; 47% benchmark success | Best supported |
| Globular proteins | **High** | FGF-1 wet-lab validation (+24°C Tm) | Author notes non-enzyme proteins should work |
| Antibodies | **Medium** | No direct evidence; VH/VL are globular | CDR loops may have unusual sequence space |
| Peptides | **Low** | Short sequences, stability concept less clear | Consider peptide-specific models |
| Membrane proteins | **Low** | ESMFold struggles with transmembrane helices | Avoid |
| Metalloproteins | **Low** | Explicitly noted limitation | Metal coordination not modeled |

---

## Biological Problems Addressed

### Protein Thermostability Engineering

**The biological problem:**
Thermal stability (measured by melting temperature, Tm) determines whether a protein can function in industrial conditions, survive formulation, or maintain activity across physiological temperature ranges. Low Tm is a major barrier for:
- Industrial enzymes (biocatalysis, carbon capture, detergents)
- Therapeutic proteins (biostorage, administration)
- Research reagents (long-term assay use)

Traditional approaches (directed evolution, rational design, computational mutagenesis) are resource-intensive and require many experimental cycles.

**How Pro-1 addresses it:**
- Accepts sequence + biological context as text input
- Generates chain-of-thought reasoning about known stability mechanisms (hydrophobic core packing, salt bridges, disulfide bonds, helix capping)
- Proposes specific mutations (or insertions/deletions) with biochemical rationale
- Can incorporate results from previous experiments to guide next round of proposals

**Output interpretation:**
- Mutation proposals are natural language + sequence-level (e.g., "K116E — introduces a salt bridge with R119")
- Rosetta REF2015 used internally during training but not exposed at inference — proposals should be independently validated with ESMFold + Rosetta or experimentally

**Wet-lab validation result:**
K116E on FGF-1: +24°C Tm improvement while maintaining FGFR-1 binding affinity (Adaptyv Bio, 2025). Single-point mutation matched the performance of a highly optimized 4-mutation literature variant.

### Iterative Rational Design with Experimental Feedback

**The biological problem:**
Protein engineering typically requires multiple rounds of design → synthesis → assay → redesign. Most computational tools do not incorporate experimental feedback from previous rounds.

**How Pro-1 addresses it:**
The `known_mutations` input field accepts prior experimental results:
```python
"known_mutations": [
    {"mutation": "W19A", "effect": "reduces Tm by 5°C"},
    {"mutation": "K116E", "effect": "increases Tm by 24°C, maintains binding"},
]
```
The model reasons over this history to propose complementary or alternative mutations, enabling genuine iterative design loops.

---

## Applied Use Cases

### Thermostability Optimization of FGF-1 for Therapeutic Applications

**Source:** Adaptyv Bio. "Protein Designer Spotlight: Can a language model reason about protein design?" Adaptyv Blog (June 2025). [https://www.adaptyvbio.com/blog/pro1/](https://www.adaptyvbio.com/blog/pro1/)

FGF-1 (fibroblast growth factor 1) is therapeutically relevant for bone repair, pulmonary fibrosis, type 2 diabetes, and as a scaffold for cancer-targeting cytotoxin conjugates. Its low natural Tm (~49°C) limits industrial and clinical applications.

Pro-1 designed 19 variants. The K116E single-point mutant achieved:
- +24°C melting temperature improvement over wild-type
- Maintained binding to FGFR-1 (via BLI)
- Comparable to literature-optimized multi-mutation variant (Q40P/S47I/H93G/K112N)

**Key takeaway for BioLM users:** Pro-1 can discover high-impact single-point mutations that match the performance of exhaustively optimized multi-mutation designs. This is especially valuable early in a design campaign before investing in combinatorial screening.

---

## Related Models

### Predecessor Models

Pro-1 builds on the general reasoning capability of Llama 3.1/3.3 and the GRPO training paradigm from DeepSeek-R1. It also internally uses:
- **ESMFold** — for structure prediction during the GRPO training reward loop (not at inference time)
- **ESM3** — used to generate mutation candidates for SFT training data

### Complementary Models on BioLM

| Model | Role in Pipeline | When to combine |
|---|---|---|
| **ESMFold / Boltz** | Structure prediction of Pro-1 proposed variants | Validate structural plausibility of mutations |
| **ProteinMPNN** | Inverse folding for broader sequence redesign | After Pro-1 identifies stability-critical positions |
| **ESM2** | Embedding / variant effect scoring | Cross-validate Pro-1 proposals with embedding-based stability scores |
| **Rosetta (if available)** | Physics-based scoring | Score Pro-1 proposals in silico before synthesis |

**Recommended pipeline:**
```
Pro-1 (propose mutations with reasoning)
  → ESMFold (predict structure of proposed variants)
  → Rosetta REF2015 (score predicted stability)
  → [filter top candidates]
  → Wet-lab synthesis + characterization
  → [feed results back into Pro-1 for next iteration]
```

### Alternative Models

| Alternative | Advantage | Disadvantage vs Pro-1 |
|---|---|---|
| ProteinMPNN | State-of-art inverse folding; fast | Requires input structure; no reasoning traces; no experimental context input |
| EvoProtGrad | Gradient-guided directed evolution | No interpretability; no iterative feedback loop |
| FoldX / Rosetta | Physics-based, validated | Slow; no natural language I/O; no literature knowledge |
| GPT-4 / Claude (zero-shot) | General reasoning | Not tuned on protein stability physics |

---

## Biological Background

### Protein Thermostability

Protein thermal stability refers to the temperature at which a protein unfolds (melting temperature, Tm), and is governed by:

- **Hydrophobic core packing**: burial of hydrophobic residues stabilizes folded state
- **Salt bridges**: electrostatic interactions between oppositely charged residues (Arg↔Asp, Lys↔Glu) can stabilize or destabilize depending on context
- **Hydrogen bonds**: backbone and side-chain H-bonds contribute to secondary structure stability
- **Disulfide bonds**: covalent crosslinks dramatically increase stability (cysteine engineering)
- **Helix dipoles**: N-cap and C-cap mutations tune α-helix stability
- **Proline substitutions**: restrict backbone flexibility, increase stability of unstructured loops

### Why Tm Matters

| Application | Tm Requirement | Challenge |
|---|---|---|
| Industrial enzymes (detergents, food processing) | >60°C | Must survive process temperatures |
| Carbon capture biocatalysts | >50–70°C | High-temperature industrial conditions |
| Protein therapeutics | >50°C | Must survive formulation and storage |
| Research reagents | >45°C | Long shelf life at room temperature |

### Rosetta REF2015 Energy Function

Rosetta REF2015 is the physics-based scoring function used as Pro-1's training reward. It evaluates:
- Van der Waals interactions (steric clash, attractive contacts)
- Electrostatics (Coulombic interactions)
- Hydrogen bonding geometry
- Solvation (implicit solvent model)
- Side-chain rotamer probabilities

Lower REF2015 score = more stable predicted structure. Pro-1 was trained to propose mutations that reduce this score when evaluated on ESMFold-predicted structures.

**Important caveat:** REF2015 is an approximation. It can be "hacked" by sequences that score well in silico but are not experimentally stable — a known failure mode of Pro-1.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
