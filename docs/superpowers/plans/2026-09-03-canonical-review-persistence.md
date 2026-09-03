# Canonical Review Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hoàn thiện SQLAlchemy persistence cho fields, correction history và audit events để concrete UnitOfWork đáp ứng canonical contract.

**Architecture:** Ba repository mới dùng chung SQLAlchemy Session với receipts/processing. Field projection dùng atomic CAS; correction history và audit events append-only. Schema mới được thêm bằng migration tiếp nối `20260824_0002`.

**Tech Stack:** Python 3.12, SQLAlchemy, Alembic, pytest, PostgreSQL/SQLite.

**Spec:** `docs/superpowers/specs/2026-09-03-canonical-review-persistence-design.md`

## Global Constraints

- Không thay đổi canonical public API.
- Không biến FieldRepository.save() thành implicit upsert.
- SQLAlchemy errors phải map thành PersistenceFailure.
- CAS conflict phải raise StaleUpdate.
- Tất cả repository của UnitOfWork phải dùng cùng Session.
- OCR/KIE artifacts tiếp tục immutable.
- Không sửa migration lịch sử.

---

### Task 1: ORM schema

**Files:**
- Modify: `backend/app/persistence/models.py`
- Test: `backend/tests/test_review_persistence_models.py`

- [ ] Test ba bảng chưa tồn tại và xác nhận RED.
- [ ] Thêm ExtractedFieldRecord, CorrectionHistoryRecord, AuditEventRecord.
- [ ] Chạy test và xác nhận GREEN.

### Task 2: Field repository

**Files:**
- Create: `backend/app/persistence/sqlalchemy_field_repository.py`
- Test: `backend/tests/test_sqlalchemy_field_repository.py`

- [ ] Test get/list/save.
- [ ] Test atomic updated_at CAS.
- [ ] Test PersistenceFailure mapping.
- [ ] Implement repository tối thiểu để pass.

### Task 3: History + audit repositories

**Files:**
- Create: `backend/app/persistence/sqlalchemy_correction_history_repository.py`
- Create: `backend/app/persistence/sqlalchemy_audit_event_repository.py`
- Test: `backend/tests/test_sqlalchemy_review_event_repositories.py`

- [ ] Test append/list.
- [ ] Test deterministic ordering.
- [ ] Implement append-only repositories.

### Task 4: Canonical UnitOfWork wiring

**Files:**
- Modify: `backend/app/persistence/sqlalchemy_unit_of_work.py`
- Modify: `backend/app/persistence/__init__.py`
- Test: `backend/tests/test_sqlalchemy_unit_of_work.py`

- [ ] Test UoW exposes receipts, processing, fields, correction_history, audit_events.
- [ ] Wire all repositories to one Session.
- [ ] Verify rollback/commit semantics.

### Task 5: Alembic migration

**Files:**
- Create: `backend/migrations/versions/20260903_0003_review_persistence.py`

- [ ] Create extracted_fields.
- [ ] Create correction_history.
- [ ] Create audit_events.
- [ ] Verify upgrade/downgrade/upgrade.

### Task 6: Real service integration

**Files:**
- Test: `backend/tests/integration/test_review_persistence.py`

- [ ] Run CorrectionService using concrete SQLAlchemy UoW.
- [ ] Run VerificationService using concrete SQLAlchemy UoW.
- [ ] Verify history/audit persistence.
- [ ] Verify transaction rollback on stale field.

### Task 7: Processing field materialization

**Files:**
- Modify processing persistence/orchestration only as required by canonical KIE output.
- Test processing integration.

- [ ] Materialize exactly five canonical fields after KIE.
- [ ] Keep KIE run immutable.
- [ ] Complete NEEDS_REVIEW transition atomically.

### Task 8: Final verification

- [ ] Run full backend pytest suite.
- [ ] Run PostgreSQL tests.
- [ ] Run Alembic smoke.
- [ ] Run git diff --check.
- [ ] Run Compose processing E2E.
