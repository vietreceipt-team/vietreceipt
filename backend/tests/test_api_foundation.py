from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from backend.app.api.dependencies import (
    get_receipt_service,
)
from backend.app.api.schemas import (
    ApplyFieldCorrectionRequest,
    ClearFieldCorrectionRequest,
    FieldCorrectionRequest,
    VerifyReceiptRequest,
)
from backend.app.domain.errors import ReceiptNotFound
from backend.app.main import create_app


EXPECTED_UPDATED_AT = datetime(
    2026, 8, 14, 9, 0, tzinfo=timezone.utc
)


def test_apply_request_uses_discriminated_union() -> None:
    adapter = TypeAdapter(FieldCorrectionRequest)

    request = adapter.validate_python(
        {
            "operation": "APPLY",
            "value": 325000,
            "value_status": "PRESENT",
            "expected_updated_at": (
                EXPECTED_UPDATED_AT.isoformat()
            ),
        }
    )

    assert isinstance(
        request,
        ApplyFieldCorrectionRequest,
    )
    assert request.value == 325000


def test_clear_request_rejects_value_payload() -> None:
    with pytest.raises(ValidationError):
        ClearFieldCorrectionRequest.model_validate(
            {
                "operation": "CLEAR",
                "value": 325000,
                "expected_updated_at": (
                    EXPECTED_UPDATED_AT.isoformat()
                ),
            }
        )


def test_concurrency_token_requires_timezone() -> None:
    with pytest.raises(ValidationError):
        VerifyReceiptRequest(
            expected_updated_at=datetime(
                2026,
                8,
                14,
                9,
                0,
            )
        )


def test_domain_error_uses_canonical_error_envelope() -> None:
    app = create_app()

    @app.get("/test/not-found")
    async def raise_not_found() -> None:
        raise ReceiptNotFound(
            "Receipt was not found."
        )

    client = TestClient(app)
    response = client.get("/test/not-found")

    assert response.status_code == 404

    body = response.json()
    assert body["error"]["code"] == "RECEIPT_NOT_FOUND"
    assert body["error"]["message"] == (
        "Receipt was not found."
    )

    request_id = UUID(body["error"]["request_id"])
    assert response.headers["X-Request-ID"] == str(
        request_id
    )


def test_unconfigured_services_return_typed_503() -> None:
    app = create_app()

    @app.get("/test/services")
    async def require_services(
        service=Depends(get_receipt_service),
    ) -> dict[str, bool]:
        return {"configured": service is not None}

    client = TestClient(app)
    response = client.get("/test/services")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == (
        "APPLICATION_SERVICES_UNAVAILABLE"
    )


def test_request_validation_uses_canonical_error_envelope() -> None:
    app = create_app()

    @app.get("/test/receipts/{receipt_id}")
    async def validate_receipt_id(
        receipt_id: UUID,
    ) -> dict[str, str]:
        return {"receipt_id": str(receipt_id)}

    client = TestClient(app)
    response = client.get(
        "/test/receipts/not-a-uuid"
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == (
        "REQUEST_VALIDATION_ERROR"
    )
    assert "errors" in body["error"]["details"]