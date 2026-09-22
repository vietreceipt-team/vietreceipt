"""Runs against a migrated dedicated test DB; never drops shared tables."""

import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker
from test_workflow import image_bytes, kie, reader

from backend.app.storage.filesystem import FileSystemReceiptImageStorage
from backend.app.v2.errors import V2Error
from backend.app.v2.models import Attempt, MachineRun
from backend.app.v2.processing import Processor
from backend.app.v2.runtime import database_engine
from backend.app.v2.service import InvoiceService


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="Requires real PostgreSQL TEST_DATABASE_URL",
)
def test_postgres_two_workers_and_stale_browser(tmp_path):
    service = InvoiceService(
        sessionmaker(
            database_engine(os.environ["TEST_DATABASE_URL"]), expire_on_commit=False
        ),
        FileSystemReceiptImageStorage(tmp_path / "files"),
    )
    r = service.upload("race.png", "image/png", image_bytes())
    rid = r["receipt_id"]
    with ThreadPoolExecutor(2) as p:
        outcomes = list(
            p.map(lambda _: Processor(service, reader, kie).process(rid), range(2))
        )
    assert sorted(outcomes) == [False, True]
    with service.sessions() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(Attempt)
                .where(Attempt.receipt_id == rid)
            )
            == 1
        )
        assert (
            s.scalar(
                select(func.count())
                .select_from(MachineRun)
                .where(MachineRun.receipt_id == rid)
            )
            == 2
        )
    r = service.detail(rid)

    def correct(i):
        try:
            service.correct(
                rid, "header", "", "invoice_number", str(i), "PRESENT", r["version"]
            )
            return 200
        except V2Error as e:
            return e.status

    with ThreadPoolExecutor(2) as p:
        assert sorted(p.map(correct, range(2))) == [200, 409]
