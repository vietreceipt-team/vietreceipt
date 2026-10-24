# TV6 — kịch bản demo bảo vệ

## Phạm vi và phân công

Mục tiêu: trình diễn luồng nguồn → kết quả máy → đối chiếu → sửa → verify → export, dùng bốn file synthetic đã có. TV6 phụ trách vận hành giao diện, tài liệu và evidence. TV1 chốt thiết kế nghiên cứu; protocol/worksheet hiện là bản chuẩn bị, chưa tuyển người hoặc đo hiệu quả.

Không đổi thuật toán, thêm màn hình hoặc bật grouping variant chỉ để demo. Dùng cấu hình production mặc định của TV3/TV4; ghi đúng commit, provider và runtime của lượt chạy. Demo kỹ thuật không phải accuracy benchmark hay pilot người dùng.

## Bộ ví dụ đã chọn

| Thứ tự | File do generator tạo | Điểm cần thể hiện | Kết quả cần giữ |
|---|---|---|---|
| 1 | `photo.jpg` | Upload ảnh, chờ xử lý thật, click trường/dòng để đối chiếu nguồn | Sửa có chủ ý, verify rồi tải JSON |
| 2 | `text.pdf` | PDF có lớp chữ, nguồn và evidence đúng trang | Xem/chỉnh dòng hàng, verify rồi tải CSV ZIP |
| 3 | `scan.pdf` | PDF ảnh cần OCR; không nhầm với PDF có lớp chữ | Review, verify, tải XLSX |
| 4 | `challenge.pdf` | PDF hai trang/12 dòng, lỗi PRESENT và trường UNREADABLE | Sửa số hóa đơn, giữ trường che là UNREADABLE/null, verify/export |

Ba file đầu là ba biến thể của cùng một hóa đơn giả; challenge liên quan cũng là synthetic. Không gọi đây là bốn mẫu độc lập hoặc tập test cuối.

## Chuẩn bị trước buổi bảo vệ

1. Kiểm tra lại `main` mới nhất và cập nhật nhánh PR #68; ghi SHA đã kiểm tra trong [biên bản integration](tv6-integration-20261024.md). Chỉ dùng các PR đã merge. Nếu Backend/Reader/KIE đổi sau lượt đã kiểm chứng, chạy lại bốn ca trước khi trình diễn.
2. Dùng stack riêng theo [hướng dẫn TV5](v2-reproducible-demo.md): PostgreSQL, Redis, API, worker, beat và nguồn lưu trữ cùng môi trường. Chuẩn bị model/dependency trước buổi demo, không tải lần đầu lúc bảo vệ. Windows hiện tại chưa có Docker/Python 3.12 nên cần môi trường đã chuẩn bị; không ghi rằng stack thật đã chạy trên máy Windows này.
3. Tạo bộ file trong thư mục mới bằng Python 3.12 đã cài `backend/requirements-ai.txt` và `reportlab`:

   ```sh
   python -m scripts.create_tv6_review_demo --output .data/tv6-defense-inputs
   cd frontend
   npm ci
   npx playwright install chromium
   TV6_DEMO_ROOT=../.data/tv6-defense-inputs TV6_BACKEND_URL=http://127.0.0.1:18000 npm run test:e2e:real
   ```

   Lệnh dùng shell POSIX trên môi trường stack thật. PowerShell dùng `$env:TV6_DEMO_ROOT` và `$env:TV6_BACKEND_URL` thay cho tiền tố gán biến. Generator không ghi đè thư mục cũ; mỗi lần quay mới cần đường dẫn output mới. Sau test, chuyển nguyên thư mục `frontend/real-results` sang thư mục lưu của lượt đó trước khi chạy lại, để không mất ảnh/video.
4. Để trình diễn tương tác thủ công, mở frontend ở cổng 3103, backend 18000:

   ```sh
   FRONTEND_DATA_MODE=api BACKEND_API_ORIGIN=http://127.0.0.1:18000 node server.js --hostname 127.0.0.1 --port 3103
   ```

   Bộ test tự mở frontend 3104; không mở thêm server 3104 cùng lúc. Chuẩn bị sẵn các receipt đã xử lý để không kéo dài phần chờ, đồng thời upload mới ít nhất một file để thấy luồng thật. Chỉ dùng receipt/file synthetic của phiên demo.
5. Có bản video và các export đã tải sẵn để dùng khi mạng/dịch vụ gián đoạn. Nếu dùng video dự phòng, nói rõ đó là bản ghi của lượt có commit/provenance, không gọi là demo live.

## Lời dẫn và thao tác khoảng 6–8 phút

| Thời lượng dự kiến | Thao tác | Lời giải thích chính |
|---|---|---|
| 30 giây | Giới thiệu nguồn synthetic và phiên bản chạy | “Đây là kiểm tra luồng sử dụng; chưa phải số đo accuracy hay tiết kiệm thời gian.” |
| 1 phút | Upload JPG, quan sát trạng thái xử lý; click trường/dòng | “Giá trị có nhãn Dự đoán máy, chưa đồng nghĩa người dùng đã đối chiếu.” |
| 1 phút | Mở PDF chữ, chọn dòng, chỉnh/saving rồi verify/export CSV | “Evidence chỉ ra vị trí trên nguồn; dữ liệu chỉnh sửa đi qua backend và được giữ riêng.” |
| 1 phút | Mở PDF scan, review và xuất Excel | “Nguồn là ảnh trong PDF, xử lý bằng OCR thật.” |
| 2–3 phút | Demo challenge theo trình tự bên dưới | “Giá trị PRESENT vẫn có thể sai; không đoán nội dung không đọc được.” |
| 30–60 giây | Mở JSON/CSV/XLSX và chỉ evidence | “Bản máy ban đầu không bị ghi đè. Đây là kết quả đã được người dùng review.” |

### Ca AI đọc sai và UNREADABLE

1. Mở `challenge.pdf` **trước khi sửa**. Chọn “Chi tiết” của số hóa đơn để thấy machine PRESENT `00001234 COPY`; cùng lúc đối chiếu nguồn có ghi COPY là dấu bản sao, không thuộc số hóa đơn. Giữ ảnh `01-machine.png`.
2. Click trường để highlight nguồn. Sửa số thành `00001234`, lưu; mở inspector để thấy **Máy đọc: 00001234 COPY / Người sửa: 00001234**. Giữ ảnh `03-corrected.png`.
3. Chỉ vào ký hiệu `AA/??E` bị che. Giữ `UNREADABLE` và null, xác nhận đã đối chiếu trạng thái này; không điền ký tự suy đoán, số 0 hoặc đổi thành NOT_PRESENT. Buyer tax ID `N/A` là trường NOT_PRESENT riêng.
4. Chọn dòng hàng để viewer chuyển sang trang 2. Cho thấy 12 dòng của challenge, chỉnh một ô cần kiểm tra và lưu; giữ `04-source-row.png`.
5. Đối chiếu các mục còn lại với nguồn, chỉ xác nhận sau khi xem. Verify rồi tải JSON, CSV ZIP và XLSX. Giữ `05-verified.png`; mở export để thấy số hóa đơn đúng và ký hiệu vẫn trống với trạng thái UNREADABLE.
6. Nếu cần trình diễn 409: mở cùng receipt ở hai tab trước khi sửa; tab A lưu một trường, tab B lưu với version cũ → 409 → giữ draft → tải phiên bản mới → đối chiếu và lưu lại. Đây là ca cạnh tranh có chủ ý; không tự ghi đè hoặc tự replay. Bộ E2E đã có ảnh `02-conflict.png` và history của ca này.

## Evidence cần bàn giao

Mỗi lượt giữ một thư mục riêng có nguồn/manifest/SHA-256, commit branch và commit checkout thực tế, provider/runtime, receipt/OCR/KIE run IDs, machine-before/after, detail-before/reviewed, history, ảnh từng bước, video và ba export. Worker input hash phải khớp file đã upload; machine snapshot trước/sau phải giống nhau. Kiểm tra UNREADABLE trong cả JSON, CSV ZIP và XLSX.

Giữ nguyên [gói 23/10](verification/tv6-20261023/README.md) làm mốc cũ. Lượt integration sau #69/#70 có thư mục và index mới, không thay ngày/commit của bằng chứng cũ. Video tự động chỉ là evidence kỹ thuật, không được điền vào worksheet user study.

## Khi có lỗi hoặc thay đổi dependency

- Nếu pipeline thất bại, giữ result/failure/trace/log theo sample; không loại mẫu lỗi khỏi báo cáo hay chuyển sang fake provider để làm video.
- Nếu output mới không còn lỗi COPY, ghi nhận thay đổi và chọn một lỗi thực khác sau khi kiểm tra; không sửa machine response để tái tạo lỗi giả.
- Sau khi PR Reader #65 hoặc KIE follow-up #71 merge, chạy lại workflow trên `main` mới. Workflow có trigger push cho Backend/Reader/KIE/contracts/dependency và manual dispatch; trigger chỉ có hiệu lực trên `main` sau khi phần cấu hình trong PR #68 được merge.
- User study chỉ triển khai theo thiết kế TV1 đã chốt và consent của người tham gia; TV6 hỗ trợ đo thời gian, số sửa và xuất kết quả để chấm đúng sau review.
