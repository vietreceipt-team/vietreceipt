import inspect
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID

from fastapi.testclient import TestClient

import backend.app.api.router as router_module
from backend.app.api.dependencies import (
    SYSTEM_ACTOR_ID,
    ServiceRegistry,
)
from backend.app.domain.enums import (
    CorrectionOperation,
    FieldName,
    ReceiptStatus,
    ValueStatus,
)
from backend.app.domain.models import (
    CorrectionHistory,
    ExtractedField,
    Receipt,
)
from backend.app.domain.read_models import (
    ReceiptDetail,
    ReceiptPage,
    ReceiptSummary,
)
from backend.app.main import create_app
from backend.app.ports.persistence import ReceiptUpload


RECEIPT_ID = UUID("00000000-0000-4000-8000-000000000401")
OCR_RUN_ID = UUID("00000000-0000-4000-8000-000000000402")
KIE_RUN_ID = UUID("00000000-0000-4000-8000-000000000403")
CORRECTION_ID = UUID(
    "00000000-0000-4000-8000-000000000404"
)

NOW = datetime(
    2026, 8, 14, 10, 0, tzinfo=timezone.utc
)


def make_receipt(
    status: ReceiptStatus = ReceiptStatus.UPLOADED,
) -> Receipt:
    return Receipt(
        receipt_id=RECEIPT_ID,
        original_filename="receipt.jpg",
        status=status,
        image_width_px=1000,
        image_height_px=1500,
        latest_ocr_run_id=OCR_RUN_ID,
        latest_kie_run_id=KIE_RUN_ID,
        created_at=NOW,
        updated_at=NOW,
        verified_at=(
            NOW
            if status is ReceiptStatus.VERIFIED
            else None
        ),
    )


def make_field(
    field_name: FieldName,
) -> ExtractedField:
    values: dict[FieldName, str | int] = {
        FieldName.MERCHANT_NAME: "VietReceipt Store",
        FieldName.RECEIPT_DATE: "2026-08-14",
        FieldName.TOTAL_AMOUNT: 325000,
        FieldName.INVOICE_ID: "INV-001",
        FieldName.MERCHANT_ADDRESS: "Ha Noi",
    }
    value = values[field_name]

    return ExtractedField(
        receipt_id=RECEIPT_ID,
        field_name=field_name,
        ocr_run_id=OCR_RUN_ID,
        kie_run_id=KIE_RUN_ID,
        raw_text=str(value),
        predicted_value=str(value),
        normalized_value=value,
        normalization=None,
        value_status=ValueStatus.PRESENT,
        corrected_value=None,
        corrected_status=None,
        has_correction=False,
        effective_value=value,
        effective_status=ValueStatus.PRESENT,
        confidence=0.99,
        machine_needs_review=False,
        effective_needs_review=False,
        review_reasons=(),
        review_policy_version=None,
        source_block_ids=(
            f"block_{field_name.value}",
        ),
        verified=False,
        updated_at=NOW,
    )


def make_fields() -> list[ExtractedField]:
    return [
        make_field(field_name)
        for field_name in FieldName
    ]


def make_detail(
    status: ReceiptStatus = ReceiptStatus.UPLOADED,
    *,
    include_fields: bool = False,
) -> ReceiptDetail:
    fields = (
        {
            field.field_name: field
            for field in make_fields()
        }
        if include_fields
        else {}
    )

    return ReceiptDetail(
        receipt_id=RECEIPT_ID,
        original_filename="receipt.jpg",
        status=status,
        image_width_px=1000,
        image_height_px=1500,
        latest_ocr_run_id=OCR_RUN_ID,
        latest_kie_run_id=KIE_RUN_ID,
        fields=fields,
        ocr_blocks=(),
        created_at=NOW,
        updated_at=NOW,
        verified_at=(
            NOW
            if status is ReceiptStatus.VERIFIED
            else None
        ),
    )


def make_page() -> ReceiptPage:
    return ReceiptPage(
        items=(
            ReceiptSummary(
                receipt_id=RECEIPT_ID,
                original_filename="receipt.jpg",
                status=ReceiptStatus.NEEDS_REVIEW,
                merchant_name="VietReceipt Store",
                receipt_date=date(2026, 8, 14),
                total_amount=325000,
                created_at=NOW,
            ),
        ),
        page=1,
        page_size=20,
        total_items=1,
        total_pages=1,
    )


def make_history() -> list[CorrectionHistory]:
    return [
        CorrectionHistory(
            correction_id=CORRECTION_ID,
            receipt_id=RECEIPT_ID,
            field_name=FieldName.TOTAL_AMOUNT,
            operation=CorrectionOperation.APPLY,
            kie_run_id=KIE_RUN_ID,
            old_value=325000,
            new_value=330000,
            old_status=ValueStatus.PRESENT,
            new_status=ValueStatus.PRESENT,
            changed_by=SYSTEM_ACTOR_ID,
            changed_at=NOW,
        )
    ]


class ServiceDoubles:
    def __init__(self) -> None:
        self.receipts = SimpleNamespace(
            upload_receipt=AsyncMock(
                return_value=make_receipt()
            ),
            retry_receipt=AsyncMock(
                return_value=RECEIPT_ID
            ),
        )
        self.receipt_queries = SimpleNamespace(
            list_receipts=AsyncMock(
                return_value=make_page()
            ),
            get_receipt=AsyncMock(
                return_value=make_detail()
            ),
        )
        self.corrections = SimpleNamespace(
            update_correction=AsyncMock(
                return_value=make_field(
                    FieldName.TOTAL_AMOUNT
                )
            )
        )
        self.verification = SimpleNamespace(
            get_fields=AsyncMock(
                return_value=make_fields()
            ),
            verify_receipt=AsyncMock(
                return_value=make_receipt(
                    ReceiptStatus.VERIFIED
                )
            ),
        )
        self.history = SimpleNamespace(
            get_correction_history=AsyncMock(
                return_value=make_history()
            )
        )

    def registry(self) -> ServiceRegistry:
        return ServiceRegistry(
            receipts=cast(Any, self.receipts),
            receipt_queries=cast(
                Any,
                self.receipt_queries,
            ),
            corrections=cast(Any, self.corrections),
            verification=cast(
                Any,
                self.verification,
            ),
            history=cast(Any, self.history),
        )


def make_client() -> tuple[TestClient, ServiceDoubles]:
    doubles = ServiceDoubles()
    app = create_app(
        service_registry=doubles.registry()
    )
    return TestClient(app), doubles


def test_openapi_contains_eight_required_operations() -> None:
    client, _ = make_client()
    document = client.get("/openapi.json").json()

    operation_ids = {
        operation["operationId"]
        for path_item in document["paths"].values()
        for method, operation in path_item.items()
        if method in {
            "get",
            "post",
            "patch",
            "put",
            "delete",
        }
    }

    assert {
        "uploadReceipt",
        "listReceipts",
        "getReceipt",
        "retryReceipt",
        "getReceiptFields",
        "updateFieldCorrection",
        "verifyReceipt",
        "getReceiptHistory",
    }.issubset(operation_ids)


def test_core_receipt_routes_call_services() -> None:
    client, doubles = make_client()

    upload_response = client.post(
        "/api/v1/receipts",
        files={
            "file": (
                "receipt.jpg",
                b"fake-image",
                "image/jpeg",
            )
        },
    )
    assert upload_response.status_code == 201
    assert upload_response.json()["status"] == "UPLOADED"

    upload = (
        doubles.receipts.upload_receipt.await_args.args[0]
    )
    assert isinstance(upload, ReceiptUpload)
    assert upload.filename == "receipt.jpg"

    list_response = client.get(
        "/api/v1/receipts",
        params={
            "status": "NEEDS_REVIEW",
            "merchant_name": "VietReceipt",
            "date_from": "2026-08-01",
            "date_to": "2026-08-31",
        },
    )
    assert list_response.status_code == 200
    assert list_response.json()["total_items"] == 1

    query = (
        doubles.receipt_queries
        .list_receipts
        .await_args
        .args[0]
    )
    assert query.status is ReceiptStatus.NEEDS_REVIEW
    assert query.merchant_name == "VietReceipt"

    detail_response = client.get(
        f"/api/v1/receipts/{RECEIPT_ID}"
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["fields"] == {}

    retry_response = client.post(
        f"/api/v1/receipts/{RECEIPT_ID}/retry"
    )
    assert retry_response.status_code == 202
    assert retry_response.json() == {
        "receipt_id": str(RECEIPT_ID),
        "retry_accepted": True,
    }


def test_hitl_routes_call_application_services() -> None:
    client, doubles = make_client()

    fields_response = client.get(
        f"/api/v1/receipts/{RECEIPT_ID}/fields",
        params={"kie_run_id": str(KIE_RUN_ID)},
    )
    assert fields_response.status_code == 200
    assert set(fields_response.json()) == {
        field_name.value
        for field_name in FieldName
    }

    doubles.verification.get_fields.assert_awaited_once_with(
        receipt_id=RECEIPT_ID,
        kie_run_id=KIE_RUN_ID,
        actor_id=SYSTEM_ACTOR_ID,
    )

    apply_response = client.patch(
        (
            f"/api/v1/receipts/{RECEIPT_ID}/fields/"
            "total_amount/correction"
        ),
        json={
            "operation": "APPLY",
            "value": 330000,
            "value_status": "PRESENT",
            "expected_updated_at": NOW.isoformat(),
        },
    )
    assert apply_response.status_code == 200
    assert apply_response.json()["field_name"] == (
        "total_amount"
    )

    clear_response = client.patch(
        (
            f"/api/v1/receipts/{RECEIPT_ID}/fields/"
            "total_amount/correction"
        ),
        json={
            "operation": "CLEAR",
            "expected_updated_at": NOW.isoformat(),
        },
    )
    assert clear_response.status_code == 200

    correction_calls = (
        doubles.corrections
        .update_correction
        .await_args_list
    )
    assert len(correction_calls) == 2

    assert correction_calls[0].kwargs["operation"] is (
        CorrectionOperation.APPLY
    )
    assert correction_calls[0].kwargs["value"] == 330000
    assert correction_calls[1].kwargs["operation"] is (
        CorrectionOperation.CLEAR
    )
    assert correction_calls[1].kwargs["value"] is None

    doubles.receipt_queries.get_receipt.return_value = (
        make_detail(
            ReceiptStatus.VERIFIED,
            include_fields=True,
        )
    )

    verify_response = client.post(
        f"/api/v1/receipts/{RECEIPT_ID}/verify",
        json={
            "expected_updated_at": NOW.isoformat()
        },
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["status"] == "VERIFIED"

    doubles.verification.verify_receipt.assert_awaited_once_with(
        receipt_id=RECEIPT_ID,
        expected_updated_at=NOW,
        actor_id=SYSTEM_ACTOR_ID,
    )

    history_response = client.get(
        f"/api/v1/receipts/{RECEIPT_ID}/history"
    )
    assert history_response.status_code == 200
    assert history_response.json()[0]["operation"] == (
        "APPLY"
    )


def test_router_does_not_import_infrastructure_sdks() -> None:
    source = inspect.getsource(router_module).lower()

    for forbidden_reference in (
        "sqlalchemy",
        "boto3",
        "celery",
        "minio",
        "unit_of_work",
        "session.execute",
    ):
        assert forbidden_reference not in source