from models.boltz.config import MODEL_FAMILY
from models.commons.core.logging import get_logger
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator

logger = get_logger(__name__)

"""
Test fixtures and file mappings for Boltz model testing.

This module defines the input and output file paths used in the Boltz test suite.

R2 Structure:
-------------
r2://biolm-modal/test-data/models/boltz/
├── boltz1/                          # Boltz1 directory
│   ├── *_input.json                # Input files (uses "sequences" field)
│   └── *_expected_output.json      # Expected output files
└── boltz2/                          # Boltz2 directory
    ├── *_input.json                # Input files (uses "molecules" field)
    └── *_expected_output.json      # Expected output files

Key Points:
- Each model version has its own subdirectory with inputs and outputs
- No shared inputs - Boltz1 and Boltz2 have different input formats
- Boltz1 uses "sequences" field in input JSON
- Boltz2 uses "molecules" field in input JSON
- All constants below include the subdirectory path
"""


# BOLTZ1 INPUTS - Located at test-data/models/boltz/boltz1/*_input.json
BOLTZ1_PROTEIN_INPUT = "boltz1/protein_input.json"
BOLTZ1_CYCLIC_PROTEIN_INPUT = "boltz1/cyclic_protein_input.json"
BOLTZ1_MULTIMER_INPUT = "boltz1/multimer_input.json"
BOLTZ1_LIGAND_INPUT = "boltz1/ligand_input.json"  # Boltz1 ligand (no affinity support)
BOLTZ1_TRNA_INPUT = "boltz1/trna_input.json"
BOLTZ1_DNA_PROTEIN_INPUT = "boltz1/dna_protein_input.json"
BOLTZ1_MSA_INPUT = "boltz1/msa_input.json"
BOLTZ1_EMBEDDINGS_INPUT = "boltz1/embeddings_input.json"


# BOLTZ1 OUTPUTS - Located at test-data/models/boltz/boltz1/*_expected_output.json
BOLTZ1_PROTEIN_OUTPUT = "boltz1/protein_expected_output.json"
BOLTZ1_CYCLIC_PROTEIN_OUTPUT = "boltz1/cyclic_protein_expected_output.json"
BOLTZ1_MULTIMER_OUTPUT = "boltz1/multimer_expected_output.json"
BOLTZ1_MSA_OUTPUT = "boltz1/msa_expected_output.json"
BOLTZ1_LIGAND_OUTPUT = "boltz1/ligand_expected_output.json"
BOLTZ1_TRNA_OUTPUT = "boltz1/trna_expected_output.json"
BOLTZ1_DNA_PROTEIN_OUTPUT = "boltz1/dna_protein_expected_output.json"
BOLTZ1_EMBEDDINGS_OUTPUT = "boltz1/embeddings_output.json"
# Note: Boltz1 doesn't support templates, constraints (pocket), or affinity

# BOLTZ2 INPUTS - Located at test-data/models/boltz/boltz2/*_input.json
BOLTZ2_PROTEIN_INPUT = "boltz2/protein_input.json"
BOLTZ2_CYCLIC_PROTEIN_INPUT = "boltz2/cyclic_protein_input.json"
BOLTZ2_MULTIMER_INPUT = "boltz2/multimer_input.json"
BOLTZ2_LIGAND_INPUT = "boltz2/ligand_input.json"  # Boltz2 ligand (no affinity)
BOLTZ2_LIGAND_AFFINITY_INPUT = (
    "boltz2/ligand_affinity_input.json"  # Boltz2 with affinity
)
BOLTZ2_POCKET_INPUT = "boltz2/pocket_input.json"  # Boltz2 only (constraints)
BOLTZ2_TEMPLATE_INPUT = "boltz2/template_input.json"  # Boltz2 only (templates)
BOLTZ2_TRNA_INPUT = "boltz2/trna_input.json"
BOLTZ2_DNA_PROTEIN_INPUT = "boltz2/dna_protein_input.json"
BOLTZ2_MSA_INPUT = "boltz2/msa_input.json"
BOLTZ2_EMBEDDINGS_INPUT = "boltz2/embeddings_input.json"

# BOLTZ2 OUTPUTS - Located at test-data/models/boltz/boltz2/*_expected_output.json
BOLTZ2_PROTEIN_OUTPUT = "boltz2/protein_expected_output.json"
BOLTZ2_CYCLIC_PROTEIN_OUTPUT = "boltz2/cyclic_protein_expected_output.json"
BOLTZ2_MULTIMER_OUTPUT = "boltz2/multimer_expected_output.json"
BOLTZ2_LIGAND_OUTPUT = "boltz2/ligand_expected_output.json"
BOLTZ2_LIGAND_AFFINITY_OUTPUT = (
    "boltz2/ligand_affinity_expected_output.json"  # Missing constant added!
)
BOLTZ2_POCKET_OUTPUT = "boltz2/pocket_expected_output.json"
BOLTZ2_TRNA_OUTPUT = "boltz2/trna_expected_output.json"
BOLTZ2_DNA_PROTEIN_OUTPUT = "boltz2/dna_protein_expected_output.json"
BOLTZ2_MSA_OUTPUT = "boltz2/msa_expected_output.json"
BOLTZ2_TEMPLATE_OUTPUT = "boltz2/template_expected_output.json"
BOLTZ2_EMBEDDINGS_OUTPUT = "boltz2/embeddings_output.json"


# Create TestSuite for fixture generation with programmatic inputs
# This will be configured dynamically based on MODEL_VERSION
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[],  # Will be populated in generate() based on MODEL_VERSION
)


def generate():
    """Configures and runs the fixture generator"""
    import os

    from models.boltz.schema import Boltz1PredictRequest, Boltz2PredictRequest
    from models.boltz.test import DEFAULT_BOLTZ_TOLERANCES
    from models.commons.storage.r2 import read_json_from_r2
    from models.commons.util.config import r2_bucket_name, r2_test_data_dir

    # Determine which request type to use based on MODEL_VERSION
    model_version = os.getenv("MODEL_VERSION", "boltz2")
    if model_version == "boltz1":
        RequestClass = Boltz1PredictRequest
        logger.info("Using Boltz1PredictRequest for model version: %s", model_version)
    else:
        RequestClass = Boltz2PredictRequest
        logger.info("Using Boltz2PredictRequest for model version: %s", model_version)

    # Will collect test cases for this model version
    test_cases_for_model = []

    # Define test files for each model version
    if model_version == "boltz1":
        # Boltz1 test files - each tuple is (input_file, test_name, output_file)
        test_files = [
            (BOLTZ1_PROTEIN_INPUT, "protein", BOLTZ1_PROTEIN_OUTPUT),
            (
                BOLTZ1_CYCLIC_PROTEIN_INPUT,
                "cyclic_protein",
                BOLTZ1_CYCLIC_PROTEIN_OUTPUT,
            ),
            (BOLTZ1_MULTIMER_INPUT, "multimer", BOLTZ1_MULTIMER_OUTPUT),
            (BOLTZ1_TRNA_INPUT, "trna", BOLTZ1_TRNA_OUTPUT),
            (BOLTZ1_DNA_PROTEIN_INPUT, "dna_protein", BOLTZ1_DNA_PROTEIN_OUTPUT),
            (BOLTZ1_MSA_INPUT, "msa", BOLTZ1_MSA_OUTPUT),
            (BOLTZ1_LIGAND_INPUT, "ligand", BOLTZ1_LIGAND_OUTPUT),
        ]
    else:
        # Boltz2 test files - includes additional tests for template, pocket, and ligand affinity
        test_files = [
            (BOLTZ2_PROTEIN_INPUT, "protein", BOLTZ2_PROTEIN_OUTPUT),
            (
                BOLTZ2_CYCLIC_PROTEIN_INPUT,
                "cyclic_protein",
                BOLTZ2_CYCLIC_PROTEIN_OUTPUT,
            ),
            (BOLTZ2_MULTIMER_INPUT, "multimer", BOLTZ2_MULTIMER_OUTPUT),
            (BOLTZ2_TRNA_INPUT, "trna", BOLTZ2_TRNA_OUTPUT),
            (BOLTZ2_DNA_PROTEIN_INPUT, "dna_protein", BOLTZ2_DNA_PROTEIN_OUTPUT),
            (BOLTZ2_MSA_INPUT, "msa", BOLTZ2_MSA_OUTPUT),
            (BOLTZ2_LIGAND_INPUT, "ligand", BOLTZ2_LIGAND_OUTPUT),
            (
                BOLTZ2_LIGAND_AFFINITY_INPUT,
                "ligand_affinity",
                BOLTZ2_LIGAND_AFFINITY_OUTPUT,
            ),
            (BOLTZ2_POCKET_INPUT, "pocket", BOLTZ2_POCKET_OUTPUT),
            (BOLTZ2_TEMPLATE_INPUT, "template", BOLTZ2_TEMPLATE_OUTPUT),
        ]

    # Load from R2 and create test cases
    for input_file, test_name, output_file in test_files:
        # Full path includes subdirectory already from the constant
        input_path = f"{r2_test_data_dir}/models/boltz/{input_file}"
        try:
            input_data = read_json_from_r2(r2_bucket_name, input_path)

            # Create test case for the current model version
            test_case = ActionTestCase(
                action_name=ModelActions.FOLD,
                input_fixture=RequestClass(**input_data),  # Convert to Pydantic model
                input_filename_template=input_file,
                expected_output_fixture=output_file,
                tolerances=DEFAULT_BOLTZ_TOLERANCES,
            )
            test_cases_for_model.append(test_case)
            logger.info("Added %s test case for %s", test_name, model_version)
        except Exception as e:
            logger.warning("Could not load input file %s: %s", input_path, e)
            continue

    # Add embeddings test case (applies to all variants)
    # Create base embeddings input
    embeddings_base = {
        "params": {
            "recycling_steps": 1,
            "sampling_steps": 10,
            "diffusion_samples": 1,
            "seed": 42,
            "potentials": False,
            "include": ["embeddings"],
        },
        "items": [
            {
                "molecules": [
                    {
                        "id": "A",
                        "type": "protein",
                        "sequence": "MKLLVVVQVWHHHHH",  # Short 15-residue protein
                    }
                ]
            }
        ],
    }

    # Add Boltz2-specific fields if needed
    if model_version == "boltz2":
        # Add Boltz2-only params
        embeddings_base["params"].update(
            {
                "affinity_mw_correction": False,
                "sampling_steps_affinity": 200,
                "diffusion_samples_affinity": 5,
                "affinity": None,
            }
        )
        # Add Boltz2-only item fields
        embeddings_base["items"][0]["constraints"] = None
        embeddings_base["items"][0]["templates"] = None

    embeddings_input = embeddings_base
    logger.debug(
        "[Fixture] Embeddings input for %s: %s", model_version, embeddings_input
    )

    # Add embeddings test case - use model-specific constant
    embeddings_input_file = (
        BOLTZ1_EMBEDDINGS_INPUT
        if model_version == "boltz1"
        else BOLTZ2_EMBEDDINGS_INPUT
    )
    embeddings_output_file = (
        BOLTZ1_EMBEDDINGS_OUTPUT
        if model_version == "boltz1"
        else BOLTZ2_EMBEDDINGS_OUTPUT
    )

    test_cases_for_model.append(
        ActionTestCase(
            action_name=ModelActions.FOLD,
            input_fixture=RequestClass(**embeddings_input),  # Convert to Pydantic model
            input_filename_template=embeddings_input_file,
            expected_output_fixture=embeddings_output_file,
            tolerances=DEFAULT_BOLTZ_TOLERANCES,
        )
    )

    # Configure the suite with the collected test cases for this model version only
    fixture_generation_suite.variant_test_mappings = [
        VariantTestMapping(
            variant_config={
                "MODEL_VERSION": model_version
            },  # Only run for current model
            test_cases=test_cases_for_model,  # All the test cases we collected
        )
    ]

    # Create the generator and run it
    generator = FixtureGenerator(fixture_generation_suite)
    generator.generate()


if __name__ == "__main__":
    # Usage: MODEL_VERSION=boltz1 python models/boltz/fixture.py
    generate()
