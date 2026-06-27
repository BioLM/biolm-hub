import pytest
from pydantic import Field, ValidationError

from models.commons.data import validator as v
from models.commons.data.structure_validator import validate_pdb
from models.commons.model.pydantic import RequestModel

# 1. RequestModel generic behavior


class DummyScalar(RequestModel):
    name: str = Field(...)


class DummyList(RequestModel):
    chains: list[str] = Field(..., min_length=1)


def test_dummy_scalar_accepts_correct_types():
    assert DummyScalar(name="alpha").name == "alpha"


def test_dummy_list_accepts_correct_types():
    assert DummyList(chains=["H", "L"]).chains == ["H", "L"]


def test_dummy_scalar_rejects_wrong_scalar_type():
    with pytest.raises(ValidationError):
        DummyScalar(name=123)  # type: ignore[arg-type]


def test_dummy_list_rejects_wrong_list_member_type():
    with pytest.raises(ValidationError):
        DummyList(chains=["H", 42])  # type: ignore[list-item]


# 2. Core amino-acid / nucleotide validators


def test_aa_unambiguous():
    assert v.validate_aa_unambiguous("ACDEFGHIKLMNP") == "ACDEFGHIKLMNP"
    with pytest.raises(ValueError):
        v.validate_aa_unambiguous("ACDZ")  # Z not allowed


def test_aa_extended():
    assert v.validate_aa_extended("ACDBXZ") == "ACDBXZ"
    with pytest.raises(ValueError):
        v.validate_aa_extended("ACD*")  # * not in extended set


def test_dna_unambiguous():
    assert v.validate_dna_unambiguous("ATCG") == "ATCG"
    with pytest.raises(ValueError):
        v.validate_dna_unambiguous("ATCX")  # X not allowed


# 3. Validators that accept "extra" tokens


def test_aa_unambiguous_plus_extra():
    validator = v.AAUnambiguousPlusExtra(extra=["*"])
    assert validator("ACD*EFG") == "ACD*EFG"
    with pytest.raises(ValueError):
        validator("ACD*EZ")  # Z not in unambiguous set


def test_aa_extended_plus_extra():
    validator = v.AAExtendedPlusExtra(extra=["-"])
    assert validator("ACD-BXZ") == "ACD-BXZ"
    with pytest.raises(ValueError):
        validator("ACD-123")  # digits not allowed even after stripping "-"


# 4. Token-counting helpers (Single / Multiple occurrences)


def test_single_occurrence():
    so = v.SingleOccurrenceOf("<mask>")
    assert so("A<mask>B") == "A<mask>B"
    with pytest.raises(ValueError):
        so("A<mask>B<mask>C")


def test_up_to_n_non_consecutive():
    up_to_two = v.UpToNNonConsecutiveOccurrencesOf(":", 2)
    assert up_to_two("A:B:C") == "A:B:C"
    with pytest.raises(ValueError):
        up_to_two("A:B:C:D")  # 3 colons > 2
    with pytest.raises(ValueError):
        up_to_two("A::B")  # consecutive


# 5. PDB sniffer


def test_pdb_pass_fail():
    good = "ATOM      1  N   ALA A   1      11.104   8.520   2.654"
    assert validate_pdb(good) == good
    with pytest.raises(ValueError):
        validate_pdb("HELLO WORLD")
