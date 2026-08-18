from uuid import UUID

from backend.app.domain.errors import (
    PersistenceFailure,
    ReceiptNotFound,
)
from backend.app.domain.read_models import (
    ReceiptDetail,
    ReceiptPage,
)
from backend.app.repositories.read_protocols import (
    ReceiptListQuery,
    ReceiptReadRepository,
)


class ReceiptQueryService:
    def __init__(
        self,
        *,
        repository: ReceiptReadRepository,
    ) -> None:
        self._repository = repository

    async def list_receipts(
        self,
        query: ReceiptListQuery,
    ) -> ReceiptPage:
        try:
            return await self._repository.list_page(query)
        except PersistenceFailure:
            raise
        except Exception as error:
            raise PersistenceFailure(
                "Receipt list query failed."
            ) from error

    async def get_receipt(
        self,
        *,
        receipt_id: UUID,
    ) -> ReceiptDetail:
        try:
            detail = await self._repository.get_detail(
                receipt_id
            )
        except PersistenceFailure:
            raise
        except Exception as error:
            raise PersistenceFailure(
                "Receipt detail query failed."
            ) from error

        if detail is None:
            raise ReceiptNotFound(
                f"Receipt {receipt_id} was not found."
            )

        return detail