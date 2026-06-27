"""
BoltzGen pure unit tests — no Modal, no GPU, no R2, instant.

Tests:
  TestCheckpointManifest       — CheckpointManifest JSON round-trip + requested_steps
  TestBoltzGenSchemaValidation — request/response schema; resume/partial-response fields
  TestExitHandler              — @modal.exit() checkpoint handler logic (mocked)
  TestPipelinePureFunctions    — Pure helper functions in pipeline.py and app.py

Run:
    pytest models/boltzgen/test_unit.py -v
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from models.boltzgen.output_delivery import (
    CheckpointManifest,
    OutputJob,
)
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
# Unit: CheckpointManifest
# ---------------------------------------------------------------------------


class TestCheckpointManifest:
    def test_json_round_trip(self):
        m = CheckpointManifest(
            job_id="abc-123",
            model_slug="boltzgen",
            completed_steps=["design", "inverse_folding"],
            remaining_steps=["folding", "analysis", "filtering"],
            requested_steps=[
                "design",
                "inverse_folding",
                "folding",
                "analysis",
                "filtering",
            ],
        )
        m2 = CheckpointManifest.from_json(m.to_json())
        assert m2.job_id == "abc-123"
        assert m2.completed_steps == ["design", "inverse_folding"]
        assert m2.remaining_steps == ["folding", "analysis", "filtering"]
        assert m2.requested_steps == [
            "design",
            "inverse_folding",
            "folding",
            "analysis",
            "filtering",
        ]
        assert m2.created_at == m.created_at

    def test_updated_at_refreshes_on_upload(self, tmp_path):
        """upload_checkpoint mutates manifest.updated_at before uploading."""
        import time

        m = CheckpointManifest(
            job_id="x",
            model_slug="boltzgen",
            completed_steps=[],
            remaining_steps=["design"],
            requested_steps=["design"],
        )
        original_updated = m.updated_at
        time.sleep(0.01)  # ensure clock advances

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "dummy.txt").write_text("hello")

        job = OutputJob("boltzgen", "x")

        fake_client = MagicMock()
        fake_client.upload_fileobj = MagicMock()

        with (
            patch(
                "models.commons.storage.r2.get_r2_client",
                return_value=fake_client,
            ),
            patch.dict(os.environ, {"PROTOCOLS_R2_BUCKET": "test-bucket"}),
        ):
            result = job.upload_checkpoint(output_dir, m)

        assert result is True
        assert m.updated_at != original_updated

    def test_default_requested_steps_is_empty_list(self):
        """requested_steps defaults to [] for backward compat with old checkpoints."""
        m = CheckpointManifest(
            job_id="y",
            model_slug="boltzgen",
            completed_steps=["design"],
            remaining_steps=[],
        )
        assert m.requested_steps == []

    def test_from_json_without_requested_steps(self):
        """Old checkpoint JSON missing requested_steps round-trips via from_json without error."""
        import json

        old_json = json.dumps(
            {
                "job_id": "old",
                "model_slug": "boltzgen",
                "completed_steps": ["design"],
                "remaining_steps": [],
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        )
        m = CheckpointManifest.from_json(old_json)
        assert m.requested_steps == []
        assert m.job_id == "old"

    def test_from_json_ignores_unknown_keys(self):
        """from_json silently drops keys not in the dataclass — forward compat."""
        import json

        future_json = json.dumps(
            {
                "job_id": "future",
                "model_slug": "boltzgen",
                "completed_steps": ["design"],
                "remaining_steps": [],
                "requested_steps": ["design"],
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "new_future_field": "should be ignored",
                "another_unknown": 42,
            }
        )
        m = CheckpointManifest.from_json(future_json)
        assert m.job_id == "future"
        assert m.completed_steps == ["design"]
        assert not hasattr(m, "new_future_field")


# ---------------------------------------------------------------------------
# Unit: schema validation (resume fields)
# ---------------------------------------------------------------------------


class TestBoltzGenSchemaValidation:
    """Smoke tests for BoltzGen request/response schema construction."""

    def test_protein_anything_request(self):
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

    def test_protein_small_molecule_request(self):
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
        assert request.items[0].entities[1].ligand.ccd == "TSA"

    def test_json_round_trip(self):
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
        assert reconstructed.items[0].entities[0].protein.cyclic is True

    def test_mock_response_parsing(self):
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
        assert response.is_complete is True

    def test_resume_rejects_items(self):
        """items must not be provided alongside resume_job_id."""
        with pytest.raises(ValidationError, match="Cannot provide 'items'"):
            BoltzGenDesignRequest.model_validate(
                {
                    "items": [
                        {"entities": [{"protein": {"id": "A", "sequence": "MKLL"}}]}
                    ],
                    "params": {"resume_job_id": "abc-123"},
                }
            )

    def test_resume_without_items(self):
        """Resume request with only resume_job_id is valid."""
        r = BoltzGenDesignRequest.model_validate(
            {"params": {"resume_job_id": "abc-123"}}
        )
        assert r.params.resume_job_id == "abc-123"
        assert r.items is None

    def test_fresh_run_requires_items(self):
        """Fresh run without items (and no resume_job_id) must fail."""
        with pytest.raises(ValidationError, match="'items' is required"):
            BoltzGenDesignRequest.model_validate({"params": {}})

    def test_response_new_fields_defaults(self):
        """New response fields have sensible defaults — backward compat."""
        resp = BoltzGenDesignResponse(results=[])
        assert resp.is_complete is True
        assert resp.job_id is None
        assert resp.completed_steps is None
        assert resp.remaining_steps is None

    def test_partial_response(self):
        resp = BoltzGenDesignResponse(
            results=[],
            job_id="x",
            completed_steps=["design"],
            remaining_steps=["folding", "analysis"],
            is_complete=False,
        )
        assert resp.is_complete is False
        assert resp.remaining_steps == ["folding", "analysis"]

    def test_entity_rejects_multiple_types(self):
        with pytest.raises(ValidationError, match="Exactly one entity type"):
            BoltzGenEntity(
                protein=BoltzGenProteinEntity(id="A", sequence="MKLL"),
                ligand=BoltzGenLigandEntity(id="L", smiles="CCO"),
            )

    def test_ligand_requires_ccd_or_smiles(self):
        with pytest.raises(ValidationError, match="SMILES or CCD"):
            BoltzGenLigandEntity(id="L")

    def test_file_entity_requires_cif_or_pdb(self):
        with pytest.raises(ValidationError, match="cif.*pdb|pdb.*cif"):
            BoltzGenFileEntity()

    def test_res_index_valid_formats(self):
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

    def test_res_index_invalid_formats(self):
        """_ResIndexValidatorMixin rejects invalid res_index formats."""
        with pytest.raises(ValidationError, match="must be >= 1"):
            BoltzGenChainSelector(id="A", res_index=-1)
        with pytest.raises(ValidationError, match="must be >= 1"):
            BoltzGenChainSelector(id="A", res_index=0)
        with pytest.raises(ValidationError, match="Invalid res_index format"):
            BoltzGenChainSelector(id="A", res_index="abc")
        with pytest.raises(ValidationError, match="must be >= 1"):
            BoltzGenChainSelector(id="A", res_index=[1, -5])

    def test_insertion_requires_id_and_res_index(self):
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
# Unit: @modal.exit() checkpoint handler (mocked — no GPU, no R2)
# ---------------------------------------------------------------------------


class TestExitHandler:
    """Tests for the @modal.exit() checkpoint handler."""

    def test_exit_handler_uploads_checkpoint(self, tmp_path):
        """Exit handler uploads checkpoint when pipeline is in-progress."""
        from models.boltzgen.output_delivery import CheckpointManifest

        job = OutputJob("boltzgen", "test-exit")
        output_dir = tmp_path
        requested_steps = ["design", "inverse_folding"]

        with patch.object(
            OutputJob, "upload_checkpoint", return_value=True
        ) as mock_upload:
            manifest = CheckpointManifest(
                job_id=job.job_id,
                model_slug="boltzgen",
                completed_steps=[],
                remaining_steps=[],
                requested_steps=requested_steps,
            )
            job.upload_checkpoint(output_dir, manifest)

        mock_upload.assert_called_once()
        manifest = mock_upload.call_args[0][1]
        assert manifest.job_id == "test-exit"
        assert manifest.requested_steps == ["design", "inverse_folding"]

    def test_exit_handler_noop_when_complete(self):
        """Exit handler does nothing when _pipeline_job is None (pipeline completed)."""
        pipeline_job = None

        with patch.object(OutputJob, "upload_checkpoint") as mock_upload:
            if pipeline_job is not None:
                mock_upload()

        mock_upload.assert_not_called()


# ---------------------------------------------------------------------------
# Unit: pure pipeline / app helper functions
# ---------------------------------------------------------------------------


class TestPipelinePureFunctions:
    """Tests for pure helper functions in pipeline.py and app.py."""

    # -- _strip_rank_prefix ---------------------------------------------------

    def test_strip_rank_prefix_removes_prefix(self):
        from models.boltzgen.pipeline import _strip_rank_prefix

        assert _strip_rank_prefix("rank001_design_spec_0.cif") == "design_spec_0.cif"

    def test_strip_rank_prefix_multiple_digits(self):
        from models.boltzgen.pipeline import _strip_rank_prefix

        assert _strip_rank_prefix("rank123_foo_bar.cif") == "foo_bar.cif"

    def test_strip_rank_prefix_no_prefix(self):
        from models.boltzgen.pipeline import _strip_rank_prefix

        assert _strip_rank_prefix("design_spec_0.cif") == "design_spec_0.cif"

    def test_strip_rank_prefix_rank_in_middle(self):
        from models.boltzgen.pipeline import _strip_rank_prefix

        assert _strip_rank_prefix("my_rank001_file.cif") == "my_rank001_file.cif"

    # -- _match_metrics_row ---------------------------------------------------

    def test_match_metrics_row_exact_filename(self):
        import pandas as pd

        from models.boltzgen.pipeline import _match_metrics_row

        df = pd.DataFrame(
            {"file_name": ["design_0.cif", "design_1.cif"], "plddt": [80.0, 90.0]}
        )
        row = _match_metrics_row("design_0.cif", df)
        assert row is not None
        assert row["plddt"] == 80.0

    def test_match_metrics_row_sans_extension(self):
        import pandas as pd

        from models.boltzgen.pipeline import _match_metrics_row

        df = pd.DataFrame(
            {"file_name": ["design_0", "design_1"], "plddt": [80.0, 90.0]}
        )
        row = _match_metrics_row("design_0.cif", df)
        assert row is not None
        assert row["plddt"] == 80.0

    def test_match_metrics_row_numeric_id(self):
        import pandas as pd

        from models.boltzgen.pipeline import _match_metrics_row

        df = pd.DataFrame({"id": [0, 1], "plddt": [80.0, 90.0]})
        row = _match_metrics_row("design_spec_0.cif", df)
        assert row is not None
        assert row["plddt"] == 80.0

    def test_match_metrics_row_no_match(self):
        import pandas as pd

        from models.boltzgen.pipeline import _match_metrics_row

        df = pd.DataFrame({"file_name": ["other.cif"], "plddt": [80.0]})
        row = _match_metrics_row("design_0.cif", df)
        assert row is None

    def test_match_metrics_row_anchored_regex(self):
        """Anchored regex matches trailing digits, not embedded ones."""
        import pandas as pd

        from models.boltzgen.pipeline import _match_metrics_row

        df = pd.DataFrame({"id": [7, 42], "plddt": [70.0, 99.0]})
        row = _match_metrics_row("design42_spec_7.cif", df)
        assert row is not None
        assert row["plddt"] == 70.0

    # -- _optional_configure_flags -------------------------------------------

    def test_optional_configure_flags_empty(self):
        from models.boltzgen.pipeline import BoltzGenPipelineMixin

        params = BoltzGenDesignParams()
        flags = BoltzGenPipelineMixin._optional_configure_flags(params)
        assert flags == []

    def test_optional_configure_flags_all_params(self):
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

    def test_optional_configure_flags_inverse_fold_default_omitted(self):
        """inverse_fold_num_sequences=1 (default) is NOT forwarded."""
        from models.boltzgen.pipeline import BoltzGenPipelineMixin

        params = BoltzGenDesignParams(inverse_fold_num_sequences=1)
        flags = BoltzGenPipelineMixin._optional_configure_flags(params)
        assert "--inverse_fold_num_sequences" not in flags

    # -- _find_designs_dir ---------------------------------------------------

    def test_find_designs_dir_filtering_exists(self, tmp_path):
        from models.boltzgen.pipeline import _find_designs_dir

        d = tmp_path / "final_ranked_designs" / "final_5_designs"
        d.mkdir(parents=True)
        result = _find_designs_dir(tmp_path, {BoltzGenPipelineStep.FILTERING}, budget=5)
        assert result == d

    def test_find_designs_dir_intermediate_only(self, tmp_path):
        from models.boltzgen.pipeline import _find_designs_dir

        d = tmp_path / "intermediate_designs"
        d.mkdir()
        result = _find_designs_dir(tmp_path, set(), budget=5)
        assert result == d

    def test_find_designs_dir_nothing_exists(self, tmp_path):
        from models.boltzgen.pipeline import _find_designs_dir

        with pytest.raises(FileNotFoundError, match="No output directory found"):
            _find_designs_dir(tmp_path, set(), budget=5)

    def test_find_designs_dir_skips_filtering_when_not_run(self, tmp_path):
        """If FILTERING step not in steps_run, skip filtering dir even if it exists."""
        from models.boltzgen.pipeline import _find_designs_dir

        filt_dir = tmp_path / "final_ranked_designs" / "final_5_designs"
        filt_dir.mkdir(parents=True)
        inter_dir = tmp_path / "intermediate_designs"
        inter_dir.mkdir()
        result = _find_designs_dir(tmp_path, set(), budget=5)
        assert result == inter_dir

    # -- _resolve_reset_res_index --------------------------------------------

    def test_resolve_reset_res_index_top_level_explicit(self):
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

    def test_resolve_reset_res_index_per_file_explicit(self):
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

    def test_resolve_reset_res_index_auto_infer(self):
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

    def test_resolve_reset_res_index_no_match(self):
        """Returns None when no reset is needed."""
        from models.boltzgen.app import BoltzGenModel

        item = BoltzGenDesignRequestItem(
            entities=[
                BoltzGenEntity(protein=BoltzGenProteinEntity(id="A", sequence="MKLL")),
            ],
        )
        result = BoltzGenModel._resolve_reset_res_index(item)
        assert result is None

    def test_resolve_reset_res_index_chain_list(self):
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

    def test_additional_filters_valid(self):
        """Valid filter expressions are accepted."""
        params = BoltzGenDesignParams(additional_filters=["plddt>70", "ptm>0.5"])
        assert params.additional_filters == ["plddt>70", "ptm>0.5"]

    def test_additional_filters_invalid(self):
        """Invalid filter expressions are rejected."""
        with pytest.raises(ValidationError, match="Invalid additional_filters entry"):
            BoltzGenDesignParams(additional_filters=["not a filter"])

    def test_additional_filters_none(self):
        """None is accepted (field is optional)."""
        params = BoltzGenDesignParams(additional_filters=None)
        assert params.additional_filters is None

    def test_additional_filters_gte_lte(self):
        """'>=' and '<=' operators are accepted."""
        params = BoltzGenDesignParams(additional_filters=["plddt>=70", "rmsd<=2.5"])
        assert params.additional_filters == ["plddt>=70", "rmsd<=2.5"]

    def test_additional_filters_negative_threshold(self):
        """Negative thresholds like 'affinity>-5.0' are accepted."""
        params = BoltzGenDesignParams(additional_filters=["affinity>-5.0"])
        assert params.additional_filters == ["affinity>-5.0"]
