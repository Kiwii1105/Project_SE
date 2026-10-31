# EduMate

Website hỗ trợ sinh viên **quản lý môn học, thời khóa biểu, bài tập / kỳ thi** và **hỏi đáp với giảng viên**.
Đồ án môn Nhập môn Công nghệ phần mềm, nhóm **SEEKers**.

- Frontend: HTML / CSS / JavaScript thuần (một file `static/index.html`)
- Backend: Python **Flask**
- Đăng nhập: **Firebase Authentication** (email + mật khẩu)
- Dữ liệu: **Cloud Firestore** (hoặc RAM khi chạy test)

## Chức năng

| Vai trò | Việc làm được |
|---|---|
| Sinh viên | Đăng ký / hủy môn học · xem thời khóa biểu tuần · xem bài tập và kỳ thi (quá hạn, hôm nay, sắp đến hạn) · đánh dấu đã làm · đặt câu hỏi và trả lời trong môn đã đăng ký |
| Giảng viên | Tạo môn học · **nhận / thôi phụ trách** môn đã có · thêm / xóa buổi học, bài tập, kỳ thi · xem và trả lời câu hỏi của sinh viên trong môn mình phụ trách |

Quy tắc chính:
- Hai buổi học **trùng giờ** nếu cùng thứ và giờ chồng lên nhau; học liền kề (hết 9:30, bắt đầu 9:30) không tính trùng. Hệ thống từ chối khi sinh viên đăng ký, giảng viên thêm buổi dạy, hoặc nhận phụ trách môn mà bị trùng.
- Một môn có thể do nhiều giảng viên phụ trách: người tạo môn và những người bấm **Nhận phụ trách**.
- Thời khóa biểu và hạn nộp luôn tính lại từ database mỗi lần gọi API, nên giảng viên sửa môn thì sinh viên thấy ngay.
- Giờ tính theo múi giờ Việt Nam (UTC+7).

## Cấu trúc thư mục

```
app.py               backend: thuật toán, xác thực, API
store.py             lớp truy cập dữ liệu (Firestore / RAM)
static/index.html    toàn bộ giao diện
seed.py              tạo 2 tài khoản demo + 3 môn mẫu
load_sample.py       nạp thêm 6 môn mẫu từ sample_data.json
sample_data.json     dữ liệu môn học, buổi học, bài tập mẫu
test_app.py          11 test (thuật toán, API, xác minh token)
requirements.txt     thư viện cần cài
.env.example         mẫu cấu hình (sao chép thành .env)
```

## Cài đặt (làm một lần)

### 1. Cài thư viện
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows;  macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Cấu hình Firebase
Authentication và Firestore phải thuộc **cùng một Firebase project**.

1. **Bật đăng nhập email**: Firebase Console → Authentication → Sign-in method → **Email/Password** → Enable.
2. **Tạo Firestore**: Build → Firestore Database → *Create database* (mode Production, chọn region, ví dụ `asia-southeast1`). Bước này bắt buộc, nếu thiếu sẽ báo lỗi *"database (default) does not exist"*.
3. **Lấy cấu hình web**: Project settings → General → Your apps → thêm **Web app** (`</>`) → copy `apiKey`, `projectId`, `authDomain`, `appId`.
4. **Lấy khóa Firestore**: Project settings → Service accounts → *Generate new private key*, đặt file JSON cạnh `app.py`. **Không commit file này.**
5. Tạo file cấu hình rồi điền các giá trị trên:
   ```bash
   cp .env.example .env
   ```

| Biến trong `.env` | Ý nghĩa |
|---|---|
| `SECRET_KEY` | Chuỗi ngẫu nhiên dài để ký cookie phiên. Đừng để trống |
| `FIREBASE_API_KEY`, `FIREBASE_PROJECT_ID`, `FIREBASE_APP_ID` | Từ cấu hình Web app |
| `FIREBASE_AUTH_DOMAIN` | Bỏ trống thì dùng `<projectId>.firebaseapp.com` |
| `FIREBASE_CREDENTIALS` | Đường dẫn file service account (khi phát triển) |
| `FIREBASE_CREDENTIALS_JSON` | Nội dung JSON của service account (khi deploy, thay cho file) |
| `EDUMATE_STORE` | `firestore` (mặc định) hoặc `memory` (chạy thử không cần Firebase) |
| `PORT`, `FLASK_DEBUG` | Cổng (mặc định 5000), `1` để bật debug |

Tạo `SECRET_KEY` ngẫu nhiên:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Chạy

```bash
python seed.py          # tạo tài khoản demo và 3 môn mẫu (CS101, MA101, PH101)
python load_sample.py   # (tùy chọn) nạp thêm 6 môn mẫu
python app.py           # mở http://127.0.0.1:5000
```

Tài khoản demo do `seed.py` tạo (mật khẩu `123456`):

| Vai trò | Email |
|---|---|
| Giảng viên | `gv@edumate.test` |
| Sinh viên | `sv@edumate.test` |

Các môn của `seed.py` và `load_sample.py` thuộc giảng viên demo. Muốn đăng nhập bằng giảng viên khác và xem câu hỏi của sinh viên, vào tab **Môn học** rồi bấm **Nhận phụ trách**. `load_sample.py` đọc email giảng viên từ trường `lecturer_email` trong `sample_data.json`, đổi thành email của bạn nếu cần. Chạy lại an toàn: môn đã có sẽ bị bỏ qua.

Chạy thử không cần Firebase (dữ liệu mất khi tắt server, đăng nhập vẫn cần Firebase):
```bash
EDUMATE_STORE=memory python app.py        # Windows PowerShell: $env:EDUMATE_STORE="memory"; python app.py
```

## Kiểm thử

```bash
python -m unittest -v
```
11 test, chạy bằng database RAM nên **không chạm vào Firebase thật**: thuật toán trùng lịch và hạn nộp, luồng API (đăng ký môn, hỏi đáp, nhận phụ trách), đăng nhập / đăng xuất, và xác minh token bằng JWT ký cục bộ.

## Luồng đăng nhập

```
Trình duyệt ──(email, mật khẩu)──► Firebase Auth ──► ID token (JWT, sống 1 giờ)
Trình duyệt ──POST /api/login hoặc /api/register {id_token}──► Flask
Flask: xác minh chữ ký, hạn, audience, issuer của token ──► cookie phiên Flask
```
- Mật khẩu chỉ đi giữa trình duyệt và Firebase, backend không bao giờ thấy.
- Hồ sơ người dùng ở Firestore: `users/<firebase uid>` gồm `name`, `email`, `role`.
- Tài khoản có trên Firebase nhưng chưa có hồ sơ (ví dụ tạo từ Console) sẽ tự được tạo hồ sơ **sinh viên** khi đăng nhập.
- Trình duyệt không lưu token Firebase (`inMemoryPersistence`); phiên do cookie Flask giữ.

## Thuật toán chính (`app.py`, phần "THUẬT TOÁN")

| Hàm | Việc làm |
|---|---|
| `overlaps`, `find_conflicts` | Hai buổi trùng nếu cùng thứ và `a.start < b.end` và `b.start < a.end` |
| `build_timetable` | Sắp buổi học theo (thứ, giờ bắt đầu), gom thành 7 cột |
| `classify_deadline` | `overdue` / `today` / `soon` (còn ≤ 3 ngày) / `upcoming`, theo UTC+7 |
| `rank_deadlines` | Việc chưa xong lên trước, sắp theo hạn tăng dần |

## API

| Method | Đường dẫn | Quyền |
|---|---|---|
| GET | `/api/config` (cấu hình web Firebase cho trình duyệt) | — |
| POST | `/api/register` `{id_token, name, role}` · `/api/login` `{id_token}` · `/api/logout` · GET `/api/me` | — |
| GET / POST | `/api/courses` | đăng nhập / giảng viên |
| POST / DELETE | `/api/courses/<id>/teach` (nhận / thôi phụ trách) | giảng viên |
| POST / DELETE | `/api/courses/<id>/sessions`, `/api/sessions/<id>` | giảng viên phụ trách |
| POST / DELETE | `/api/courses/<id>/enroll` | sinh viên |
| GET | `/api/timetable`, `/api/deadlines` | đăng nhập |
| POST / DELETE | `/api/courses/<id>/deadlines`, `/api/deadlines/<id>` | giảng viên phụ trách |
| POST | `/api/deadlines/<id>/done` | sinh viên đã đăng ký |
| GET | `/api/questions?course_id=` | thành viên môn học |
| POST | `/api/courses/<id>/questions` | sinh viên đã đăng ký |
| POST | `/api/questions/<id>/answers` | sinh viên đã đăng ký hoặc giảng viên phụ trách |

## Gỡ lỗi thường gặp

| Triệu chứng | Nguyên nhân và cách xử lý |
|---|---|
| `The database (default) does not exist` | Chưa tạo Firestore, hoặc file service account thuộc project khác. Làm bước 2 phần cài đặt, kiểm tra `FIREBASE_PROJECT_ID` |
| `no secret key was set` | `SECRET_KEY` trong `.env` bị trống. Đặt một chuỗi ngẫu nhiên |
| 401 `Thiếu id_token` khi đăng nhập | Trình duyệt đang dùng `index.html` cũ. Thay bằng bản hiện tại và tải lại bằng Ctrl+F5 |
| 401 `Token used too early` (xem log của Flask) | Đồng hồ máy lệch so với Firebase. Bật đồng bộ thời gian tự động trong Windows (Settings → Time & language → Sync now). Server cho phép lệch tối đa 60 giây |
| Danh sách môn học trống | Chưa có dữ liệu. Chạy `python seed.py` và `python load_sample.py` |
| Giảng viên không thấy câu hỏi | Giảng viên chưa phụ trách môn đó. Vào tab Môn học bấm **Nhận phụ trách** |

## Triển khai (deploy)

1. Đặt `SECRET_KEY` mạnh và `FIREBASE_CREDENTIALS_JSON` (nội dung JSON) thay cho file.
2. Thêm tên miền vào Firebase Console → Authentication → Settings → **Authorized domains** (`localhost` có sẵn).
3. Chạy bằng một WSGI server (ví dụ `gunicorn app:app`) thay vì `python app.py`.

## Hạn chế hiện tại và việc nên làm tiếp

- Ai cũng tự chọn được vai trò giảng viên khi đăng ký. Nên dùng mã mời hoặc để quản trị viên duyệt, rồi chuyển vai trò sang Firebase custom claims.
- Chưa bắt xác minh email (`email_verified`) và chưa có "quên mật khẩu" (Firebase có sẵn `sendPasswordResetEmail`).
- Dữ liệu cũ trong Firestore tạo trước khi dùng Firebase Auth (collection `users` có `password_hash`) không còn dùng được: xóa đi rồi chạy lại `seed.py`.
- Khi giảng viên đổi giờ học, chưa cảnh báo những sinh viên bị trùng lịch mới.
- Tính năng trong proposal chưa làm: nhắc deadline (F06), dashboard (F07), đính kèm file (F08), công thức LaTeX (F09).

## Nhóm thực hiện

Nhóm **SEEKers**: Lê Kiến Quốc (Developer), Nguyễn Xuân Quyên (BA), Nguyễn Hoàng Bảo Khánh (Designer), Lương Duy Phước (Tester).
