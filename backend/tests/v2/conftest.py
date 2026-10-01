import pytest
from sqlalchemy.orm import sessionmaker

from backend.app.storage.filesystem import FileSystemReceiptImageStorage
from backend.app.v2.models import Base
from backend.app.v2.runtime import database_engine
from backend.app.v2.service import InvoiceService


@pytest.fixture
def svc(tmp_path):
    engine = database_engine("sqlite:///" + str(tmp_path / "db.sqlite"))
    Base.metadata.create_all(engine)
    yield InvoiceService(
        sessionmaker(engine, expire_on_commit=False),
        FileSystemReceiptImageStorage(tmp_path / "files"),
    )
    engine.dispose()
