"""
BoltzGen pure unit tests — no Modal, no GPU, no R2, instant.

Tests:
  TestBoltzGenSchemaValidation — request/response schema validation
  TestPipelinePureFunctions    — Pure helper functions in pipeline.py and app.py

Run:
    pytest models/boltzgen/test_unit.py -v
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from models.boltzgen.schema import (
    BoltzGenChainSelector,
    BoltzGenDesignInsertion,
    BoltzGenDesignParams,
    BoltzGenDesignRequest,
    BoltzGenDesignRequestItem,
    BoltzGenDesignResponse,
    BoltzGenDesignSpec,
    BoltzGenEntity,
    BoltzGenFileEntity,
    BoltzGenLigandEntity,
    BoltzGenPipelineStep,
    BoltzGenProteinEntity,
    BoltzGenProtocol,
)

# ---------------------------------------------------------------------------
# Unit: schema validation
# ---------------------------------------------------------------------------


class TestBoltzGenSchemaValidation:
    """Smoke tests for BoltzGen request/response schema construction."""

    def test_protein_anything_request(self) -> None:
        request = BoltzGenDesignRequest(
            params=BoltzGenDesignParams(
                protocol=BoltzGenProtocol.PROTEIN_ANYTHING,
                num_designs=3,
                budget=2,
            ),
            items=[
                BoltzGenDesignRequestItem(
                    entities=[
                        BoltzGenEntity(
                            protein=BoltzGenProteinEntity(id="A", sequence="20..30")
                        ),
                        BoltzGenEntity(
                            protein=BoltzGenProteinEntity(
                                id="B", sequence="ACDEFGHIKLMNPQRSTVWY"
                            )
                        ),
                    ]
                )
            ],
        )
        assert request.params.protocol == BoltzGenProtocol.PROTEIN_ANYTHING
        assert len(request.items[0].entities) == 2

    def test_protein_small_molecule_request(self) -> None:
        request = BoltzGenDesignRequest(
            params=BoltzGenDesignParams(
                protocol=BoltzGenProtocol.PROTEIN_SMALL_MOLECULE,
                num_designs=3,
                budget=2,
            ),
            items=[
                BoltzGenDesignRequestItem(
                    entities=[
                        BoltzGenEntity(
                            protein=BoltzGenProteinEntity(id="A", sequence="140..180")
                        ),
                        BoltzGenEntity(ligand=BoltzGenLigandEntity(id="B", ccd="TSA")),
                    ]
                )
            ],
        )
        ligand = request.items[0].entities[1].ligand
        assert ligand is not None
        assert ligand.ccd == "TSA"

    def test_json_round_trip(self) -> None:
        original = BoltzGenDesignRequest(
            params=BoltzGenDesignParams(
                protocol=BoltzGenProtocol.PEPTIDE_ANYTHING,
                num_designs=5,
                budget=3,
            ),
            items=[
                BoltzGenDesignRequestItem(
                    entities=[
                        BoltzGenEntity(
                            protein=BoltzGenProteinEntity(
                                id="A", sequence="8..18", cyclic=True
                            )
                        )
                    ]
                )
            ],
        )
        reconstructed = BoltzGenDesignRequest.model_validate_json(
            original.model_dump_json()
        )
        assert reconstructed.params.num_designs == 5
        protein = reconstructed.items[0].entities[0].protein
        assert protein is not None
        assert protein.cyclic is True

    def test_mock_response_parsing(self) -> None:
        mock = {
            "results": [
                {
                    "cif": "data_design_0\nloop_\n_atom_site.group_PDB\nATOM 1 C CA ALA A 1 1.0 2.0 3.0",
                    "sequence": "ACDEFGHIKLMNPQRSTVWY",
                    "metrics": {"plddt": 85.5, "ptm": 0.75},
                },
                {
                    "cif": "data_design_1\nloop_\n_atom_site.group_PDB\nATOM 1 C CA GLY A 1 4.0 5.0 6.0",
                    "sequence": "WYTSVRQPNMLKIHGFEDCA",
                    "metrics": {"plddt": 78.2, "ptm": 0.68},
                },
            ]
        }
        response = BoltzGenDesignResponse.model_validate(mock)
        assert len(response.results) == 2
        assert response.results[0].metrics == {"plddt": 85.5, "ptm": 0.75}
        assert response.results[1].sequence == "WYTSVRQPNMLKIHGFEDCA"

    def test_request_requires_items(self) -> None:
        """A design request without items must fail (items is required)."""
        with pytest.raises(ValidationError, match="items"):
            BoltzGenDesignRequest.model_validate({"params": {}})

    def test_entity_rejects_multiple_types(self) -> None:
        with pytest.raises(ValidationError, match="Exactly one entity type"):
            BoltzGenEntity(
                protein=BoltzGenProteinEntity(id="A", sequence="MKLL"),
                ligand=BoltzGenLigandEntity(id="L", smiles="CCO"),
            )

    def test_ligand_requires_ccd_or_smiles(self) -> None:
        with pytest.raises(ValidationError, match="SMILES or CCD"):
            BoltzGenLigandEntity(id="L")

    def test_file_entity_requires_cif_or_pdb(self) -> None:
        with pytest.raises(ValidationError, match="cif.*pdb|pdb.*cif"):
            BoltzGenFileEntity()

    def test_res_index_valid_formats(self) -> None:
        """_ResIndexValidatorMixin accepts valid boltzgen res_index formats."""
        sel = BoltzGenChainSelector(id="A", res_index=5)
        assert sel.res_index == 5
        sel = BoltzGenChainSelector(id="A", res_index="10..16")
        assert sel.res_index == "10..16"
        sel = BoltzGenChainSelector(id="A", res_index="..10")
        assert sel.res_index == "..10"
        sel = BoltzGenChainSelector(id="A", res_index="1..5,10,20..30")
        assert sel.res_index == "1..5,10,20..30"
        sel = BoltzGenChainSelector(id="A", res_index="all")
        assert sel.res_index == "all"
        sel = BoltzGenChainSelector(id="A", res_index=[1, "10..16", 20])
        assert sel.res_index == [1, "10..16", 20]
        sel = BoltzGenChainSelector(id="A")
        assert sel.res_index is None

    def test_res_index_invalid_formats(self) -> None:
        """_ResIndexValidatorMixin rejects invalid res_index formats."""
        with pytest.raises(ValidationError, match="must be >= 1"):
            BoltzGenChainSelector(id="A", res_index=-1)
        with pytest.raises(ValidationError, match="must be >= 1"):
            BoltzGenChainSelector(id="A", res_index=0)
        with pytest.raises(ValidationError, match="Invalid res_index format"):
            BoltzGenChainSelector(id="A", res_index="abc")
        with pytest.raises(ValidationError, match="must be >= 1"):
            BoltzGenChainSelector(id="A", res_index=[1, -5])

    def test_insertion_requires_id_and_res_index(self) -> None:
        """BoltzGenDesignInsertion requires 'id' and 'res_index' keys."""
        di = BoltzGenDesignInsertion(
            insertion={"id": "B", "res_index": 26, "num_residues": "1..5"}
        )
        assert di.insertion["id"] == "B"
        with pytest.raises(ValidationError, match="'id' key"):
            BoltzGenDesignInsertion(insertion={"res_index": 26})
        with pytest.raises(ValidationError, match="'res_index' key"):
            BoltzGenDesignInsertion(insertion={"id": "B"})


# ---------------------------------------------------------------------------
# Unit: pure pipeline / app helper functions
# ---------------------------------------------------------------------------


class TestPipelinePureFunctions:
    """Tests for pure helper functions in pipeline.py and app.py."""

    # -- _strip_rank_prefix ---------------------------------------------------

    def test_strip_rank_prefix_removes_prefix(self) -> None:
        from models.boltzgen.pipeline import _strip_rank_prefix

        assert _strip_rank_prefix("rank001_design_spec_0.cif") == "design_spec_0.cif"

    def test_strip_rank_prefix_multiple_digits(self) -> None:
        from models.boltzgen.pipeline import _strip_rank_prefix

        assert _strip_rank_prefix("rank123_foo_bar.cif") == "foo_bar.cif"

    def test_strip_rank_prefix_no_prefix(self) -> None:
        from models.boltzgen.pipeline import _strip_rank_prefix

        assert _strip_rank_prefix("design_spec_0.cif") == "design_spec_0.cif"

    def test_strip_rank_prefix_rank_in_middle(self) -> None:
        from models.boltzgen.pipeline import _strip_rank_prefix

        assert _strip_rank_prefix("my_rank001_file.cif") == "my_rank001_file.cif"

    # -- _match_metrics_row ---------------------------------------------------

    def test_match_metrics_row_exact_filename(self) -> None:
        import pandas as pd

        from models.boltzgen.pipeline import _match_metrics_row

        df = pd.DataFrame(
            {"file_name": ["design_0.cif", "design_1.cif"], "plddt": [80.0, 90.0]}
        )
        row = _match_metrics_row("design_0.cif", df)
        assert row is not None
        assert row["plddt"] == 80.0

    def test_match_metrics_row_sans_extension(self) -> None:
        import pandas as pd

        from models.boltzgen.pipeline import _match_metrics_row

        df = pd.DataFrame(
            {"file_name": ["design_0", "design_1"], "plddt": [80.0, 90.0]}
        )
        row = _match_metrics_row("design_0.cif", df)
        assert row is not None
        assert row["plddt"] == 80.0

    def test_match_metrics_row_numeric_id(self) -> None:
        import pandas as pd

        from models.boltzgen.pipeline import _match_metrics_row

        df = pd.DataFrame({"id": [0, 1], "plddt": [80.0, 90.0]})
        row = _match_metrics_row("design_spec_0.cif", df)
        assert row is not None
        assert row["plddt"] == 80.0

    def test_match_metrics_row_no_match(self) -> None:
        import pandas as pd

        from models.boltzgen.pipeline import _match_metrics_row

        df = pd.DataFrame({"file_name": ["other.cif"], "plddt": [80.0]})
        row = _match_metrics_row("design_0.cif", df)
        assert row is None

    def test_match_metrics_row_anchored_regex(self) -> None:
        """Anchored regex matches trailing digits, not embedded ones."""
        import pandas as pd

        from models.boltzgen.pipeline import _match_metrics_row

        df = pd.DataFrame({"id": [7, 42], "plddt": [70.0, 99.0]})
        row = _match_metrics_row("design42_spec_7.cif", df)
        assert row is not None
        assert row["plddt"] == 70.0

    # -- _optional_configure_flags -------------------------------------------

    def test_optional_configure_flags_empty(self) -> None:
        from models.boltzgen.pipeline import BoltzGenPipelineMixin

        params = BoltzGenDesignParams()
        flags = BoltzGenPipelineMixin._optional_configure_flags(params)
        assert flags == []

    def test_optional_configure_flags_all_params(self) -> None:
        from models.boltzgen.pipeline import BoltzGenPipelineMixin

        params = BoltzGenDesignParams(
            diffusion_batch_size=4,
            step_scale=1.5,
            noise_scale=0.8,
            inverse_fold_num_sequences=3,
            inverse_fold_avoid="KC",
            refolding_rmsd_threshold=2.0,
            alpha=0.5,
            filter_biased=True,
            additional_filters=["plddt>70", "ptm>0.5"],
            metrics_override={"plddt": 1.0},
        )
        flags = BoltzGenPipelineMixin._optional_configure_flags(params)
        assert "--diffusion_batch_size" in flags
        assert "4" in flags
        assert "--step_scale" in flags
        assert "--noise_scale" in flags
        assert "--inverse_fold_num_sequences" in flags
        assert "3" in flags
        assert "--inverse_fold_avoid" in flags
        assert "KC" in flags
        assert "--refolding_rmsd_threshold" in flags
        assert "--alpha" in flags
        assert "--filter_biased" in flags
        assert "true" in flags
        assert "--additional_filters" in flags
        assert "plddt>70" in flags
        assert "ptm>0.5" in flags
        assert "--metrics_override" in flags

    def test_optional_configure_flags_inverse_fold_default_omitted(self) -> None:
        """inverse_fold_num_sequences=1 (default) is NOT forwarded."""
        from models.boltzgen.pipeline import BoltzGenPipelineMixin

        params = BoltzGenDesignParams(inverse_fold_num_sequences=1)
        flags = BoltzGenPipelineMixin._optional_configure_flags(params)
        assert "--inverse_fold_num_sequences" not in flags

    # -- _find_designs_dir ---------------------------------------------------

    def test_find_designs_dir_filtering_exists(self, tmp_path: Path) -> None:
        from models.boltzgen.pipeline import _find_designs_dir

        d = tmp_path / "final_ranked_designs" / "final_5_designs"
        d.mkdir(parents=True)
        result = _find_designs_dir(tmp_path, {BoltzGenPipelineStep.FILTERING}, budget=5)
        assert result == d

    def test_find_designs_dir_intermediate_only(self, tmp_path: Path) -> None:
        from models.boltzgen.pipeline import _find_designs_dir

        d = tmp_path / "intermediate_designs"
        d.mkdir()
        result = _find_designs_dir(tmp_path, set(), budget=5)
        assert result == d

    def test_find_designs_dir_nothing_exists(self, tmp_path: Path) -> None:
        from models.boltzgen.pipeline import _find_designs_dir

        with pytest.raises(FileNotFoundError, match="No output directory found"):
            _find_designs_dir(tmp_path, set(), budget=5)

    def test_find_designs_dir_skips_filtering_when_not_run(
        self, tmp_path: Path
    ) -> None:
        """If FILTERING step not in steps_run, skip filtering dir even if it exists."""
        from models.boltzgen.pipeline import _find_designs_dir

        filt_dir = tmp_path / "final_ranked_designs" / "final_5_designs"
        filt_dir.mkdir(parents=True)
        inter_dir = tmp_path / "intermediate_designs"
        inter_dir.mkdir()
        result = _find_designs_dir(tmp_path, set(), budget=5)
        assert result == inter_dir

    # -- _resolve_reset_res_index --------------------------------------------

    def test_resolve_reset_res_index_top_level_explicit(self) -> None:
        """Top-level reset_res_index is used directly."""
        from models.boltzgen.app import BoltzGenModel

        item = BoltzGenDesignRequestItem(
            entities=[
                BoltzGenEntity(protein=BoltzGenProteinEntity(id="A", sequence="MKLL")),
            ],
            reset_res_index=[BoltzGenChainSelector(id="A")],
        )
        result = BoltzGenModel._resolve_reset_res_index(item)
        assert result == [{"chain": {"id": "A"}}]

    def test_resolve_reset_res_index_per_file_explicit(self) -> None:
        """Per-file-entity reset_res_index is used when top-level is absent."""
        from models.boltzgen.app import BoltzGenModel

        cif_content = (
            "data_test\n"
            "loop_\n"
            "_atom_site.group_PDB\n"
            "_atom_site.type_symbol\n"
            "_atom_site.label_atom_id\n"
            "_atom_site.label_comp_id\n"
            "_atom_site.label_asym_id\n"
            "_atom_site.label_seq_id\n"
            "_atom_site.Cartn_x\n"
            "_atom_site.Cartn_y\n"
            "_atom_site.Cartn_z\n"
            "ATOM C CA ALA A 1 1.0 2.0 3.0\n"
        )
        item = BoltzGenDesignRequestItem(
            entities=[
                BoltzGenEntity(
                    file=BoltzGenFileEntity(
                        cif=cif_content,
                        reset_res_index=[BoltzGenChainSelector(id="B")],
                    )
                ),
            ],
        )
        result = BoltzGenModel._resolve_reset_res_index(item)
        assert result == [{"chain": {"id": "B"}}]

    def test_resolve_reset_res_index_auto_infer(self) -> None:
        """Auto-infer from single-file design specs."""
        from models.boltzgen.app import BoltzGenModel

        cif_content = (
            "data_test\n"
            "loop_\n"
            "_atom_site.group_PDB\n"
            "_atom_site.type_symbol\n"
            "_atom_site.label_atom_id\n"
            "_atom_site.label_comp_id\n"
            "_atom_site.label_asym_id\n"
            "_atom_site.label_seq_id\n"
            "_atom_site.Cartn_x\n"
            "_atom_site.Cartn_y\n"
            "_atom_site.Cartn_z\n"
            "ATOM C CA ALA A 1 1.0 2.0 3.0\n"
        )
        item = BoltzGenDesignRequestItem(
            entities=[
                BoltzGenEntity(
                    file=BoltzGenFileEntity(
                        cif=cif_content,
                        design=[
                            BoltzGenDesignSpec(chain="B", res_index="26..34"),
                        ],
                    )
                ),
            ],
        )
        result = BoltzGenModel._resolve_reset_res_index(item)
        assert result == [{"chain": {"id": "B"}}]

    def test_resolve_reset_res_index_no_match(self) -> None:
        """Returns None when no reset is needed."""
        from models.boltzgen.app import BoltzGenModel

        item = BoltzGenDesignRequestItem(
            entities=[
                BoltzGenEntity(protein=BoltzGenProteinEntity(id="A", sequence="MKLL")),
            ],
        )
        result = BoltzGenModel._resolve_reset_res_index(item)
        assert result is None

    def test_resolve_reset_res_index_chain_list(self) -> None:
        """Auto-infer with chain as a list deduplicates."""
        from models.boltzgen.app import BoltzGenModel

        cif_content = (
            "data_test\n"
            "loop_\n"
            "_atom_site.group_PDB\n"
            "_atom_site.type_symbol\n"
            "_atom_site.label_atom_id\n"
            "_atom_site.label_comp_id\n"
            "_atom_site.label_asym_id\n"
            "_atom_site.label_seq_id\n"
            "_atom_site.Cartn_x\n"
            "_atom_site.Cartn_y\n"
            "_atom_site.Cartn_z\n"
            "ATOM C CA ALA A 1 1.0 2.0 3.0\n"
        )
        item = BoltzGenDesignRequestItem(
            entities=[
                BoltzGenEntity(
                    file=BoltzGenFileEntity(
                        cif=cif_content,
                        design=[
                            BoltzGenDesignSpec(chain=["B", "C"]),
                            BoltzGenDesignSpec(chain="B"),  # duplicate
                        ],
                    )
                ),
            ],
        )
        result = BoltzGenModel._resolve_reset_res_index(item)
        assert result == [{"chain": {"id": "B"}}, {"chain": {"id": "C"}}]

    # -- additional_filters schema validation ---------------------------------

    def test_additional_filters_valid(self) -> None:
        """Valid filter expressions are accepted."""
        params = BoltzGenDesignParams(additional_filters=["plddt>70", "ptm>0.5"])
        assert params.additional_filters == ["plddt>70", "ptm>0.5"]

    def test_additional_filters_invalid(self) -> None:
        """Invalid filter expressions are rejected."""
        with pytest.raises(ValidationError, match="Invalid additional_filters entry"):
            BoltzGenDesignParams(additional_filters=["not a filter"])

    def test_additional_filters_none(self) -> None:
        """None is accepted (field is optional)."""
        params = BoltzGenDesignParams(additional_filters=None)
        assert params.additional_filters is None

    def test_additional_filters_gte_lte(self) -> None:
        """'>=' and '<=' operators are accepted."""
        params = BoltzGenDesignParams(additional_filters=["plddt>=70", "rmsd<=2.5"])
        assert params.additional_filters == ["plddt>=70", "rmsd<=2.5"]

    def test_additional_filters_negative_threshold(self) -> None:
        """Negative thresholds like 'affinity>-5.0' are accepted."""
        params = BoltzGenDesignParams(additional_filters=["affinity>-5.0"])
        assert params.additional_filters == ["affinity>-5.0"]
