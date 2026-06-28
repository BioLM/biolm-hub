"""Canonical, cross-model test inputs — the shared test-asset library.

Standard sequences used by more than one model live here as importable
constants, so per-model fixtures don't each hardcode (and independently drift)
their own copy. Importing a constant is the Modal-free way to reuse an input.

Each asset also has a stable canonical name under ``test-data/shared/`` in
public R2, for fixtures that reference a (typically large) shared input by path
instead of importing it — see the ``shared/`` path support in
``models.commons.testing.runner`` (a fixture path beginning with ``shared/``
resolves to ``test-data/shared/...`` rather than the per-model directory).

Naming convention (locked — also in CONTRIBUTING.md):

    test-data/shared/<category>/<name>.<ext>

    shared/protein/<name>.fasta    shared/dna/<name>.fasta
    shared/pdb/<name>.cif          shared/antibody/<name>.json
"""

# A standard 61-residue protein, used across the protein language models
# (esm2, esm1b, esmc, e1, dsm) for encode / predict / score smoke inputs.
# Canonical R2 name: shared/protein/standard.fasta
STANDARD_PROTEIN = "TPSSKEMMSQALKATFSGFTKEQQRLGIPKDPRQWTETHVRDWVMWAVNEFSLKGVDFQKF"

# A standard 65-residue protein, used by the thermostability models
# (esmstabp, temberture).
# Canonical R2 name: shared/protein/stability.fasta
STANDARD_PROTEIN_STABILITY = (
    "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG"
)
