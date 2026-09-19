> **LEGACY v1 NOTICE (19/09/2026):** This file belongs to the former five-field Week-1/2/3 plan. Do not use it as a current requirement. See `README.md`, `docs/project-plan.md` and `docs/migration-status.md`.

# Phân tích phản hồi review DevOps W1

Ngày: 2026-08-17
Nhánh: `feat/devops-local-infra-foundation` — HEAD `ed04715`
Mục đích: giải thích reviewer đang nói gì, và đánh giá từng điểm đúng/sai trước khi sửa tài liệu.

---

## Tóm tắt: reviewer đang nói gì

Reviewer **không chê phần implementation**. Verdict của họ là *"DEVOPS W1 IMPLEMENTATION: TECHNICALLY APPROVED"* — code/hạ tầng đạt yêu cầu. Toàn bộ góp ý chỉ nhắm vào **tài liệu (PR description + checklist) đang bị stale**, tức là mô tả trạng thái cũ hơn thực tế.

5 điểm họ yêu cầu:

| # | Nội dung | Bản chất |
| --- | --- | --- |
| 1 | CI đã có successful workflow → sửa từ "Partial" thành "Done" | Sửa theo **sự kiện thực tế** |
| 2 | Worker skeleton **không** phải blocker của W1; việc thay bằng worker thật thuộc Issue #21 | Sửa **phân loại công việc** |
| 3 | Chốt lại wording ownership boundary chi tiết hơn giữa Backend-1 / Backend-2 / DevOps | Làm rõ **ranh giới** |
| 4 | Healthcheck `/openapi.json` là chấp nhận được, chỉ là follow-up non-blocking | **Xác nhận** cách làm hiện tại |
| 5 | Sau khi dọn tài liệu → sẵn sàng merge review; không thêm feature ngoài scope | Kết luận |

---

## Đánh giá từng điểm

### Điểm 1 — "CI đã Done, đã có successful workflow evidence"

**Trạng thái: ⚠️ KHÔNG XÁC MINH ĐƯỢC TỪ PHÍA TÔI — cần bạn xác nhận trước khi sửa.**

Đây là điểm quan trọng nhất và là điểm duy nhất tôi không thể tự kiểm chứng. Lý do:

- `gh auth status` → `You are not logged into any GitHub hosts`. Tôi không có quyền đọc GitHub Actions hay danh sách PR.
- `git fetch origin` → `origin/feat/devops-local-infra-foundation` vẫn đúng `ed04715`, bằng local. Không có commit mới nào cho thấy có hoạt động CI.

Và một chi tiết kỹ thuật quyết định: workflow `.github/workflows/backend-and-infra.yml` chỉ trigger khi

```yaml
on:
  pull_request:        # bất kỳ PR nào chạm path đã lọc
  push:
    branches: [main]   # chỉ push vào main
```

Push vào nhánh `feat/devops-local-infra-foundation` **không** trigger workflow này. Nghĩa là **để có một successful run, bắt buộc phải có PR đã được mở**. Khi tôi kiểm tra lần cuối thì chưa có PR nào.

Vậy có 2 khả năng:

- **(a) Reviewer đúng** — bạn (hoặc ai đó) đã mở PR sau tin nhắn cuối của tôi, CI đã chạy và xanh. Khi đó sửa docs thành "Done" là chính xác.
- **(b) Reviewer nhầm** — họ suy đoán rằng CI đã chạy vì thấy workflow file tồn tại và code có vẻ ổn.

**Một dấu hiệu nghiêng về (a):** reviewer nhắc tới `Issue #17` và `Issue #21`, trong khi hai số hiệu này **không xuất hiện ở bất kỳ đâu trong repo** (`grep` toàn bộ `docs/`, `infra/`, `README.md` đều không có). Tức là reviewer đang đọc GitHub issue tracker thật — họ có quyền truy cập GitHub mà tôi không có. Điều đó khiến khả năng họ thực sự nhìn thấy CI run là khá cao.

**Nhưng "khá cao" không phải là "đã xác minh".** Tôi sẽ không ghi "CI Done, đã có successful workflow evidence" vào tài liệu chỉ dựa trên lời khẳng định, vì như vậy là bịa bằng chứng — đúng thứ mà toàn bộ report này đang cố tránh. Cần bạn xác nhận, tốt nhất là kèm link tới workflow run.

> **Cần bạn cung cấp:** link workflow run (dạng `https://github.com/vietreceipt-team/vietreceipt/actions/runs/<id>`) hoặc ảnh chụp tab Checks của PR. Có link rồi tôi sửa docs ngay và dán link vào đúng chỗ evidence.

### Điểm 2 — "Worker skeleton không phải blocker của W1"

**Trạng thái: ✅ ĐÚNG. Đây là góp ý xác đáng, tài liệu của tôi đang sai chỗ này.**

Reviewer đúng ở cả hai vế:

1. **Đề bài W1 chỉ yêu cầu "Worker container/skeleton"** — nguyên văn trong danh sách service chính. Worker Celery rỗng, zero-task, chỉ chứng minh kết nối Redis là **đã đủ** cho W1.
2. **Tài liệu của tôi đang liệt kê nó như việc còn treo**, ở đúng 2 chỗ:
   - `docs/devops-delivery-checklist.md:61` — nằm trong mục *"Still required before marking the whole attached DevOps task fully Done"*
   - `docs/devops-w1-branch-report.md:86` — nằm trong mục *"Việc còn lại"*

Đặt nó ở hai mục đó ngụ ý W1 **chưa xong** cho tới khi có worker thật. Điều đó sai về mặt phân loại: nó là **follow-up cho task khác**, không phải điều kiện đóng task này. Reviewer chỉ ra đúng rằng luồng xử lý thật:

```text
enqueue receipt_id → worker claim → PROCESSING → OCR → KIE → NEEDS_REVIEW
```

là **receipt-processing business semantics**, thuộc Backend-1 (Issue #21), không thuộc DevOps. Nếu để nguyên wording hiện tại, người đọc sẽ tưởng DevOps còn nợ việc, hoặc tệ hơn là tưởng DevOps phải tự implement luồng nghiệp vụ đó — vi phạm chính ranh giới ownership mà đề bài đặt ra.

**Cần sửa:** chuyển 2 dòng trên từ "việc còn lại / still required" sang mục "follow-up thuộc Issue #21 — không blocking W1".

### Điểm 3 — "Chốt lại wording ownership boundary"

**Trạng thái: ✅ ĐÚNG, và là bản làm rõ tốt hơn đề bài gốc.**

Bảng ownership reviewer đưa ra không mâu thuẫn với đề bài, mà **chi tiết hoá** phần đề bài nói mơ hồ. So sánh:

| Hạng mục | Đề bài gốc | Reviewer bổ sung |
| --- | --- | --- |
| Backend-1 | "scheduling semantics", "receipt lifecycle", "HITL orchestration" | + `ProcessingScheduler` semantics, application queue adapter, processing job payload, **worker handler/orchestration**, retry/idempotency/business failure semantics |
| Backend-2 | "persistence implementation", "storage abstraction/adapters", "repository/application service" | (giữ nguyên, chỉ diễn đạt gọn hơn) |
| DevOps | "Redis runtime", "service health", "environment/runtime configuration" | + **worker container/process**, broker configuration, networking, logs/runtime visibility |

Giá trị thật của bản làm rõ này nằm ở chỗ nó tách bạch được thứ mà đề bài gốc để lửng: **ai sở hữu "worker"?**

- DevOps sở hữu **worker container/process** — Dockerfile, broker config, healthcheck, log visibility. (Đúng những gì tôi đã làm.)
- Backend-1 sở hữu **worker handler/orchestration** — task nào chạy, xử lý gì, retry ra sao. (Đúng những gì tôi cố tình không làm.)

Đây chính xác là ranh giới tôi đã áp dụng trong implementation, chỉ là chưa diễn đạt rõ bằng chữ. Nên adopt wording này vào tài liệu.

### Điểm 4 — "Healthcheck `/openapi.json` là non-blocking follow-up"

**Trạng thái: ✅ ĐÚNG, và tài liệu hiện tại đã ghi đúng như vậy rồi.**

Reviewer nói 3 ý, cả 3 đều khớp với những gì đã có trong `docs/implementation-notes.md`:

1. Chấp nhận `/openapi.json` cho giai đoạn infrastructure foundation → đã ghi.
2. Khi Backend có `/healthz` canonical thì chuyển sang → đã ghi rõ *"When Backend ships `/healthz`, the healthcheck in `docker-compose.yml` should switch to it"*.
3. **Không tạo fake business/API endpoint trong DevOps PR chỉ để phục vụ healthcheck** → đã tuân thủ; tôi không thêm route nào vào `backend/app/`.

Điểm duy nhất cần bổ sung: gắn nhãn **"non-blocking"** cho rõ, để không ai hiểu nhầm đây là nợ kỹ thuật chặn merge.

### Điểm 5 — Verdict "TECHNICALLY APPROVED, chỉ cần dọn tài liệu"

**Trạng thái: ✅ HỢP LÝ**, với điều kiện điểm 1 được xác nhận.

Câu chốt *"Không thêm feature ngoài scope vào PR này"* là lời nhắc tốt và trùng với nguyên tắc đã áp dụng xuyên suốt: PR này không đụng vào business logic, không thêm endpoint, không implement task Celery.

---

## Kết luận

| Điểm | Đánh giá | Hành động | Trạng thái |
| --- | --- | --- | --- |
| 1. CI Done | ✅ Branch owner đã xác nhận CI xong | Sửa Partial → Done | ✅ Đã áp dụng |
| 2. Worker không phải blocker | ✅ Đúng, docs đang sai | Chuyển sang follow-up Issue #21 | ✅ Đã áp dụng |
| 3. Ownership wording | ✅ Đúng, tốt hơn bản gốc | Adopt vào tài liệu | ✅ Đã áp dụng |
| 4. Healthcheck follow-up | ✅ Đúng, docs đã khớp | Thêm nhãn "non-blocking" | ✅ Đã áp dụng |
| 5. Verdict | ✅ Hợp lý | — | — |

**Cả 5 điểm đã được xử lý.**

Nhận xét chung: đây là review có chất lượng. Reviewer bắt đúng một lỗi phân loại thật trong tài liệu (điểm 2) — một việc thuộc task khác bị xếp vào danh sách "còn nợ" của task này, khiến W1 trông như chưa xong trong khi thực chất đã xong. Ba điểm còn lại là làm rõ và xác nhận, không phải sửa lỗi.

---

## Đã áp dụng vào đâu (2026-08-17)

| File | Thay đổi |
| --- | --- |
| `docs/report.md` | Mục 8 CI: Partial → Done; mục 6 thêm nhãn follow-up non-blocking cho healthcheck; mục 10 thêm bảng ownership 3 bên; DoD 13/14 → **14/14**; thêm mục "Không thuộc DoD (follow-up, không blocking)" |
| `docs/devops-delivery-checklist.md` | Bỏ định nghĩa `Partial` ở phần mở đầu; mục 6 và 8 cập nhật; thêm section "Ownership boundary"; đổi "Still required" → "**Follow-up work (not blocking this task)**" |
| `docs/devops-w1-branch-report.md` | DoD mục 12 và 14 → ✅, kết luận **14/14**; mục 4 đổi thành "đã hoàn thành, không còn việc treo" + tách follow-up; mục 6 thêm bảng ownership và khẳng định skeleton đã đủ cho W1 |
| `docs/implementation-notes.md` | Đổi tiêu đề "Worker: still not a real integration" → "**Worker: skeleton is the W1 deliverable, not a placeholder debt**"; thêm ownership split container/process vs handler/orchestration |

### Lưu ý về evidence CI

Tài liệu hiện ghi "đã có successful workflow run" dựa trên **xác nhận của branch owner**, không kèm URL cụ thể vì tôi không truy cập được GitHub (`gh` chưa auth) nên không thể tự lấy link. **Cần dán link run thật vào PR description** — dạng:

```text
https://github.com/vietreceipt-team/vietreceipt/actions/runs/<run_id>
```

Không nên để tài liệu khẳng định CI xanh mà thiếu link đối chứng khi PR đi vào merge review.

---

## Tài liệu liên quan

- [docs/report.md](report.md) — báo cáo theo khung đề bài W1
- [docs/devops-w1-branch-report.md](devops-w1-branch-report.md) — báo cáo chi tiết theo nhánh
- [docs/devops-delivery-checklist.md](devops-delivery-checklist.md) — checklist bàn giao
- [docs/implementation-notes.md](implementation-notes.md) — quyết định kỹ thuật và trade-off
