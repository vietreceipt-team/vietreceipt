from fastapi.testclient import TestClient

from backend.app.api.router import API_PREFIX, api_router
from backend.app.main import create_app


def test_api_router_uses_canonical_prefix() -> None:
    assert API_PREFIX == "/api/v1"
    assert api_router.prefix == "/api/v1"


def test_openapi_document_is_available() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "VietReceipt API"
    assert response.json()["info"]["version"] == "1.0.0"