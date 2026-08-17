import logging
from uuid import UUID, uuid4

from app.persistence.models import Receipt, ReceiptStatus
from app.repositories.receipt_repository import ReceiptRepository
from app.storage.errors import ObjectNotFoundError
from app.storage.keys import generate_receipt_object_key
from app.storage.protocol import ReceiptImageStorage
from app.storage.validator import ReceiptImageValidator

from .errors import PersistenceFailure, ReceiptDeleteFailure

logger = logging.getLogger(__name__)


class ReceiptService:
    def __init__(
        self,
        *,
        validator: ReceiptImageValidator,
        storage: ReceiptImageStorage,
        repository: ReceiptRepository,
    ) -> None:
        self._validator = validator
        self._storage = storage
        self._repository = repository

    def create_receipt_from_image(
        self,
        *,
        user_id: str,
        original_filename: str,
        image_bytes: bytes,
    ) -> Receipt:
        validated = self._validator.validate(image_bytes)
        receipt_id = uuid4()
        storage_key = generate_receipt_object_key(validated.format, receipt_id)

        self._storage.put(storage_key, validated.data, validated.content_type)

        receipt = Receipt(
            receipt_id=receipt_id,
            user_id=user_id,
            original_filename=original_filename,
            storage_key=storage_key,
            content_type=validated.content_type,
            image_width_px=validated.width_px,
            image_height_px=validated.height_px,
            status=ReceiptStatus.UPLOADED,
        )

        try:
            return self._repository.create(receipt)
        except Exception as db_exc:
            try:
                self._storage.delete(storage_key)
            except Exception as cleanup_exc:
                logger.error(
                    "Receipt persistence failed and storage cleanup also failed",
                    extra={
                        "receipt_id": str(receipt_id),
                        "operation": "create_receipt_cleanup",
                        "error_category": type(cleanup_exc).__name__,
                    },
                    exc_info=cleanup_exc,
                )
                raise PersistenceFailure(
                    "Receipt persistence failed; storage cleanup also failed"
                ) from db_exc

            if isinstance(db_exc, PersistenceFailure):
                raise
            raise PersistenceFailure("Could not persist receipt metadata") from db_exc

    def get_receipt(self, receipt_id: UUID) -> Receipt | None:
        return self._repository.get_by_id(receipt_id)

    def delete_receipt(self, receipt_id: UUID) -> bool:
        receipt = self._repository.get_by_id(receipt_id)
        if receipt is None:
            return False

        try:
            self._storage.delete(receipt.storage_key)
        except ObjectNotFoundError:
            logger.warning(
                "Receipt image was already absent during delete",
                extra={
                    "receipt_id": str(receipt_id),
                    "operation": "delete_receipt",
                    "error_category": "ObjectNotFoundError",
                },
            )
        except Exception as exc:
            raise ReceiptDeleteFailure("Could not delete stored receipt image") from exc

        try:
            deleted = self._repository.delete(receipt_id)
        except Exception as exc:
            logger.error(
                "Receipt image deleted but metadata deletion failed",
                extra={
                    "receipt_id": str(receipt_id),
                    "operation": "delete_receipt",
                    "error_category": type(exc).__name__,
                },
                exc_info=exc,
            )
            raise ReceiptDeleteFailure(
                "Stored image was deleted but receipt metadata deletion failed"
            ) from exc

        if not deleted:
            raise ReceiptDeleteFailure("Receipt disappeared during metadata deletion")
        return True
