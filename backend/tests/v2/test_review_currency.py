import json

import pytest
from fastapi.testclient import TestClient
from test_workflow import kie, process

from backend.app.main import create_app
from backend.app.v2.errors import V2Error
from backend.app.v2.models import Cell, Invoice

MONEY_CELLS = (
    ("header", "", "subtotal"),
    ("header", "", "tax_amount"),
    ("header", "", "total_amount"),
    ("line", "line-1", "unit_price"),
    ("line", "line-1", "amount"),
    ("tax", "0", "taxable_amount"),
    ("tax", "0", "tax_amount"),
)


def usd_kie(evidence, **kwargs):
    result = kie(evidence, **kwargs)
    result["fields"]["currency"]["normalized_value"] = "USD"
    return result


@pytest.mark.parametrize("section,row,field", MONEY_CELLS)
def test_currency_edit_rechecks_all_effective_money_and_rolls_back(
    svc, section, row, field
):
    detail = process(svc, provider=usd_kie)
    rid = detail["receipt_id"]
    detail = svc.correct(rid, section, row, field, 349.25, "PRESENT", detail["version"])
    client = TestClient(create_app(v2_service=svc))
    original_machine = client.get(f"/api/v2/receipts/{rid}/machine-results").json()
    original_history = svc.history(rid)
    response = client.patch(
        f"/api/v2/receipts/{rid}/fields/currency/correction",
        json={
            "value": "VND",
            "status": "PRESENT",
            "expected_version": detail["version"],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_VALUE"
    assert f"{section}.{field}" in response.json()["error"]["message"]
    assert svc.detail(rid) == detail
    assert svc.history(rid) == original_history
    assert (
        client.get(f"/api/v2/receipts/{rid}/machine-results").json() == original_machine
    )
    svc.verify(rid, detail["version"])
    assert json.loads(svc.export(rid, "json")[0])["header"]["currency"] == "USD"


@pytest.mark.parametrize(
    "status", ["UNKNOWN", "NOT_PRESENT", "UNREADABLE", "AMBIGUOUS"]
)
def test_currency_change_preserves_nonpresent_money_statuses(svc, status):
    detail = process(svc, provider=usd_kie)
    rid = detail["receipt_id"]
    for section, row, field in MONEY_CELLS:
        detail = svc.correct(rid, section, row, field, None, status, detail["version"])
    detail = svc.correct(
        rid, "header", "", "currency", "VND", "PRESENT", detail["version"]
    )
    svc.verify(rid, detail["version"])
    payload = json.loads(svc.export(rid, "json")[0])
    assert payload["header"]["total_amount"] is None
    assert payload["line_items"][0]["amount"] is None
    assert payload["tax_breakdown"][0]["tax_amount"] is None
    assert payload["value_statuses"]["header"]["total_amount"] == status
    assert payload["value_statuses"]["line_items"][0]["amount"] == status
    assert payload["value_statuses"]["tax_breakdown"][0]["tax_amount"] == status


def test_integer_money_allows_currency_change_and_export(svc):
    detail = process(svc, provider=usd_kie)
    rid = detail["receipt_id"]
    detail = svc.correct(
        rid, "header", "", "currency", "VND", "PRESENT", detail["version"]
    )
    svc.verify(rid, detail["version"])
    payload = json.loads(svc.export(rid, "json")[0])
    assert payload["header"]["currency"] == "VND"
    assert payload["header"]["total_amount"] == 100


def test_machine_usd_cents_require_review_but_corrected_integer_allows_vnd(svc):
    def machine_cents(evidence, **kwargs):
        result = usd_kie(evidence, **kwargs)
        result["fields"]["total_amount"]["normalized_value"] = 349.25
        return result

    detail = process(svc, provider=machine_cents)
    rid = detail["receipt_id"]
    with pytest.raises(V2Error, match="header.total_amount"):
        svc.correct(rid, "header", "", "currency", "VND", "PRESENT", detail["version"])
    detail = svc.correct(
        rid, "header", "", "total_amount", 349, "PRESENT", detail["version"]
    )
    detail = svc.correct(
        rid, "header", "", "currency", "VND", "PRESENT", detail["version"]
    )
    assert detail["fields"]["total_amount"]["normalized_value"] == 349.25
    svc.verify(rid, detail["version"])
    payload = json.loads(svc.export(rid, "json")[0])
    assert payload["header"]["currency"] == "VND"
    assert payload["header"]["total_amount"] == 349


@pytest.mark.parametrize("section,row,field", MONEY_CELLS)
def test_verification_and_all_exports_reject_legacy_incompatible_projection(
    svc, section, row, field
):
    detail = process(svc)
    rid = detail["receipt_id"]
    # Reproduce a projection persisted before cross-cell validation existed.
    with svc.sessions.begin() as session:
        cell = session.get(Cell, (rid, section, row, field))
        cell.correction = {"value": 349.25, "status": "PRESENT"}
        cell.reviewed = True
    with pytest.raises(V2Error, match=f"{section}.{field}") as error:
        svc.verify(rid, detail["version"])
    assert error.value.code == "INVALID_VALUE"
    assert svc.detail(rid)["version"] == detail["version"]
    assert svc.detail(rid)["status"] == "NEEDS_REVIEW"
    with svc.sessions.begin() as session:
        session.get(Invoice, rid).status = "VERIFIED"
    for fmt in ("json", "csv", "xlsx"):
        with pytest.raises(V2Error, match=f"{section}.{field}"):
            svc.export(rid, fmt)


def test_currency_cannot_be_cleared_while_effective_amounts_need_usd(svc):
    detail = process(svc, provider=usd_kie)
    rid = detail["receipt_id"]
    detail = svc.correct(
        rid, "header", "", "total_amount", 349.25, "PRESENT", detail["version"]
    )
    with pytest.raises(V2Error, match="header.total_amount"):
        svc.correct(rid, "header", "", "currency", None, "UNKNOWN", detail["version"])
    assert svc.detail(rid) == detail
