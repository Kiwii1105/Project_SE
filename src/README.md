# EduMate (bản MVP tối giản)

Quản lý môn học, thời khóa biểu, deadline và hỏi đáp với giảng viên.
Stack: HTML/CSS/JS thuần · Flask · Firebase Authentication (đăng nhập) · Firestore (dữ liệu).

## Cài đặt Firebase (làm 1 lần)
1. **Bật đăng nhập bằng email**: Firebase Console → Authentication → Sign-in method → **Email/Password** → Enable.
2. **Lấy cấu hình web**: Project settings → General → Your apps → thêm **Web app** (`</>`) → copy `apiKey`, `projectId`, `authDomain`, `appId`.
3. **Lấy khóa Firestore**: Project settings → Service accounts → Generate new private key (đặt file JSON cạnh `app.py`, **không commit**).
4. `cp .env.example .env` rồi điền các giá trị trên. Authentication và Firestore phải thuộc **cùng một Firebase project**.
5. Khi deploy: thêm tên miền vào Authentication → Settings → Authorized domains (`localhost` có sẵn), đặt `SECRET_KEY` mạnh và `FIREBASE_CREDENTIALS_JSON` thay cho file.

## Chạy
```bash
pip install -r requirements.txt
python seed.py        # (tùy chọn) dữ liệu demo + 2 tài khoản demo trên Firebase Auth (mật khẩu 123456)
python app.py         # mở http://127.0.0.1:5000
python -m unittest -v # test, chạy bằng database RAM, không đụng Firebase thật
```

## Luồng đăng nhập
```
Trình duyệt ──(email, mật khẩu)──► Firebase Auth ──► ID token (JWT, sống 1 giờ)
Trình duyệt ──POST /api/login hoặc /api/register {id_token}──► Flask
Flask: xác minh chữ ký + hạn + audience + issuer của token ──► cookie phiên Flask
```
- Mật khẩu chỉ đi giữa trình duyệt và Firebase, backend không bao giờ thấy.
- Hồ sơ người dùng trong Firestore (`users/<firebase uid>`): `name`, `email`, `role`.
- Đăng nhập bằng tài khoản có trên Firebase nhưng chưa có hồ sơ (VD: tạo từ Console) sẽ tự tạo hồ sơ **sinh viên**.
- Trình duyệt không lưu token Firebase (`inMemoryPersistence`); phiên do cookie Flask giữ.

## Cấu trúc
```
app.py             backend: thuật toán, xác thực, API
store.py           lớp truy cập dữ liệu (Firestore / RAM)
static/index.html  toàn bộ giao diện (1 file)
seed.py            dữ liệu demo
test_app.py        test thuật toán, API, xác minh token
.env.example       mẫu cấu hình
```

## Thuật toán chính (trong app.py, phần "THUẬT TOÁN")
| Hàm | Việc làm |
|---|---|
| `overlaps`, `find_conflicts` | Hai buổi trùng nếu cùng thứ và `a.start < b.end` và `b.start < a.end`. Dùng khi sinh viên đăng ký môn và khi giảng viên thêm buổi dạy. Học liền kề không tính trùng. |
| `build_timetable` | Sắp buổi học theo (thứ, giờ bắt đầu), gom thành 7 cột. |
| `classify_deadline` | `overdue` / `today` / `soon` (≤ 3 ngày) / `upcoming`, tính theo giờ Việt Nam (UTC+7). |
| `rank_deadlines` | Việc chưa xong lên trước, sắp theo hạn tăng dần. |

Thời khóa biểu và deadline luôn **tính lại từ database mỗi lần gọi API**, nên khi giảng viên sửa
thông tin môn học thì sinh viên thấy ngay, không có dữ liệu cũ bị lệch.

## API
| Method | Đường dẫn | Quyền |
|---|---|---|
| GET | `/api/config` (cấu hình web Firebase cho trình duyệt) | — |
| POST | `/api/register` `{id_token, name, role}` · `/api/login` `{id_token}` · `/api/logout` · GET `/api/me` | — |
| GET / POST | `/api/courses` | đăng nhập / giảng viên |
| POST / DELETE | `/api/courses/<id>/teach` (nhận / thôi phụ trách một môn đã có) | giảng viên |
| POST / DELETE | `/api/courses/<id>/sessions`, `/api/sessions/<id>` | giảng viên phụ trách |
| POST / DELETE | `/api/courses/<id>/enroll` | sinh viên |
| GET | `/api/timetable`, `/api/deadlines` | đăng nhập |
| POST / DELETE | `/api/courses/<id>/deadlines`, `/api/deadlines/<id>` | giảng viên phụ trách |
| POST | `/api/deadlines/<id>/done` | sinh viên đã đăng ký |
| GET | `/api/questions?course_id=` | thành viên môn học |
| POST | `/api/courses/<id>/questions` | sinh viên đã đăng ký |
| POST | `/api/questions/<id>/answers` | sinh viên đã đăng ký hoặc giảng viên phụ trách |

## Giảng viên phụ trách môn
Một môn có thể do nhiều giảng viên phụ trách: người tạo môn (`lecturer_id`) và những người bấm
**Nhận phụ trách** (`lecturer_ids`). Giảng viên phụ trách mới xem/trả lời được câu hỏi của sinh viên và
thêm lịch học, bài tập, kỳ thi cho môn đó. Nhận môn trùng giờ với lịch dạy hiện có sẽ bị từ chối.
Các môn nạp từ `seed.py` / `load_sample.py` thuộc giảng viên demo, nên giảng viên khác cần nhận phụ trách.

## Việc nên làm tiếp
- Ai cũng tự chọn được vai trò giảng viên khi đăng ký; nên dùng mã mời hoặc duyệt, rồi chuyển vai trò sang Firebase custom claims.
- Chưa bắt xác minh email (`email_verified`) và chưa có "quên mật khẩu" (Firebase có sẵn `sendPasswordResetEmail`).
- Dữ liệu cũ trong Firestore tạo trước khi dùng Firebase Auth (collection `users` có `password_hash`, id là mã băm email) không còn dùng được: xóa đi rồi chạy lại `seed.py`.
- Khi giảng viên đổi giờ học, chưa cảnh báo những sinh viên bị trùng lịch mới.
- Tính năng mở rộng trong proposal: nhắc deadline (F06), dashboard (F07), đính kèm file (F08), LaTeX (F09).