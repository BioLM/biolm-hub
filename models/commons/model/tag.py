from enum import Enum

from pydantic import BaseModel, Field

"""
Standardized tag taxonomy for BioLM models.

This module defines a controlled vocabulary for categorizing biological language models
based on their input/output modalities, molecule types, tasks, and architectures.
"""


class InputModality(str, Enum):
    """The type of data the model accepts."""

    SEQUENCE = "sequence"
    STRUCTURE = "structure"
    MSA = "msa"
    SMILES = "smiles"
    TEXT = "text"  # For generic, non-biological text


class InputMolecule(str, Enum):
    """The type of biological molecule the model processes.

    Rule of Specificity: Models should be tagged with the most specific applicable
    molecule type. For example, antibody-specific models should use ANTIBODY,
    not PROTEIN.
    """

    PROTEIN = "protein"
    ANTIBODY = "antibody"
    NANOBODY = "nanobody"
    TCR = "tcr"
    PEPTIDE = "peptide"
    DNA = "dna"
    RNA = "rna"
    LIGAND = "ligand"
    COMPLEX = "complex"


class Task(str, Enum):
    """The primary goal or function of the model."""

    STRUCTURE_PREDICTION = "structure_prediction"
    INVERSE_FOLDING = "inverse_folding"
    EMBEDDING = "embedding"
    SEQUENCE_GENERATION = "sequence_generation"
    SEQUENCE_COMPLETION = "sequence_completion"
    PROPERTY_PREDICTION = "property_prediction"
    SEQUENCE_CLASSIFICATION = "sequence_classification"
    ANNOTATION = "annotation"
    FEATURE_EXTRACTION = "feature_extraction"
    SEQUENCE_OPTIMIZATION = "sequence_optimization"
    STABILITY_PREDICTION = "stability_prediction"
    UTILITY = "utility"  # For placeholder or utility models


class OutputModality(str, Enum):
    """The type of data the model produces."""

    STRUCTURE = "structure"
    SEQUENCE = "sequence"
    EMBEDDING = "embedding"
    LOG_PROBABILITIES = "log_probabilities"
    LOGITS = "logits"
    SCALAR = "scalar"
    CLASS_LABEL = "class_label"
    ANNOTATIONS = "annotations"
    DICTIONARY = "dictionary"
    TEXT = "text"  # For generic, non-biological text


class Architecture(str, Enum):
    """The underlying technical architecture of the model."""

    TRANSFORMER = "transformer"
    BERT = "bert"
    T5 = "t5"
    AUTOREGRESSIVE = "autoregressive"
    GNN = "gnn"
    DIFFUSION = "diffusion"
    ALGORITHMIC = "algorithmic"
    PLACEHOLDER = "placeholder"


class ModelTags(BaseModel):
    """A validated structure for applying tags to a model.

    Each model must define:
    - At least one input modality
    - At least one task
    - At least one output modality
    - At least one architecture

    Input molecules are optional (e.g., for utility models).
    """

    input_modality: list[InputModality] = Field(..., min_length=1)
    input_molecule: list[InputMolecule] = Field(default_factory=list)
    task: list[Task] = Field(..., min_length=1)
    output_modality: list[OutputModality] = Field(..., min_length=1)
    architecture: list[Architecture] = Field(..., min_length=1)
