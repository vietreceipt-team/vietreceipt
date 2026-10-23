import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DatabaseError


def test_migration_preserves_legacy_and_runs_are_immutable(tmp_path, monkeypatch):
    url = "sqlite:///" + str(tmp_path / "migration.db")
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_engine(url)
    with engine.begin() as c:
        c.execute(text("CREATE TABLE legacy_receipts (id INTEGER PRIMARY KEY)"))
        c.execute(text("INSERT INTO legacy_receipts VALUES (7)"))
    cfg = Config("backend/alembic.ini")
    command.upgrade(cfg, "head")
    assert "invoice_v2_receipts" in inspect(engine).get_table_names()
    with engine.begin() as c:
        assert c.scalar(text("SELECT id FROM legacy_receipts")) == 7
    command.downgrade(cfg, "base")
    assert "legacy_receipts" in inspect(engine).get_table_names()
    command.upgrade(cfg, "head")
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO invoice_v2_machine_runs (run_id,receipt_id,attempt_id,kind,payload,created_at) VALUES ('r','i','a','OCR','{}','2026-09-21')"
            )
        )
    # Database enforcement applies even to direct SQL, beyond ORM events.
    with engine.begin() as c:
        with pytest.raises(DatabaseError):
            c.execute(text("UPDATE invoice_v2_machine_runs SET kind='KIE'"))


def test_provenance_upgrade_preserves_existing_attempt(tmp_path, monkeypatch):
    url = "sqlite:///" + str(tmp_path / "existing.db")
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config("backend/alembic.ini")
    command.upgrade(config, "20260921_v2")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO invoice_v2_attempts (attempt_id,receipt_id,ocr_run_id,kie_run_id,status,stage,lease_until,created_at) VALUES ('old','invoice','ocr','kie','FAILED','DOCUMENT_READING',1,'2026-09-21')"
            )
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT attempt_id, status, provenance FROM invoice_v2_attempts")
        ).one()
        assert tuple(row) == ("old", "FAILED", None)
    engine.dispose()
