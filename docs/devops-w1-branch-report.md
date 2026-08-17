# Báo cáo nhánh `feat/devops-local-infra-foundation`

Người thực hiện: Đặng Quang Trung — DevOps
Ngày lập báo cáo: 2026-08-17 (cập nhật lần 3, cùng ngày, sau khi commit và push)
Nhánh: `feat/devops-local-infra-foundation`
Commit HEAD: `e5f78bc`
Trạng thái push: **đã push đầy đủ.** `origin/feat/devops-local-infra-foundation` trùng đúng `e5f78bc` — không còn commit local nào chưa lên remote. Push gồm: merge commit từ `origin/main` (`46e5fd4`, mang theo Week-2 Core Receipt + HITL API, PR #19) và 3 commit mới (`889d274`, `a0c8bf0`, `e5f78bc`), tổng cộng nối thêm 13 commit lên nhánh so với lần push trước (`7cf4e77`).

---

## 1. Việc vừa thực hiện trong lượt này

Báo cáo lần đầu (cùng ngày) chỉ ra thiếu sót: chưa có service `backend`, `worker`, `frontend` trong Compose ⇒ stack tối thiểu theo yêu cầu chưa đủ 5 service. Đã xử lý:

1. **Merge `origin/main` vào nhánh** (merge commit, không rebase/force-push) để lấy `backend/app/main.py` — entrypoint FastAPI thật, chỉ mới có trên `main` sau PR #19, chưa từng có trên nhánh này lúc tách ra.
2. **Container hoá Backend thật**: `infra/docker/backend.Dockerfile` không còn là placeholder `http.server`; cài `backend/requirements.txt`, chạy `uvicorn backend.app.main:app`. Không sửa code Backend-1.
3. **Worker skeleton**: `infra/docker/worker.Dockerfile` + `infra/docker/worker/celery_app.py` — app Celery rỗng, broker/backend trỏ Redis qua `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND`, **không có task nghiệp vụ nào**. Chỉ chứng minh worker kết nối được Redis.
4. **Frontend container**: `infra/docker/frontend.Dockerfile` chạy `next dev` (dev server, không phải production image).
5. Thêm 3 service `backend`, `worker`, `frontend` vào `docker-compose.yml`, dùng chung `vietreceipt_internal`, dùng đúng biến canonical (`DATABASE_URL`, `REDIS_URL`, `CELERY_*`, `STORAGE_*`). `backend` và `worker` có healthcheck; `frontend` không có Compose healthcheck (dev server không có endpoint health rẻ) nhưng được smoke test kiểm ở mức HTTP.
6. Thêm `BACKEND_PORT`, `FRONTEND_PORT` vào `.env.example`.
7. Mở rộng `infra/scripts/smoke-test.sh` (8 bước → 10 bước): chờ `backend`/`worker` healthy, **xác minh DNS từ chính container `backend`** (`getent hosts postgres redis minio`) thay vì chỉ từ `postgres`, kiểm `backend` trả `/openapi.json`, kiểm `frontend` phản hồi HTTP.
8. **Phát hiện và sửa một lỗi CI thực sự**: sau khi merge, `backend/tests` có thêm các test API dùng `TestClient`, đòi hỏi package `httpx2` (khai báo sẵn trong `backend/requirements-dev.txt`, do Backend team pin) — package này KHÔNG nằm trong `pyproject.toml`'s `[test]` extra. CI job cũ (`pip install -e "./backend[test]"`) sẽ fail ngay khi có PR vì thiếu `httpx2`/`fastapi`/`uvicorn`. Đã sửa cả hai job trong `.github/workflows/backend-and-infra.yml` thành `pip install -e "./backend[test]" -r backend/requirements-dev.txt`, và cập nhật lệnh tương ứng trong `infra/README.md` và `docs/test-plan-v1.md`.
9. Root `README.md` giờ trỏ tới `infra/README.md` trong bảng Deliverables.
10. `docs/implementation-notes.md` thêm mục "Update — 2026-08-17" ghi lại quyết định và validation hôm nay (không sửa mục ngày 2026-08-14 cũ).
11. `docs/devops-delivery-checklist.md` cập nhật toàn bộ trạng thái.

---

## 2. Bằng chứng đã chạy thật (không phải suy đoán)

Đã build và chạy toàn bộ stack local, xác minh trực tiếp bằng lệnh, không chỉ đọc code:

```
docker compose build backend worker frontend   → thành công, cả 3 image build xong
docker compose up -d                            → 6/6 service start
docker compose ps -a
```

| Service | Trạng thái quan sát được |
| --- | --- |
| postgres | `healthy` |
| redis | `healthy` |
| minio | `healthy` |
| minio-init | `Exited (0)` |
| backend | `healthy` |
| worker | `healthy` |
| frontend | `Up` (không có healthcheck, kiểm ở mức HTTP — xem dưới) |

Kiểm tra bổ sung:

- `curl http://localhost:8000/openapi.json` → trả về đúng OpenAPI document thật của VietReceipt (`"title":"VietReceipt API"`).
- `curl -L http://localhost:3000` → trả về HTML shell Next.js thật.
- `docker compose exec backend python -c "socket.gethostbyname(...)"` → `postgres`, `redis`, `minio` đều resolve được **từ chính container backend** (172.18.0.x) — đây là bằng chứng trực tiếp cho DoD "Backend/Worker resolve infrastructure qua service name", mạnh hơn báo cáo trước (lúc đó Backend/Worker chưa tồn tại nên chỉ suy luận từ cấu hình).
- `docker compose logs worker` → `Connected to redis://redis:6379/0`, `celery@... ready.`
- Chạy `./infra/scripts/smoke-test.sh` toàn bộ 10 bước: **PASS toàn bộ**, bao gồm 122 Backend test (31 storage test cũ + 91 test API/domain mới từ merge) và full contract suite (9 positive + 23 negative case).
- `docker compose down` (không dùng `-v`) → giữ nguyên 3 volume dữ liệu.

---

## 3. Đối chiếu Definition of Done — cập nhật

| # | Tiêu chí | Trạng thái | Thay đổi so với báo cáo trước |
| --- | --- | --- | --- |
| 1 | Docker Compose chạy được | ✅ | không đổi |
| 2 | PostgreSQL chạy và healthy | ✅ | không đổi |
| 3 | Redis chạy và healthy | ✅ | không đổi |
| 4 | MinIO chạy và healthy | ✅ | không đổi |
| 5 | Persistent volumes được cấu hình | ✅ | không đổi |
| 6 | Shared environment variables rõ ràng | ✅ | thêm `BACKEND_PORT`/`FRONTEND_PORT`; Backend owner đã confirm `STORAGE_*` đúng, không đổi tên |
| 7 | `.env.example` được cập nhật | ✅ | không đổi |
| 8 | Không có secret thật trong repository | ✅ | không đổi |
| 9 | Backend/Worker resolve infrastructure qua service name | ✅ | **nâng từ ⚠️ lên ✅** — giờ chứng minh được từ chính container backend, không còn suy luận |
| 10 | Có local setup documentation | ✅ | `infra/README.md` cập nhật đủ 6 service |
| 11 | Có health/status verification | ✅ | `backend`/`worker` có healthcheck; `frontend` kiểm HTTP trong smoke test |
| 12 | CI foundation chạy được | ⚠️ | Workflow đã sửa lỗi thực sự (thiếu `httpx2`) và đã validate logic tương đương ở local; **vẫn chưa có bằng chứng một lần chạy Actions thật trên GitHub** vì chưa mở PR |
| 13 | Không duplicate Backend-1/Backend-2 implementation | ✅ | Backend container chạy nguyên `app/main.py` của Backend-1; Worker không có task nào |
| 14 | PR có evidence chứng minh environment reproducible | ❌ | **Chưa mở PR** — đây là việc còn lại duy nhất mang tính thủ tục |

Kết luận: **13/14 xong**, chỉ còn treo việc mở PR + đính kèm log Actions chạy xanh.

---

## 4. Việc còn lại (chỉ mang tính thủ tục, không còn khoảng trống kỹ thuật)

1. **Mở PR**, đính kèm evidence: `docker compose config`, `docker compose up -d`, `docker compose ps`, output smoke test, và link tới GitHub Actions run thành công sau khi CI chạy trên PR.
2. **Thay Worker skeleton bằng Celery app thật** khi Backend/Worker owner chốt module path + dependency — xem mục 6 dưới.

Đã xử lý xong trong lượt này (không còn treo):

- ~~Xác nhận với Backend owner việc dùng `STORAGE_*` thay vì `S3_*`~~ — **Backend owner đã confirm `STORAGE_*` đúng, giữ nguyên, không đổi tên.**
- ~~Commit các thay đổi~~ — xem mục 7 dưới, đã commit theo nhóm và push.

---

## 5. Rủi ro/lưu ý kỹ thuật cần biết khi review

- `backend`'s `service_registry` mặc định là `None` (`create_app()` không truyền registry) ⇒ phần lớn endpoint `/api/v1/*` sẽ trả lỗi 500 cho tới khi Backend wire persistence thật. Healthcheck cố tình dùng `/openapi.json` vì route này không phụ thuộc `service_registry`.
- Worker chưa có bất kỳ task nghiệp vụ nào — container chạy được nhưng "rỗng", đúng như đề bài chỉ yêu cầu "skeleton".
- Frontend chưa gọi Backend API (không có biến `NEXT_PUBLIC_API_*` nào trong code) — container hoá không thay đổi việc đó, đây là việc của Frontend/Backend owner sau này.
- `infra/docker/backend.Dockerfile` giờ COPY toàn bộ `backend/` (không dùng `.dockerignore` riêng cho subfolder) — image build sẽ include cả `backend/tests`; đủ dùng cho W1, có thể tối ưu sau bằng multi-stage build nếu cần giảm kích thước.

---

## 6. Backend đã "tích hợp entrypoint", Worker thì chưa — vì sao khác nhau

Backend owner đã gửi contract chính thức cho entrypoint FastAPI:

- Module path từ repository root: `backend.app.main:app`.
- Command: `python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`.
- Dependencies: `fastapi==0.141.1`, `pydantic==2.13.4`, `pydantic-settings==2.15.0`, `python-multipart==0.0.32`, `uvicorn[standard]==0.52.3` — đúng những gì đã có trong `backend/requirements.txt`.
- Chưa có `/healthz`/`/readyz` trong PR #19; Backend khuyến cáo **không** cấu hình probe vào endpoint chưa tồn tại.

`infra/docker/backend.Dockerfile` đã khớp contract này về bản chất từ trước (cùng module path, host, port, nguồn dependency); đã chỉnh CMD dùng đúng form `python -m uvicorn ...` để khớp 1:1 với command đã confirm, dễ review. Healthcheck trong Compose cố tình dùng `/openapi.json` (route FastAPI tự có sẵn, không phụ thuộc `service_registry`) làm probe tạm thời — **khi Backend có `/healthz` thì phải đổi healthcheck sang đó**, chưa làm vì endpoint chưa tồn tại. → **"Tích hợp Backend khi có entrypoint": đã xong, không còn việc gì treo.**

Worker khác hẳn: Backend/Worker owner xác nhận **chưa chốt** Celery module path, chưa chốt worker command, và **chưa khai báo Celery/Redis client nào trong dependency của PR #19**. Không có "entrypoint thật" nào để tích hợp. `infra/docker/worker/celery_app.py` + `infra/docker/worker.Dockerfile` trong nhánh này là **skeleton do DevOps tự tạo** (rỗng, không task, tự pin `celery[redis]==5.4.0` riêng) — chỉ để chứng minh hạ tầng Redis/Celery hoạt động, đúng đúng yêu cầu "Worker container/skeleton" trong đề bài. Healthcheck của nó đã dùng đúng phương án Backend gợi ý (`celery -A <app> inspect ping`). → **"Tích hợp Worker khi có entrypoint": vẫn còn treo, cố ý.** Khi Backend/Worker owner chốt Celery app thật, DevOps cần trỏ `infra/docker/worker.Dockerfile` sang module path của họ và bỏ file `celery_app.py`/`requirements.txt` tạm này.

## 7. Commit và push

Các thay đổi trong lượt này được commit theo nhóm logic rồi push:

1. `46e5fd4` — Merge commit từ `origin/main` (đã tạo tự động lúc `git merge`, không rebase/force-push).
2. `889d274` — `feat(infra): containerize backend, worker and frontend for local compose` — Dockerfile, `docker-compose.yml`, `.env.example`.
3. `a0c8bf0` — `test(infra): extend smoke checks and fix backend CI dependency install` — `infra/scripts/smoke-test.sh`, `.github/workflows/backend-and-infra.yml`.
4. `e5f78bc` — `docs(infra): document backend/worker/frontend containers and confirm STORAGE_*` — toàn bộ tài liệu liên quan.

Đã push bằng `git push origin feat/devops-local-infra-foundation` thường (không force): `7cf4e77..e5f78bc`. Không viết lại lịch sử đã có trên remote — chỉ nối thêm commit.

---

## 8. Tài liệu liên quan

- [infra/README.md](../infra/README.md) — hướng dẫn chạy hạ tầng local, đã cập nhật đủ 6 service
- [docs/test-plan-v1.md](test-plan-v1.md) — kịch bản kiểm tra
- [docs/implementation-notes.md](implementation-notes.md) — quyết định kỹ thuật, có mục cập nhật riêng ngày 2026-08-17
- [docs/devops-delivery-checklist.md](devops-delivery-checklist.md) — checklist bàn giao, đã cập nhật
