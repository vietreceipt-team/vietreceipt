# Canonical Review Persistence Design

## Goal

Hoàn thiện concrete SQLAlchemy UnitOfWork để đáp ứng đầy đủ canonical UnitOfWork contract cho processing, correction, history và verification.

Concrete UnitOfWork phải expose:

- receipts
- processing
- fields
- correction_history
- audit_events

Tất cả repository phải dùng cùng một SQLAlchemy Session để các thay đổi thuộc một transaction duy nhất.

## Existing State

Hiện tại SQLAlchemyUnitOfWork chỉ expose:

- receipts
- processing

Canonical contract còn yêu cầu:

- fields
- correction_history
- audit_events

Chưa có concrete SQLAlchemy repositories hoặc database tables cho ba repository này.

## Database Model

Thêm ba bảng mới.

### extracted_fields

Đây là current canonical field projection.

Primary key:

- receipt_id
- field_name

Fields:

- receipt_id
- field_name
- ocr_run_id
- kie_run_id
- raw_text
- predicted_value
- normalized_value
- normalization
- value_status
- corrected_value
- corrected_status
- has_correction
- effective_value
- effective_status
- confidence
- machine_needs_review
- effective_needs_review
- review_reasons
- review_policy_version
- source_block_ids
- verified
- updated_at

Các canonical values kiểu `str | int | None` được lưu bằng JSON để giữ nguyên type.

`review_reasons` và `source_block_ids` cũng được lưu bằng JSON array.

Machine OCR/KIE artifacts vẫn immutable trong `ocr_runs` và `kie_runs`.
`extracted_fields` chỉ là mutable review projection.

### correction_history

Append-only table.

Fields:

- correction_id primary key
- receipt_id foreign key
- field_name
- operation
- kie_run_id
- old_value
- new_value
- old_status
- new_status
- changed_by
- changed_at

Không có update/delete repository method.

### audit_events

Append-only table.

Fields:

- event_id primary key
- receipt_id foreign key
- event_type
- field_name nullable
- operation nullable
- actor_id nullable
- occurred_at

Không có update/delete repository method.

## Repository Design

### SQLAlchemyFieldRepository

Implements:

- get(receipt_id, field_name)
- list_for_receipt(receipt_id, kie_run_id=None)
- save(field, expected_updated_at)

`save()` dùng atomic database CAS:

UPDATE extracted_fields
SET ...
WHERE receipt_id = :receipt_id
  AND field_name = :field_name
  AND updated_at = :expected_updated_at

Rules:

- rowcount == 1: success
- rowcount == 0: raise StaleUpdate
- SQLAlchemyError: raise PersistenceFailure

Không dùng SELECT -> Python compare -> UPDATE.

### SQLAlchemyCorrectionHistoryRepository

Implements:

- append(record)
- list_for_receipt(receipt_id)

Append-only.

Read ordering:

- changed_at ASC
- correction_id ASC

SQLAlchemy errors được map thành PersistenceFailure.

### SQLAlchemyAuditEventRepository

Implements:

- append(event)
- list_for_receipt(receipt_id)

Append-only.

Read ordering:

- occurred_at ASC
- event_id ASC

SQLAlchemy errors được map thành PersistenceFailure.

## Transaction Boundary

SQLAlchemyUnitOfWork tạo tất cả repository bằng cùng một Session:

- SQLAlchemyReceiptRepository
- SQLAlchemyProcessingRepository
- SQLAlchemyFieldRepository
- SQLAlchemyCorrectionHistoryRepository
- SQLAlchemyAuditEventRepository

Correction flow:

1. save field
2. save receipt
3. append correction history
4. append audit events
5. commit

Verification flow:

1. save five fields
2. save receipt
3. append audit events
4. commit

Nếu bất kỳ thao tác nào fail trước commit, toàn bộ transaction rollback.

Nếu commit fail:

- rollback
- raise PersistenceFailure

## Initial Machine Field Creation

FieldRepository.save() không được biến thành implicit upsert.

Processing/KIE cần một explicit creation boundary cho lần đầu persist năm canonical machine fields.

Creation phải:

- tạo đúng five canonical fields cho một KIE run
- không overwrite field projection hiện có ngoài flow được định nghĩa
- giữ immutable KIE artifact riêng biệt
- dùng cùng transaction với processing completion

Chi tiết API creation sẽ được triển khai tối thiểu theo nhu cầu của processing flow, không mở rộng public canonical FieldRepository contract nếu không cần thiết.

## Migration

Tạo migration mới sau:

20260824_0002_processing_runs.py

Không sửa migration lịch sử.

Migration mới tạo:

- extracted_fields
- correction_history
- audit_events

Foreign keys phải tham chiếu receipts và run identity phù hợp.

## Concurrency

Receipt CAS hiện tại được giữ nguyên.

Field correction CAS phải chạy atomic tại database.

Two-session regression test phải chứng minh:

- hai transaction đọc cùng field version
- transaction đầu update thành công
- transaction sau dùng stale expected_updated_at bị StaleUpdate

Nếu verification update nhiều field và một field stale, transaction phải rollback toàn bộ.

## Error Semantics

Implementation-specific SQLAlchemy exceptions không được leak lên service layer.

Map thành:

- StaleUpdate cho CAS conflict
- PersistenceFailure cho database failure

Domain/service errors vẫn giữ nguyên.

## Testing

Bắt buộc có:

- SQLAlchemy field repository CRUD/read tests
- atomic two-session field CAS regression test
- correction history append/list ordering test
- audit event append/list ordering test
- concrete UnitOfWork exposes all canonical repositories
- correction flow chạy thật với SQLAlchemy UnitOfWork
- verification flow chạy thật với SQLAlchemy UnitOfWork
- rollback regression
- migration upgrade test
- full backend suite
- PostgreSQL CI validation

Implementation thực hiện theo TDD: test fail trước, sau đó mới thêm production code.
