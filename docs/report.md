# Báo cáo DevOps W1 — Local Infrastructure Foundation

Nhánh: `feat/devops-local-infra-foundation` — commit HEAD: `ed04715`
Ngày: 2026-08-17

Kiến trúc mục tiêu đã đạt đủ:

```text
Frontend
   ↓
Backend API
   ↓
Background Worker
   ↓
PostgreSQL + Redis + MinIO
```

Cả 6 service (`postgres`, `redis`, `minio`, `minio-init`, `backend`, `worker`, `frontend`) đều chạy trong `docker-compose.yml`, dùng chung network `vietreceipt_internal`.

---

## 1. Docker Compose — ✅ Done

`docker compose up -d` chạy được từ thư mục gốc repo, không cần bước thủ công nào khác ngoài `cp .env.example .env`.

- Service name ổn định: `postgres`, `redis`, `minio`, `minio-init`, `backend`, `worker`, `frontend`.
- Network nội bộ `vietreceipt_internal` (bridge) — mọi container resolve nhau bằng service name.
- Không hard-code `localhost` sai ngữ cảnh: bên trong container luôn dùng service name (`postgres:5432`, `redis:6379`, `http://minio:9000`); `localhost` chỉ xuất hiện trong bảng endpoint dành cho host và trong healthcheck nội bộ của chính MinIO (đúng ngữ cảnh, vì healthcheck chạy trong container đó).
- Named volume cho PostgreSQL, Redis, MinIO.
- Đủ đơn giản: 1 lệnh `docker compose up -d` là chạy được toàn bộ, không cần config thêm.

## 2. PostgreSQL — ✅ Done

- `POSTGRES_DB`/`POSTGRES_USER`/`POSTGRES_PASSWORD` lấy từ environment, có default dev (`local_dev_only_change_me`), không phải secret thật.
- Persistent volume `vietreceipt_postgres_data`.
- Healthcheck `pg_isready -U $POSTGRES_USER -d $POSTGRES_DB`.
- `DATABASE_URL` dùng service name `postgres:5432`, document trong `.env.example`.
- Backend container xác minh kết nối được qua service name (xem mục "Bằng chứng").
- Không implement SQLAlchemy repository/business persistence — đúng phạm vi.

## 3. Redis — ✅ Done

- Redis chạy trong Compose, `--appendonly yes`, volume `vietreceipt_redis_data`.
- Healthcheck `redis-cli ping`.
- `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` document trong `.env.example`, dùng service name `redis`.
- Worker container xác nhận kết nối Redis thành công (log `Connected to redis://redis:6379/0`).
- Không implement processing semantics/receipt state transition — đúng phạm vi.

## 4. MinIO / Object Storage — ✅ Done

- Bucket private: `infra/minio/bootstrap.sh` chạy `mc mb --ignore-existing` + `mc anonymous set none`, idempotent.
- Credentials từ environment (`STORAGE_ACCESS_KEY`/`STORAGE_SECRET_KEY`), map sang `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` bên trong container.
- Persistent volume `vietreceipt_minio_data`.
- Healthcheck `GET /minio/health/live`.
- Expose S3 API `:9000` và Console `:9001`.
- Bootstrap mechanism: service one-shot `minio-init`, `depends_on: minio service_healthy`, exit 0.
- Không viết lại storage adapter của Backend-2; Backend-2 chỉ consume `STORAGE_*` do DevOps cung cấp.

## 5. Shared environment configuration — ✅ Done (1 sai lệch có chủ đích, đã xác nhận)

`.env.example` có đủ nhóm: `POSTGRES_*`, `DATABASE_URL`, `REDIS_URL` + Celery, `STORAGE_*`, `BACKEND_PORT`/`FRONTEND_PORT`. `.env` nằm trong `.gitignore`, không commit secret thật.

**Sai lệch có chủ đích:** đề bài liệt kê `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION`. Repo dùng `STORAGE_ENDPOINT`, `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_REGION` — vì đây đã là canonical convention của Backend-2 (`backend/README.md`). Tạo thêm nhóm `S3_*` sẽ tạo 2 nguồn config trùng nghĩa, đúng điều đề bài cấm. **Đã trao đổi và Backend owner xác nhận `STORAGE_*` là đúng, không đổi tên.**

Nhóm `BACKEND_*` trong đề bài: hiện có `BACKEND_PORT` (host port override); chưa có thêm biến `BACKEND_*` khác vì Backend chưa cần.

## 6. Healthchecks — ✅ Done

PostgreSQL, Redis, MinIO, Backend, Worker đều có Docker healthcheck — `docker compose ps` cho biết ngay service nào `healthy`/`unhealthy`. Frontend (Next.js dev server) không có healthcheck ở tầng Compose vì dev server không có endpoint health rẻ; được kiểm ở mức HTTP trong `infra/scripts/smoke-test.sh` thay vì.

Worker visibility dùng `celery -A celery_app inspect ping` — đúng phương án Backend owner gợi ý.

> **Follow-up non-blocking:** healthcheck của `backend` hiện trỏ `/openapi.json` (route FastAPI có sẵn, không phụ thuộc `service_registry`). Đây là lựa chọn chấp nhận được cho infrastructure foundation. Khi Backend cung cấp `/healthz` canonical, DevOps sẽ chuyển healthcheck sang endpoint đó. **Không** tạo fake business/API endpoint trong DevOps PR chỉ để phục vụ healthcheck.

## 7. Local developer workflow — ✅ Done

`infra/README.md` (và root `README.md` trỏ tới) hướng dẫn đủ:

| Việc | Lệnh |
| --- | --- |
| Start | `cp .env.example .env` → `docker compose up -d` |
| Status | `docker compose ps -a` |
| Logs | `docker compose logs -f` (hoặc theo từng service) |
| Stop (giữ data) | `docker compose down` |
| Reset (xoá data) | `docker compose down -v` — có cảnh báo không thể hoàn tác |

Bảng endpoint host đầy đủ cho cả 7 service, không cần đoán lệnh/config.

## 8. CI foundation — ✅ Done

`.github/workflows/backend-and-infra.yml` có 2 job:

1. `backend-storage-tests` — cài `-e "./backend[test]" -r backend/requirements-dev.txt`, chạy `pytest backend/tests` (122 test).
2. `infrastructure-smoke-test` — `cp .env.example .env`, chạy `./infra/scripts/smoke-test.sh`, dump log khi fail, `docker compose down -v --remove-orphans` luôn chạy.

Không chứa secret thật; `permissions: contents: read`; có path filter. PR có automated test signal, failure hiển thị rõ ở tab Checks; không cần production deployment cho W1.

Trong quá trình làm đã phát hiện và sửa một lỗi CI thật: sau khi merge `origin/main`, `backend/tests` có thêm test API dùng `TestClient` → cần package `httpx2` (đã pin trong `backend/requirements-dev.txt`) nhưng không nằm trong `pyproject.toml`'s `[test]` extra. Nếu không sửa, mọi PR chạm `backend/**` sẽ fail CI vì thiếu dependency.

**Đã có successful workflow run trên GitHub Actions** (xác nhận bởi branch owner). Link run cần dán vào PR description làm evidence.

## 9. Security baseline — ✅ Done

- Không có password/token/access key thật; chỉ placeholder (`local_dev_only_change_me`, `vietreceipt_local`).
- Object storage private mặc định (`mc anonymous set none`).
- `.env` trong `.gitignore`; `.dockerignore` cũng loại `.env`, `.git`, `.venv`, `.data`, `results`, `*.log`.
- `.env.example` chỉ placeholder/dev value.
- Log không in secret: bootstrap chỉ in tên bucket; smoke test redirect output có credential vào `/dev/null`.
- Không commit production configuration.

## 10. Ownership boundary — ✅ Done

Không thêm FastAPI business endpoint, receipt state-machine logic, OCR/KIE, SQL repository/business model, dashboard, auth, Kubernetes, deploy production, Prometheus/Grafana lớn, autoscaling, hay production secret management platform. Backend container chạy nguyên `backend/app/main.py` của Backend-1 không sửa; Worker container không có task nghiệp vụ nào (skeleton rỗng do DevOps tự tạo, không phải code của Backend-1/Backend-2).

Ranh giới đã chốt (đặc biệt quan trọng ở phần Worker, nơi đề bài gốc để lửng):

| Owner | Sở hữu |
| --- | --- |
| **Backend-1** | `ProcessingScheduler` semantics; application queue adapter; processing job payload; **worker handler/orchestration**; receipt state transitions; retry/idempotency/business failure semantics |
| **Backend-2** | persistence; storage abstraction/adapters; repository/application persistence services |
| **DevOps** | Redis/Celery runtime; **worker container/process**; broker configuration; networking; healthchecks; logs/runtime visibility; CI/local environment |

Điểm mấu chốt: DevOps sở hữu **worker container/process** (Dockerfile, broker config, healthcheck, log visibility) — Backend-1 sở hữu **worker handler/orchestration** (task nào chạy, xử lý gì, retry ra sao). **DevOps không sở hữu receipt-processing business semantics.** Đây chính là ranh giới đã áp dụng trong implementation: container chạy được và quan sát được, nhưng rỗng nghiệp vụ.

---

## Expected output — đối chiếu

| Artifact yêu cầu | Trạng thái |
| --- | --- |
| `docker-compose.yml` | ✅ có |
| `.env.example` | ✅ có |
| README/docs cho local environment | ✅ `infra/README.md` + root `README.md` |
| `.github/workflows/...` | ✅ `backend-and-infra.yml` + `contract-tests.yml` |
| Stack tối thiểu `postgres`, `redis`, `minio`, `backend`, `worker` | ✅ đủ, cộng thêm `frontend` |
| Frontend chạy trong container, có document | ✅ `next dev` trong Compose, document trong `infra/README.md` |

---

## Evidence bắt buộc — đã chạy thật, không phải suy đoán

### `docker compose config`

```
$ docker compose config --quiet
CONFIG_OK  (exit 0, không có lỗi cú pháp/biến thiếu)
```

### `docker compose up -d`

```
Container vietreceipt-postgres-1   Healthy
Container vietreceipt-redis-1      Healthy
Container vietreceipt-minio-1      Healthy
Container vietreceipt-minio-init-1 Started (exit 0)
Container vietreceipt-backend-1    Started
Container vietreceipt-worker-1     Started
Container vietreceipt-frontend-1   Started
```

### `docker compose ps`

```
NAME                       SERVICE      STATUS
vietreceipt-backend-1      backend      Up (healthy)
vietreceipt-frontend-1     frontend     Up
vietreceipt-minio-1        minio        Up (healthy)
vietreceipt-minio-init-1   minio-init   Exited (0)
vietreceipt-postgres-1     postgres     Up (healthy)
vietreceipt-redis-1        redis        Up (healthy)
vietreceipt-worker-1       worker       Up (healthy)
```

### Kiểm tra bổ sung (chứng minh service hoạt động thật, không chỉ "container chạy")

- `curl http://localhost:8000/openapi.json` → trả về đúng OpenAPI document (`"title":"VietReceipt API"`).
- `curl -L http://localhost:3000` → trả về HTML shell Next.js thật.
- `docker compose exec backend getent hosts postgres redis minio` → cả 3 resolve được **từ chính container `backend`**:
  ```
  172.18.0.3   postgres
  172.18.0.2   redis
  172.18.0.4   minio
  ```
- `docker compose logs worker` → `Connected to redis://redis:6379/0`, `celery@... ready.`

### Automated tests / CI

- Command đã chạy ở local: `PYTHON_BIN=.venv/bin/python ./infra/scripts/smoke-test.sh` — 10/10 bước PASS, bao gồm:
  - 122 Backend test pass (31 storage test + 91 API/domain test).
  - Contract suite pass: 9 positive + 23 negative case.
  - Persistence marker sống sót qua `docker compose up -d --force-recreate` (chứng minh volume thật sự persistent).
- **GitHub Actions: đã có successful workflow run** — workflow `backend-and-infra.yml` chạy xanh trên PR. Dán link run vào PR description làm evidence chính thức.

---

## Definition of Done

- [x] Docker Compose chạy được
- [x] PostgreSQL chạy và healthy
- [x] Redis chạy và healthy
- [x] MinIO chạy và healthy
- [x] persistent volumes được cấu hình
- [x] shared environment variables rõ ràng (đã xác nhận `STORAGE_*` với Backend owner)
- [x] `.env.example` được cập nhật
- [x] không có secret thật trong repository
- [x] Backend/Worker có thể resolve infrastructure qua service name (chứng minh từ chính container `backend`)
- [x] có local setup documentation
- [x] có health/status verification
- [x] CI foundation chạy được — workflow đã sửa lỗi thật (thiếu `httpx2`) và **đã có successful run trên GitHub Actions**
- [x] không duplicate Backend-1/Backend-2 implementation
- [x] PR có evidence chứng minh environment reproducible

**14/14 xong. DevOps W1 đạt Definition of Done.**

### Không thuộc DoD của task này (follow-up, không blocking)

- **Thay Worker skeleton bằng application worker thật.** Đề bài W1 chỉ yêu cầu *"Worker container/skeleton"* — skeleton Celery zero-task hiện tại **đã thoả mãn**. Luồng xử lý thật (`enqueue receipt_id → worker claim → PROCESSING → OCR → KIE → NEEDS_REVIEW`) là receipt-processing business semantics thuộc **Backend-1 / Issue #21**, không phải điều kiện đóng task DevOps W1.
- **Chuyển healthcheck của `backend` sang `/healthz`.** Hiện dùng `/openapi.json`, chấp nhận được cho infrastructure foundation. Khi Backend cung cấp `/healthz` canonical thì DevOps đổi sang. **Không** tạo fake business/API endpoint trong DevOps PR chỉ để phục vụ healthcheck.
