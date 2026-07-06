import re

aa_unambiguous = "ACDEFGHIKLMNPQRSTVWY"
aa_extended = aa_unambiguous + "BXZUO"

dna_unambiguous = "ACTG"

rna_unambiguous = "ACUG"

regexes = {
    "aa_extended": re.compile(f"^[{aa_extended}]+$"),
    "aa_unambiguous": re.compile(f"^[{aa_unambiguous}]+$"),
    "dna_unambiguous": re.compile(f"^[{dna_unambiguous}]+$"),
}


def validate_aa_extended(text: str) -> str:
    if not regexes["aa_extended"].match(text):
        raise ValueError(
            f"Residues can only be represented with '{aa_extended}' characters"
        )
    return text


def validate_aa_unambiguous(text: str) -> str:
    if not regexes["aa_unambiguous"].match(text):
        raise ValueError(
            f"Residues can only be represented with '{aa_unambiguous}' characters"
        )
    return text


def validate_dna_unambiguous(text: str) -> str:
    if not regexes["dna_unambiguous"].match(text):
        raise ValueError(
            f"Nucleotides can only be represented with '{dna_unambiguous}' characters"
        )
    return text


class AAUnambiguousPlusExtra:
    def __init__(self, extra: list[str]):
        if not extra:
            raise ValueError("Extra cannot be empty")
        self.extra = extra

    def __call__(self, value: str) -> str:
        text_clean = value
        for ex in self.extra:
            text_clean = text_clean.replace(ex, "")
        validate_aa_unambiguous(text_clean)
        return value


class AAExtendedPlusExtra:
    def __init__(self, extra: list[str]):
        if not extra:
            raise ValueError("Extra cannot be empty")
        self.extra = extra

    def __call__(self, value: str) -> str:
        text_clean = value
        for ex in self.extra:
            text_clean = text_clean.replace(ex, "")
        validate_aa_extended(text_clean)
        return value


class SingleOccurrenceOf:
    def __init__(self, single_token: str):
        self.single_token = single_token

    def __call__(self, value: str) -> str:
        count = value.count(self.single_token)
        if count != 1:
            raise ValueError(
                f"Expected a single occurrence of '{self.single_token}', got {count}"
            )
        return value


class SingleOrMoreOccurrencesOf:
    def __init__(self, token: str):
        self.token = token

    def __call__(self, value: str) -> str:
        count = value.count(self.token)
        if count < 1:
            raise ValueError(
                f"Expected at least one occurrence of '{self.token}', got none"
            )
        return value


class UpToNNonConsecutiveOccurrencesOf:
    """
    Validates that a given token appears no more than `max_count` times and
    never appears consecutively (e.g. '::').
    """

    def __init__(self, token: str, max_count: int):
        self.token = token
        self.max_count = max_count

    def __call__(self, value: str) -> str:
        total_count = value.count(self.token)
        if total_count > self.max_count:
            raise ValueError(
                f"Expected up to {self.max_count} occurrences of '{self.token}', "
                f"but found {total_count} in '{value}'."
            )
        if self.token * 2 in value:  # e.g., "::" if token=":"
            raise ValueError(
                f"Consecutive occurrences of '{self.token}' are not allowed: '{value}'."
            )
        return value


### SMILES validators

# Characters permitted in a SMILES string.
# Covers: atoms (A-Z, a-z), ring-closures (0-9, %nn), charges (+/-),
# branches (), stereochemistry @, bonds =#:/, dot . and wildcard *.
_SMILES_VALID_CHARS_RE = re.compile(r"^[A-Za-z0-9@+\-\[\]()=#%/\\.:\*]+$")


def validate_smiles(smiles: str) -> str:
    """Basic SMILES format validation that does not require rdkit.

    Checks that the string is non-empty, contains only recognised SMILES
    characters, and has balanced brackets / parentheses.  This is a
    lightweight sanity-check suitable for use inside pydantic validators that
    run on servers without rdkit installed.
    """
    if not smiles or not smiles.strip():
        raise ValueError("SMILES string cannot be empty")
    smiles = smiles.strip()
    if not _SMILES_VALID_CHARS_RE.match(smiles):
        raise ValueError(
            f"SMILES string contains invalid characters: {smiles!r}. "
            "Only standard SMILES notation is accepted."
        )
    if smiles.count("[") != smiles.count("]"):
        raise ValueError(f"SMILES string has unbalanced square brackets: {smiles!r}")
    if smiles.count("(") != smiles.count(")"):
        raise ValueError(f"SMILES string has unbalanced parentheses: {smiles!r}")
    return smiles
