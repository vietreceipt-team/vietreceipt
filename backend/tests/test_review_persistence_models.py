from backend.app.persistence.models import Base


def test_canonical_review_persistence_tables_are_registered():
    tables = Base.metadata.tables

    assert "extracted_fields" in tables
    assert "correction_history" in tables
    assert "audit_events" in tables


def test_extracted_fields_has_canonical_identity_and_version_columns():
    table = Base.metadata.tables["extracted_fields"]

    assert set(table.primary_key.columns.keys()) == {
        "receipt_id",
        "field_name",
    }

    required_columns = {
        "receipt_id",
        "field_name",
        "ocr_run_id",
        "kie_run_id",
        "raw_text",
        "predicted_value",
        "normalized_value",
        "normalization",
        "value_status",
        "corrected_value",
        "corrected_status",
        "has_correction",
        "effective_value",
        "effective_status",
        "confidence",
        "machine_needs_review",
        "effective_needs_review",
        "review_reasons",
        "review_policy_version",
        "source_block_ids",
        "verified",
        "updated_at",
    }

    assert required_columns <= set(table.columns.keys())


def test_history_and_audit_tables_are_append_only_record_shapes():
    history = Base.metadata.tables["correction_history"]
    audit = Base.metadata.tables["audit_events"]

    assert list(history.primary_key.columns.keys()) == [
        "correction_id"
    ]
    assert list(audit.primary_key.columns.keys()) == [
        "event_id"
    ]

    assert {
        "receipt_id",
        "field_name",
        "operation",
        "kie_run_id",
        "old_value",
        "new_value",
        "old_status",
        "new_status",
        "changed_by",
        "changed_at",
    } <= set(history.columns.keys())

    assert {
        "receipt_id",
        "event_type",
        "field_name",
        "operation",
        "actor_id",
        "occurred_at",
    } <= set(audit.columns.keys())
