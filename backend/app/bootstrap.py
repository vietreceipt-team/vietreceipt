from __future__ import annotations

from datetime import timedelta
import boto3
import os
from celery import Celery

from backend.app.domain.errors import PersistenceFailure
from backend.app.persistence import (
    SQLAlchemyReceiptPersistenceService,
    SQLAlchemyReceiptImageLoader,
    SQLAlchemyUnitOfWorkFactory,
    create_database_engine,
    create_session_factory,
)
from backend.app.adapters.celery_scheduler import CeleryProcessingScheduler
from backend.app.ports.clock import SystemClock
from backend.app.ports.ids import UUID4Generator
from backend.app.services.receipt_service import ReceiptService
from backend.app.storage import (
    FileSystemReceiptImageStorage,
    ReceiptImageStorageConfig,
    ReceiptImageValidator,
)
from backend.app.storage.s3 import S3ReceiptImageStorage


def _build_storage(config: ReceiptImageStorageConfig):
    if config.backend == "filesystem":
        return FileSystemReceiptImageStorage(config.filesystem_root)
    if not config.access_key or not config.secret_key:
        raise PersistenceFailure("S3 storage credentials are not configured.")
    client = boto3.client(
        "s3",
        endpoint_url=config.endpoint,
        region_name=config.region,
        aws_access_key_id=config.access_key,
        aws_secret_access_key=config.secret_key,
        use_ssl=config.secure,
    )
    return S3ReceiptImageStorage(client, config.bucket)


def build_processing_orchestrator() -> ProcessingOrchestrator:
    from backend.app.services.processing_orchestrator import ProcessingOrchestrator
    from ai.kie.pipeline import run_kie
    from ai.ocr import run_ocr

    engine = create_database_engine()
    session_factory = create_session_factory(engine)
    storage = _build_storage(ReceiptImageStorageConfig.from_env())
    return ProcessingOrchestrator(
        unit_of_work_factory=SQLAlchemyUnitOfWorkFactory(session_factory),
        image_loader=SQLAlchemyReceiptImageLoader(
            session_factory=session_factory,
            storage=storage,
        ),
        ocr_provider=run_ocr,
        kie_provider=run_kie,
        id_generator=UUID4Generator(),
        clock=SystemClock(),
    )



def build_processing_recovery_service():
    from backend.app.services.processing_recovery import (
        ProcessingRecoveryService,
    )

    stale_after_seconds = int(
        os.getenv("PROCESSING_STALE_AFTER_SECONDS", "900")
    )
    if stale_after_seconds <= 0:
        raise ValueError(
            "PROCESSING_STALE_AFTER_SECONDS must be positive."
        )

    engine = create_database_engine()
    session_factory = create_session_factory(engine)

    return ProcessingRecoveryService(
        unit_of_work_factory=SQLAlchemyUnitOfWorkFactory(
            session_factory
        ),
        clock=SystemClock(),
        stale_after=timedelta(seconds=stale_after_seconds),
    )

def build_receipt_service() -> ReceiptService:
    """Build the upload/retry service with the same DB and storage adapters as worker."""
    engine = create_database_engine()
    session_factory = create_session_factory(engine)
    config = ReceiptImageStorageConfig.from_env()
    storage = _build_storage(config)
    clock = SystemClock()
    ids = UUID4Generator()
    celery_client = Celery(
        "vietreceipt_api",
        broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
        backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
    )
    return ReceiptService(
        persistence=SQLAlchemyReceiptPersistenceService(
            validator=ReceiptImageValidator(
                max_size_bytes=config.max_upload_size_bytes,
                max_pixels=config.max_image_pixels,
            ),
            storage=storage,
            session_factory=session_factory,
            id_generator=ids,
            clock=clock,
        ),
        scheduler=CeleryProcessingScheduler(celery_client),
        unit_of_work_factory=SQLAlchemyUnitOfWorkFactory(session_factory),
        clock=clock,
    )
