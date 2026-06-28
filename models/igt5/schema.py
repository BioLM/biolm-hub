from functools import partial
from typing import Annotated, Optional

from pydantic import (
    AliasChoices,
    BeforeValidator,
    ConfigDict,
    Field,
    PrivateAttr,
    model_validator,
)

from models.commons.data.validator import validate_aa_extended
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### IgT5 Params


class IgT5Params(ModelParams):
    params_version = "v1"
    display_name = "IgT5"
    base_model_slug = "igt5"
    log_identifier = "IgT5"
    batch_size = 8
    max_sequence_len = 256
    max_unpaired_sequence_len = 512


class IgT5ModelTypes(EnhancedStringEnum):
    PAIRED = "paired"
    UNPAIRED = "unpaired"


### IgT5 Request


class IgT5EncodeIncludeOptions(EnhancedStringEnum):
    MEAN = "mean"  # mean embedding (default)
    RESIDUE = "residue"  # per-residue embeddings
    # LOGITS = "logits"  # predicted per-residue logits
    # ATTENTIONS = "attentions"  # self-attention weights


class IgT5EncodeRequestParams(RequestModel):
    include: list[IgT5EncodeIncludeOptions] = Field(
        default_factory=partial(list, [IgT5EncodeIncludeOptions.MEAN])
    )


class IgT5EncodeRequestItem(RequestModel):
    # Canonical antibody field names; old `heavy`/`light` accepted via alias.
    model_config = ConfigDict(populate_by_name=True)

    heavy_chain: Optional[
        Annotated[
            str,
            BeforeValidator(validate_aa_extended),
            Field(
                None,
                min_length=1,
                max_length=IgT5Params.max_sequence_len,
                validation_alias=AliasChoices("heavy_chain", "heavy"),
            ),
        ]
    ] = None

    light_chain: Optional[
        Annotated[
            str,
            BeforeValidator(validate_aa_extended),
            Field(
                None,
                min_length=1,
                max_length=IgT5Params.max_sequence_len,
                validation_alias=AliasChoices("light_chain", "light"),
            ),
        ]
    ] = None

    sequence: Optional[
        Annotated[
            str,
            BeforeValidator(validate_aa_extended),
            Field(None, min_length=1, max_length=IgT5Params.max_unpaired_sequence_len),
        ]
    ] = None

    # Private attribute to store the inferred "kind"
    _kind: Optional[str] = PrivateAttr()

    @model_validator(mode="after")
    def validate_and_infer_type(cls, instance):
        """
        Infer request type and ensure valid field combos:
          - If `heavy` and `light` => "paired"
          - If `sequence` => "unpaired"
          - Otherwise => error.
        """
        from models.igt5.config import IgT5ModelTypes

        heavy, light, sequence = (
            instance.heavy_chain,
            instance.light_chain,
            instance.sequence,
        )

        if sequence and (heavy or light):
            raise ValueError(
                "Cannot provide both `sequence` and (`heavy_chain`, `light_chain`). "
                "Pick one."
            )

        if heavy and light:
            instance._kind = IgT5ModelTypes.PAIRED
        elif sequence:
            instance._kind = IgT5ModelTypes.UNPAIRED
        else:
            raise ValueError(
                "Must provide either (`heavy_chain`, `light_chain`) OR `sequence`, "
                "but not both."
            )

        return instance

    @property
    def kind(self) -> str:
        return self._kind


class IgT5EncodeRequest(RequestModel):
    params: IgT5EncodeRequestParams = Field(default_factory=IgT5EncodeRequestParams)
    items: list[IgT5EncodeRequestItem] = Field(
        min_length=1, max_length=IgT5Params.batch_size
    )


### IgT5 Response


class IgT5EncodeResponseResult(ResponseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        exclude_unset=True,
        exclude_none=True,
    )

    embeddings: Optional[list[float]] = None
    residue_embeddings: Optional[list[list[float]]] = None
    # attentions: Optional[list[list[float]]] = None
    # logits: Optional[list[list[float]]] = None


class IgT5EncodeResponse(ResponseModel):
    results: list[IgT5EncodeResponseResult]
