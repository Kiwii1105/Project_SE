# Chạy lại 16 ca kiểm thử EduMate

Dev cần một checkout EduMate có thư mục `src` và Python đã cài các gói trong `src/requirements.txt`. Nếu máy chưa cài, chạy từ thư mục gốc checkout:

```sh
python -m pip install -r src/requirements.txt
```

Nếu bộ QA nằm cùng repo, chạy lệnh sau từ thư mục gốc:

```sh
python docs/test/reports/2026-11-23-logic-qa/replay/run.py
```

Nếu nhận ZIP, giải nén rồi chạy từ thư mục `EduMate-QA-Replay`:

```sh
python replay/run.py --repo "/duong-dan/Project_SE"
```

Thay đường dẫn bằng thư mục gốc checkout của dev. Trên Windows, có thể dùng `py -3` thay `python` nếu máy dùng Python Launcher.

Trang [EduMate QA](http://127.0.0.1:5080/__qa/) tự mở. **Bấm một mã QA** để chạy ca đó. Mỗi lượt tạo dữ liệu mới trong RAM. Ca API và unittest hiện bảng kết quả vừa chạy. Ca giao diện mở EduMate, tự thao tác rồi ghi lại kết quả trên màn hình. Các ảnh minh chứng cũ nằm ở [thư mục ảnh](../evidence/README.md).

- **Đã tái hiện hành vi** nghĩa là checkout hiện tại cho ra kết quả đã báo. Với QA-02, QA-06 và QA-07, đối chiếu quy tắc với BA trước khi chốt lỗi.
- **Không tái hiện trên checkout này** nghĩa là lượt chạy không cho ra hành vi đã báo. Dùng dòng kết quả để đối chiếu khi retest.
- **Không chạy được ca kiểm thử** cho biết thiếu điều kiện hoặc giao diện đã đổi làm ca không tìm được thao tác. QA-05 chạy trực tiếp test `test_app.ApiTests.test_config_endpoint` trong checkout.

Bộ này chạy trên địa chỉ `127.0.0.1` với tài khoản và dữ liệu mẫu. Các lỗi ghi dữ liệu, phản hồi chậm và thao tác đồng thời được mô phỏng theo từng ca. Dùng commit `0f47905` để đối chiếu kết quả ban đầu hoặc checkout chứa bản sửa để chạy lại. Dừng bằng **Ctrl+C**. Nếu cổng 5080 bận, thêm `--port 5081` và dùng URL mà lệnh in ra.
