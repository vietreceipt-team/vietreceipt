from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.domain.enums import ReceiptStatus
from backend.app.domain.errors import PersistenceFailure
from backend.app.domain.models import Receipt
from backend.app.ports.clock import Clock
from backend.app.ports.ids import IdGenerator
from backend.app.ports.persistence import ReceiptUpload
from backend.app.storage.errors import ObjectNotFoundError
from backend.app.storage.keys import generate_receipt_object_key
from backend.app.storage.protocol import ReceiptImageStorage
from backend.app.storage.validator import ReceiptImageValidator

from .sqlalchemy_receipt_repository import SQLAlchemyReceiptRepository

logger = logging.getLogger(__name__)


class SQLAlchemyReceiptPersistenceService:
    """Concrete Backend-2 implementation of ReceiptPersistenceService."""

    def __init__(
        self,
        *,
        validator: ReceiptImageValidator,
        storage: ReceiptImageStorage,
        session_factory: sessionmaker[Session],
        id_generator: IdGenerator,
        clock: Clock,
    ) -> None:
        self._validator = validator
        self._storage = storage
        self._session_factory = session_factory
        self._id_generator = id_generator
        self._clock = clock

    async def persist_upload(self, upload: ReceiptUpload) -> Receipt:
        raw_bytes = upload.file.read()
        validated = self._validator.validate(raw_bytes)

        receipt_id = self._id_generator.new_id()
        storage_key = generate_receipt_object_key(validated.format, receipt_id)

        self._storage.put(storage_key, validated.data, validated.content_type)

        now = self._clock.now()
        receipt = Receipt(
            receipt_id=receipt_id,
            original_filename=upload.filename,
            status=ReceiptStatus.UPLOADED,
            processing_stage=None,
            image_width_px=validated.width_px,
            image_height_px=validated.height_px,
            latest_ocr_run_id=None,
            latest_kie_run_id=None,
            last_error=None,
            created_at=now,
            updated_at=now,
            review_started_at=None,
            processed_at=None,
            verified_at=None,
        )

        session = self._session_factory()
        repository = SQLAlchemyReceiptRepository(session)
        try:
            persisted = await repository.create_with_storage(
                receipt,
                storage_key=storage_key,
                content_type=validated.content_type,
            )
            session.commit()
            return persisted
        except Exception as db_exc:
            session.rollback()
            try:
                self._storage.delete(storage_key)
            except Exception as cleanup_exc:
                logger.error(
                    "Receipt DB persistence failed and storage cleanup failed",
                    extra={
                        "receipt_id": str(receipt_id),
                        "operation": "persist_upload_cleanup",
                        "error_category": type(cleanup_exc).__name__,
                    },
                    exc_info=cleanup_exc,
                )
                raise PersistenceFailure(
                    "Receipt persistence failed; storage cleanup also failed."
                ) from db_exc

            if isinstance(db_exc, PersistenceFailure):
                raise
            raise PersistenceFailure("Receipt persistence failed.") from db_exc
        finally:
            session.close()

    async def delete_receipt(self, receipt_id: UUID) -> bool:
        """Internal delete foundation; public API semantics stay outside this adapter."""
        session = self._session_factory()
        repository = SQLAlchemyReceiptRepository(session)
        try:
            metadata = await repository.get_storage_metadata(receipt_id)
            if metadata is None:
                return False

            storage_key, _content_type = metadata
            try:
                self._storage.delete(storage_key)
            except ObjectNotFoundError:
                logger.warning(
                    "Receipt image was already absent during delete",
                    extra={
                        "receipt_id": str(receipt_id),
                        "operation": "delete_receipt",
                        "error_category": "ObjectNotFoundError",
                    },
                )

            deleted = await repository.delete(receipt_id)
            if not deleted:
                session.rollback()
                return False
            try:
                session.commit()
            except SQLAlchemyError as exc:
                session.rollback()
                logger.error(
                    "Receipt delete database failure after storage deletion",
                    extra={
                        "receipt_id": str(receipt_id),
                        "operation": "delete_receipt",
                        "error_category": type(exc).__name__,
                        "consistency_state": "storage_deleted_db_not_confirmed",
                    },
                    exc_info=exc,
                )
                raise PersistenceFailure("Receipt deletion failed.") from exc
            return True
        except PersistenceFailure:
            session.rollback()
            raise
        except SQLAlchemyError as exc:
            session.rollback()
            logger.error(
                "Receipt delete database failure",
                extra={
                    "receipt_id": str(receipt_id),
                    "operation": "delete_receipt",
                    "error_category": type(exc).__name__,
                },
                exc_info=exc,
            )
            raise PersistenceFailure("Receipt deletion failed.") from exc
        finally:
            session.close()
