"""Production composition root for the currently concrete upload/processing path."""

from backend.app.api.dependencies import get_receipt_service
from backend.app.bootstrap import build_receipt_service
from backend.app.main import create_app


receipt_service = build_receipt_service()
app = create_app()
app.dependency_overrides[get_receipt_service] = lambda: receipt_service
