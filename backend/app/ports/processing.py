from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class ReceiptImageLoader(Protocol):
    async def load(self, receipt_id: UUID) -> bytes:
        ...


@runtime_checkable
class OCRProvider(Protocol):
    def __call__(
        self,
        image: bytes,
        *,
        receipt_id: UUID,
        ocr_run_id: UUID,
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class KIEProvider(Protocol):
    def __call__(
        self,
        ocr_result: dict[str, Any],
        *,
        kie_run_id: UUID,
    ) -> dict[str, Any]:
        ...
