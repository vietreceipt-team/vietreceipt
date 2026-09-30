import os
from functools import lru_cache

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.app.storage.config import ReceiptImageStorageConfig
from backend.app.storage.filesystem import FileSystemReceiptImageStorage
from backend.app.storage.s3 import S3ReceiptImageStorage

from .service import InvoiceService


def database_engine(url):
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(
        url,
        pool_pre_ping=True,
        **(
            {"connect_args": {"check_same_thread": False, "timeout": 30}}
            if url.startswith("sqlite")
            else {}
        ),
    )
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")

    return engine


@lru_cache
def build_service():
    engine = database_engine(os.environ["DATABASE_URL"])
    config = ReceiptImageStorageConfig.from_env()
    if config.backend == "filesystem":
        storage = FileSystemReceiptImageStorage(config.filesystem_root)
    else:
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=config.endpoint,
            aws_access_key_id=config.access_key,
            aws_secret_access_key=config.secret_key,
            region_name=config.region,
            use_ssl=config.secure if config.secure is not None else True,
        )
        storage = S3ReceiptImageStorage(client, config.bucket)
    return InvoiceService(
        sessionmaker(engine, expire_on_commit=False),
        storage,
        max_upload_bytes=config.max_upload_size_bytes,
        max_retries=int(os.getenv("PROCESSING_MAX_RETRIES", "3")),
    )
