import hashlib
import logging

import modal

from models.commons.core.decorator import modal_endpoint
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
    .pip_install(common_requirements)
    .pip_install("sadie-antibody==1.0.6")
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
    def load_model(self):
        from sadie.renumbering import Renumbering

        self.Renumbering = Renumbering

    @modal.enter(snap=False)
    def setup_model(self):
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
                    seq=seq,
                    scheme=scheme,
                    region=region,
                    scfv=scfv,
                    allowed_chain=allowed_chain,
                )
                for seq in sequences
            ]
        except Exception as e:
            logging.error(f"SADIE call failed with error [{e}]")
            raise e

        return SADIEPredictResponse(results=results)

    def _compute_sadie(
        self,
        seq: str,
        scheme: SADIENumbering,
        region: SADIERegion,
        scfv: bool,
        allowed_chain: list[str],
    ) -> SADIEPredictResponseResult:
        renumbering_api = self.Renumbering(
            scheme=scheme,
            region_assign=region,
            run_multiproc=True,
            scfv=scfv,
            allowed_chain=allowed_chain,
        )
        seq_id = hashlib.sha256(seq.encode()).hexdigest()
        try:
            r = renumbering_api.run_single(seq_id=seq_id, seq=seq).to_dict(
                orient="records"
            )[0]
            r["e_value"] = r["e-value"]
        except Exception as e:
            raise ValueError(f"Error processing sequence {seq}: {e}") from e

        return SADIEPredictResponseResult(**r)


if __name__ == "__main__":
    """
    Usage:
        python models/sadie/app.py

        # Force deploy to "qa" or "main" environment:
        python models/sadie/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        SADIEModel,
        description=f"Run and optionally deploy the {SADIEParams.display_name} Modal app.",
    )
