import hashlib

import modal

from models.commons.core.decorator import modal_endpoint
from models.commons.core.error import ValidationError400
from models.commons.core.logging import get_logger
from models.commons.modal.source import setup_source_layer
from models.commons.model.base import ModelMixinSnap
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
)
from models.sadie.config import MODEL_FAMILY
from models.sadie.schema import (
    SADIENumbering,
    SADIEParams,
    SADIEPredictRequest,
    SADIEPredictResponse,
    SADIEPredictResponseResult,
    SADIERegion,
)

logger = get_logger(__name__)

# Build Modal container image
image = (
    modal.Image.debian_slim(
        python_version="3.10"
    )  # sadie-antibody==1.0.6 requires Python <3.12
    .apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .uv_pip_install("sadie-antibody==1.0.6")
    # NOTE: pip downgrades biopython to 1.80 and pydantic to v1 per sadie's requirements.
    # sadie-antibody==1.0.6 is incompatible with pydantic v2 (uses validate_arguments).
    # schema.py must use @validator (v1 syntax), not @field_validator.
)
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)


# Define the app
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config()
logger.info("App name: %s", app_name)
app = modal.App(app_name, image=image)


@app.cls(
    image=image,
    secrets=[cloudflare_r2_secret],
    enable_memory_snapshot=True,
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class SADIEModel(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def load_model(self) -> None:
        # SADIE's HMMER aligner reads ``G3.species`` (a @property that issues an
        # HTTP GET to https://g3.jordanrwillis.com/api/v1) to decide, per
        # (species, chain), whether to build HMMs live from the remote G3 gene
        # database or fall back to the bundled local ANARCI numbering HMMs. That
        # G3 host has been decommissioned (the Heroku app behind its CNAME no
        # longer resolves), so the property raises and every predict fails with
        # a DNS NameResolutionError before any numbering happens.
        #
        # Patch ``G3.species`` to an empty list so the aligner's short-circuit
        # (``single_species not in self.g3.species``) is always True and SADIE
        # uses its packaged local numbering HMMs + local germline dict
        # (sadie/numbering/germlines.py) -- a fully offline, supported path that
        # needs no network. Germline assignment already uses the local dict, so
        # v_gene/j_gene/identity outputs are unaffected.
        from sadie.renumbering.clients.g3 import G3

        G3.species = property(lambda _self: [])

        from sadie.renumbering import Renumbering

        self.Renumbering = Renumbering

    @modal.enter(snap=False)
    def setup_model(self) -> None:
        logger.info(
            "%s model ready for inference from memory snapshot!",
            SADIEParams.display_name,
        )

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict(self, payload: SADIEPredictRequest) -> SADIEPredictResponse:
        """
        Performs feature generation using the SADIE package.

        Parameters:
        - payload (SADIEPredictRequest): The request object containing sequences and parameters.

        Returns:
        - SADIEPredictResponse: The response containing feature results.
        """

        sequences = [item.sequence for item in payload.items]
        scheme = payload.params.scheme
        region = payload.params.region_assign
        scfv = payload.params.scfv
        allowed_chain = payload.params.allowed_chain
        try:
            results = [
                self._compute_sadie(
                    idx=idx,
                    seq=seq,
                    scheme=scheme,
                    region=region,
                    scfv=scfv,
                    allowed_chain=allowed_chain,
                )
                for idx, seq in enumerate(sequences)
            ]
        except ValidationError400:
            raise
        except Exception:
            logger.error("SADIE call failed", exc_info=True)
            raise

        return SADIEPredictResponse(results=results)

    def _compute_sadie(
        self,
        idx: int,
        seq: str,
        scheme: SADIENumbering,
        region: SADIERegion,
        scfv: bool,
        allowed_chain: list[str],
    ) -> SADIEPredictResponseResult:
        renumbering_api = self.Renumbering(
            scheme=scheme,
            region_assign=region,
            run_multiproc=False,  # No multiprocessing benefit for single-sequence path
            scfv=scfv,
            allowed_chain=allowed_chain,
        )
        seq_id = hashlib.sha256(seq.encode()).hexdigest()
        result_rows = renumbering_api.run_single(seq_id=seq_id, seq=seq).to_dict(
            orient="records"
        )
        if not result_rows:
            raise ValidationError400(
                f"Could not annotate item {idx}: no antibody or TCR variable domain detected."
            )
        r = result_rows[0]
        r["e_value"] = r["e-value"]
        return SADIEPredictResponseResult(**r)


if __name__ == "__main__":
    """
    Usage:
        python models/sadie/app.py

        # Force deploy to "biolm-hub-dev" or "biolm-hub" environment:
        python models/sadie/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        SADIEModel,
        description=f"Run and optionally deploy the {SADIEParams.display_name} Modal app.",
    )
