# Hạ tầng và triển khai VietReceipt

Thư mục này chứa các cấu hình liên quan đến triển khai, môi trường chạy và hạ tầng của hệ thống VietReceipt.

## Phạm vi chính

- Docker
- Docker Compose
- Cấu hình cơ sở dữ liệu
- Cấu hình lưu trữ tệp
- Biến môi trường
- Quy trình triển khai
- Nhật ký hệ thống
- Kiểm tra tình trạng dịch vụ
- Hỗ trợ môi trường phát triển và môi trường chạy thử

## Thành viên phụ trách chính

Đặng Quang Trung — DevOps, QA và phân tích hệ thống

## Nguyên tắc

- Không ghi mật khẩu hoặc khóa bí mật trực tiếp trong file cấu hình.
- Các thông tin nhạy cảm phải được truyền qua biến môi trường.
- Mọi dịch vụ phải có hướng dẫn chạy rõ ràng.
- Cấu hình triển khai phải có khả năng tái tạo trên máy khác.
- Không đưa dữ liệu hóa đơn thật vào image Docker hoặc file cấu hình.
- Mọi thay đổi phải gắn với GitHub Issue tương ứng.

## Chạy hạ tầng local

Từ thư mục gốc của repository:

```bash
cp .env.example .env
docker compose up -d
docker compose ps -a
```

Compose khởi động PostgreSQL, Redis, MinIO, Backend, Worker và Frontend trên
network `vietreceipt_internal`. Container `minio-init` chờ MinIO healthy, tạo
bucket private `vietreceipt` nếu chưa có, rồi thoát với code 0. Việc chạy lại
init là an toàn.

Các endpoint từ máy host:

| Dịch vụ | Endpoint mặc định |
| --- | --- |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |
| MinIO S3 API | `http://localhost:9000` |
| MinIO Console | `http://localhost:9001` |
| Backend API | `http://localhost:8000` (OpenAPI tại `/openapi.json`, docs tại `/docs`) |
| Frontend (vanilla HTML/CSS/JavaScript server) | `http://localhost:3000` |

`Backend` build từ `infra/docker/backend.Dockerfile`, chạy đúng app FastAPI mà
Backend-1 commit tại `backend/app/main.py`; DevOps chỉ container hoá, không
sửa domain/API code. `Worker` build từ `infra/docker/worker.Dockerfile`, chạy
một Celery app rỗng (`infra/docker/worker/celery_app.py`) chỉ để chứng minh
worker kết nối được Redis broker — **chưa có task xử lý hóa đơn nào**; task đó
thuộc về Backend-1/Backend-2. `Frontend` build từ
`infra/docker/frontend.Dockerfile`, chạy static server không dependency cho môi
trường local. Server giữ route `/receipts/{receipt_id}/` và reverse proxy
`/api/v1/*` tới `BACKEND_API_ORIGIN=http://backend:8000`; đây không phải
production image.

Backend, Worker và Frontend chạy trong cùng Compose network phải dùng service
name, không dùng `localhost`:

```dotenv
DATABASE_URL=postgresql+psycopg://vietreceipt:...@postgres:5432/vietreceipt
REDIS_URL=redis://redis:6379/0
STORAGE_ENDPOINT=http://minio:9000
BACKEND_API_ORIGIN=http://backend:8000
```

`POSTGRES_*` chỉ dành cho container PostgreSQL. `DATABASE_URL` là nguồn cấu
hình database duy nhất của Backend/Worker. Tất cả storage adapter dùng nhóm
`STORAGE_*`; không thêm nhóm biến `S3_*` thứ hai.

W1 chốt `STORAGE_BACKEND=filesystem`. MinIO vẫn được provision, healthcheck và
tạo bucket private để chuẩn bị hạ tầng S3-compatible, nhưng chưa phải storage
adapter runtime. Khi team quyết định chuyển runtime sang MinIO, giá trị hợp lệ
là `STORAGE_BACKEND=s3`, không phải `minio`.

## Lệnh vận hành

```bash
docker compose ps -a
docker compose logs -f
docker compose down
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-contracts.txt
.venv/bin/python -m pip install -e "./backend[test]" -r backend/requirements-dev.txt
PYTHON_BIN=.venv/bin/python ./infra/scripts/smoke-test.sh
```

`docker compose down` xóa container/network nhưng giữ ba named volume:
`vietreceipt_postgres_data`, `vietreceipt_redis_data` và
`vietreceipt_minio_data`.

> **Cảnh báo:** `docker compose down -v` xóa toàn bộ dữ liệu local trong cả ba
> volume và không thể hoàn tác.

Chi tiết kịch bản kiểm tra nằm tại `../docs/test-plan-v1.md`.
