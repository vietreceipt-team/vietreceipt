from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
)
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
)

from backend.app.domain.enums import ValueStatus


FieldValueInput = StrictStr | StrictInt | None


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApplyFieldCorrectionRequest(APIModel):
    operation: Literal["APPLY"]
    value: FieldValueInput
    value_status: ValueStatus
    expected_updated_at: AwareDatetime


class ClearFieldCorrectionRequest(APIModel):
    operation: Literal["CLEAR"]
    expected_updated_at: AwareDatetime


FieldCorrectionRequest = Annotated[
    ApplyFieldCorrectionRequest
    | ClearFieldCorrectionRequest,
    Field(discriminator="operation"),
]


class VerifyReceiptRequest(APIModel):
    expected_updated_at: AwareDatetime


class RetryAcceptedResponse(APIModel):
    receipt_id: UUID
    retry_accepted: Literal[True] = True


class ErrorBody(APIModel):
    code: str
    message: str
    details: dict[str, Any] | None = None
    request_id: UUID


class ErrorResponse(APIModel):
    error: ErrorBody