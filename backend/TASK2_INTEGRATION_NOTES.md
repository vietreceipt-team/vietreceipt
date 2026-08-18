# Task 2 integration notes

This revision adapts Backend-2 persistence/storage work to the Week-2 canonical backend
architecture merged into `main`.

## Removed duplicates

- local `ReceiptService`
- local `Receipt` / `ReceiptStatus` domain duplicates
- local `ReceiptRepository` protocol duplicate
- local `PersistenceFailure` duplicate

## Canonical contracts consumed

- `backend.app.domain.models.Receipt`
- `backend.app.domain.enums.ReceiptStatus`
- `backend.app.domain.errors.PersistenceFailure`
- `backend.app.ports.persistence.ReceiptPersistenceService`
- `backend.app.repositories.protocols.ReceiptRepository`
- `backend.app.ports.ids.IdGenerator`
- `backend.app.ports.clock.Clock`

## Backend-2 concrete adapters

- `SQLAlchemyReceiptPersistenceService`
- `SQLAlchemyReceiptRepository`
- `SQLAlchemyUnitOfWork`
- Alembic receipt migration
- storage compensation on DB failure
- internal delete foundation

## Open contract questions

- `ReceiptUpload` has no owner/user reference.
- Canonical `ReceiptService` currently wraps validation/storage errors that are not
  `PersistenceFailure`.

Backend-2 intentionally does not modify public API/domain contracts to resolve those
questions.
