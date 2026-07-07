# ChemBERTa — Biological & Chemical Context

How ChemBERTa fits into cheminformatics and drug discovery. For the API see [README.md](README.md);
for architecture and training see [MODEL.md](MODEL.md).

## Molecule Coverage

ChemBERTa operates on **small molecules** encoded as **SMILES** (Simplified Molecular-Input
Line-Entry System) strings — the 1D text serialization of a molecular graph. It is pretrained on a
100M-molecule subset of **ZINC20**, a database of commercially available (purchasable), largely
drug-like compounds. In catalog terms its input molecule type is `ligand`.

**Well covered:** organic drug-like small molecules — the kind found in medicinal-chemistry and
virtual-screening libraries (typical molecular weights, standard organic elements, common functional
groups, ring systems, stereochemistry, and charges expressible in SMILES).

**Poorly covered / out of distribution:** very large molecules (long peptides, oligonucleotides,
polymers) that exceed the ~510-token context; organometallics and exotic inorganic chemistry
under-represented in ZINC20; and any molecule whose SMILES exceeds the 512-character input cap.
ChemBERTa reads only the 1D SMILES — it has no explicit 3D conformer or stereochemically resolved
geometry.

## Biological Problems Addressed

Small molecules are the dominant modality in drug discovery, chemical biology, and agrochemical
research. Turning a molecule into a fixed-length numerical vector ("molecular featurization") is the
gateway to machine learning on chemistry. ChemBERTa addresses:

- **Molecular representation.** A learned, dense embedding of a molecule that downstream models can
  consume — an alternative to hand-crafted descriptors and circular fingerprints (ECFP).
- **Property / activity prediction (QSAR/QSPR).** Physicochemical properties (solubility,
  lipophilicity), ADMET endpoints (toxicity, blood–brain-barrier penetration), and bioactivity are
  predicted by training a lightweight head on ChemBERTa embeddings.
- **Library triage and novelty scoring.** The pseudo-log-likelihood provides a model-based
  "typicality" signal for ranking or filtering molecules — for example, flagging chemically unusual
  SMILES or screening the output of a generative model for plausibility.
- **Chemical similarity and clustering.** Embeddings support nearest-neighbor search, deduplication,
  and diversity analysis across compound collections.

## Applied Use Cases

- **QSAR feature extraction.** Embed a screening library with `encode` and train a classifier or
  regressor for a bioactivity or ADMET endpoint — the canonical ChemBERTa workflow. MolPROP (Rollins
  et al., 2024) demonstrates exactly this, fusing ChemBERTa-2 embeddings with a graph neural network
  and evaluating on seven MoleculeNet datasets (solubility, lipophilicity, toxicity, BBB penetration,
  and more).
- **Virtual-screening pre-filter.** Use embeddings (similarity to known actives) and/or `log_prob`
  (plausibility) to shortlist candidate ligands before committing expensive structure-based methods.
- **Generative-model quality control.** Score de-novo-generated SMILES with `log_prob` to
  down-weight implausible or degenerate outputs.
- **Baseline for representation benchmarks.** As a widely used pretrained SMILES encoder, ChemBERTa
  is a natural baseline against ECFP fingerprints and graph neural networks — noting that such
  embeddings do not always beat fingerprints (Praski et al., 2025).

## Related Models

ChemBERTa is the first small-molecule model in the catalog; the closest relatives are the other
masked-LM sequence encoders for different molecule types, and the structure models that consume
small-molecule ligands:

- **DNABERT-2** (`dnabert2`) — the analogous BPE-tokenized masked-LM encoder for DNA (`encode` +
  `log_prob`); use it when the input is nucleotides rather than a small molecule.
- **ESM-2** (`esm2`) / **ESM C** (`esmc`) — masked-LM protein encoders; combine ChemBERTa (ligand)
  with ESM (protein) embeddings for protein–ligand interaction models.
- **Chai-1** (`chai1`) / **BoltzGen** (`boltzgen`) — structure models that accept small-molecule
  SMILES ligands; use ChemBERTa to screen/rank ligands, then these to predict 3D protein–ligand
  structure.

## Biological Background

**SMILES** linearizes a molecular graph into a string by walking its atoms and bonds, encoding
elements, bonds (`=`, `#`), rings (matched digits), branches (parentheses), charges, and
stereochemistry. The same molecule can be written as many valid SMILES; canonicalization picks one
deterministically. A chemical language model treats these strings like sentences: by learning to fill
in masked tokens across 100M molecules, ChemBERTa internalizes statistical regularities of chemical
"grammar" — which atoms and groups co-occur, how rings close, which substructures are common — and
encodes them into a representation that transfers to downstream property-prediction tasks. This is
the direct chemical analogue of masked-language-model protein encoders (ESM) and DNA encoders
(DNABERT-2): the same self-supervised recipe, applied to the language of molecules.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
