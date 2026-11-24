# Kiểm thử logic EduMate

**Tester** · Duy Phuoc  
**Ghi nhận ban đầu** · 19/11/2026  
**Commit đối chiếu** · `0f47905`

## Phạm vi và môi trường kiểm thử

Đợt kiểm thử tập trung vào các chức năng sau đăng nhập của sinh viên và giảng viên, gồm đăng ký và quản lý môn học, xem thời khóa biểu, theo dõi bài tập và kỳ thi, hỏi đáp và đăng xuất.

Các ca kiểm thử chức năng chạy trên bản EduMate cục bộ dùng Flask, với tài khoản mẫu và dữ liệu lưu trong RAM.

| Lượt chạy | Kết quả |
| --- | --- |
| Bộ unittest trên `0f47905` | 12/12 pass trong môi trường sạch. |
| Bộ test mở rộng của nhóm | 55/58 pass. Ba ca fail là QA-01, QA-02 và QA-03 bên dưới. |
| Giao diện cục bộ | Kiểm tra học phần, thời khóa biểu, bài tập và kỳ thi, hỏi đáp, đăng xuất. Hai hành vi cần đối chiếu với yêu cầu được ghi ở TC-17 và TC-18. |
| Kiểm thử tải cục bộ | 50 người dùng giả, 50 môn học, 600 request, 0 lỗi. P95 của danh sách môn, lịch, deadline và đăng ký lần lượt là 59,5 ms, 42,0 ms, 45,0 ms và 44,1 ms. |
| Bản Render | Trang đăng nhập hoạt động. Đăng nhập thành công và đọc/ghi Firestore thực tế chưa kiểm tra được vì Firebase từ chối hai tài khoản demo trong README của dự án. |

## Lỗi và hành vi cần rà soát

> **Lưu ý.** QA-05 đã có bản sửa và kết quả kiểm thử lại. QA-02, QA-06 và QA-07 cần BA xác nhận quy tắc nghiệp vụ trước khi chốt lỗi.

**16 ca** ghi nhận lỗi hoặc hành vi quan sát được trên commit `0f47905`. Các ca chạy cục bộ, trừ khi ghi rõ môi trường khác. [Xem ảnh và video minh chứng kèm chú thích](evidence/README.md).

| Mã | Lỗi hoặc hành vi | Cách tái hiện | Thực tế | Mong đợi hoặc trạng thái | Minh chứng | Chi tiết |
| --- | --- | --- | --- | --- | --- | --- |
| QA-01 | Giảng viên đồng phụ trách bị trùng lịch | B dạy thứ Hai 08:00–09:00. B nhận phụ trách môn của A khi môn chưa có lịch. A thêm buổi 08:30–09:30 vào môn chung. Mở lịch của B. | API trả `201`. Lịch B có hai buổi chồng nhau 30 phút. | Từ chối lưu với `409` và báo lịch của giảng viên bị trùng. [Mã nguồn](https://github.com/Kiwii1105/Project_SE/blob/0f47905/src/app.py#L430-L453) | [Ảnh](evidence/QA-01.jpg) | Khi thêm buổi vào môn có nhiều giảng viên, hệ thống chỉ đối chiếu lịch của người đang thao tác. Vì lịch của giảng viên đồng phụ trách chưa được kiểm tra, buổi mới có thể làm lịch của họ bị trùng dù lịch người thêm vẫn hợp lệ. |
| QA-02 | API tự đổi số thập phân thành thứ Hai | Gửi yêu cầu thêm buổi hợp lệ về giờ với `weekday=0.5`. | API trả `201`, lưu `weekday=0` và hiển thị thứ Hai. Form web chỉ có danh sách thứ có sẵn. | Bộ test mong đợi `400` và không lưu. BA cần chốt quy tắc nhận số nguyên cho API. | [Thẻ kết quả gửi và lưu thứ](evidence/QA-02.jpg) | API chuyển `weekday` sang số nguyên trước khi kiểm tra khoảng từ 0 đến 6. Phần thập phân của `0.5` bị bỏ, nên giá trị đã đổi thành `0` và qua kiểm tra. BA cần xác nhận đầu vào có bắt buộc là số nguyên hay không. |
| QA-03 | Giảng viên xóa deadline thất bại, sinh viên mất dấu hoàn thành | Sinh viên mở mục **Bài tập** và đánh dấu một deadline là **Đã hoàn thành**. Sau đó, giảng viên yêu cầu xóa đúng deadline này. Bài kiểm thử mô phỏng lỗi ở bước xóa bản ghi deadline. Cuối cùng, kiểm tra lại danh sách bài tập của sinh viên. | Yêu cầu xóa trả `HTTP 500`. Sinh viên vẫn thấy deadline trong danh sách, nhưng ô hoàn thành đã mất dấu tick dù sinh viên chưa bỏ chọn. | Nếu yêu cầu xóa thất bại, deadline vẫn phải xuất hiện và sinh viên vẫn phải thấy dấu **Đã hoàn thành**. | [Thẻ kết quả trước và sau lỗi xóa](evidence/QA-03.jpg) | EduMate xóa bản ghi đánh dấu hoàn thành của sinh viên trước, rồi mới xóa bản ghi deadline. Lỗi mô phỏng xảy ra ở bước thứ hai. Deadline vì thế vẫn được lưu, còn dấu hoàn thành đã bị xóa ở bước trước và không được khôi phục. |
| QA-05 | Unittest đọc lẫn cấu hình Firebase thật | Trên bản gốc, đặt `FIREBASE_AUTH_DOMAIN` khác domain test rồi chạy `test_config_endpoint`. | Ca test fail vì API trả domain từ môi trường. | Đã push bản sửa. | [Thẻ kết quả unittest trước bản sửa](evidence/QA-05.jpg) | Trên bản gốc, unittest đặt API key và project ID mẫu nhưng vẫn đọc `FIREBASE_AUTH_DOMAIN` từ môi trường. Khi domain này khác `edumate-test.firebaseapp.com`, `test_config_endpoint` báo fail. Bản sửa đặt `FIREBASE_AUTH_DOMAIN` thành domain giả trong `src/test_app.py` trước khi import `app`. Commit đã được push lên nhánh `test/isolate-firebase-auth-domain`. [Commit `f4efa15`](https://github.com/Kiwii1105/Project_SE/commit/f4efa152b54c8acc56ab352e9a9af2e6d2a0fb2a) **Kiểm thử lại ngày 24/11/2026.** Cả hai lần chạy đạt **12/12 unittest**, gồm một lần với môi trường sạch và một lần đặt sẵn domain giả `qa-fixture.invalid` để mô phỏng cấu hình từ `.env` của nhóm. |
| QA-06 | Cho tạo kỳ thi với hạn đã qua | Ngày 23/11/2026, giảng viên tạo kỳ thi có hạn 16/11/2026 lúc 10:00. | Hệ thống lưu và sinh viên thấy kỳ thi mới mang nhãn **Quá hạn**. | Cần đối chiếu BR-06. Nếu hạn mới bắt buộc ở tương lai, form phải từ chối lưu. | [Ảnh](evidence/QA-06.jpg) | Khi tạo kỳ thi, hệ thống đọc và chuẩn hóa ngày giờ rồi lưu. Danh sách của sinh viên so hạn với giờ hiện tại nên kỳ thi vừa tạo đã mang nhãn **Quá hạn**. BA cần xác nhận BR-06 có cho nhập hạn trong quá khứ hay không. |
| QA-07 | Sinh viên tự phản hồi làm câu hỏi hết chờ | Sinh viên đặt câu hỏi rồi tự gửi thêm một phản hồi. Giảng viên mở Hỏi đáp trước khi trả lời. | Chỉ có phản hồi của sinh viên nhưng giao diện báo **Đã trả lời hết**. | Theo cách hiểu BR-09 trong test plan, chỉ phản hồi của giảng viên phụ trách mới đổi trạng thái. Cần BA xác nhận quy tắc. | [Ảnh](evidence/QA-07.jpg) | Chỉ báo **Chưa trả lời** dựa vào số phản hồi, nên một tin nhắn bổ sung do chính sinh viên gửi cũng làm chỉ báo biến mất. BA cần xác nhận theo BR-09 vai trò nào được tính là đã trả lời. |
| QA-08 | Thông báo sai loại khi tạo kỳ thi | Giảng viên chọn loại **Kỳ thi** và thêm thành công. | Mục mới lưu đúng loại kỳ thi, thông báo lại ghi **Đã thêm bài tập**. | Thông báo dùng đúng loại đã tạo. | [Ảnh](evidence/QA-08.jpg) | Giá trị **Kỳ thi** đã được lưu đúng. Cả hai loại dùng chung thao tác thêm, và giao diện luôn dùng câu **Đã thêm bài tập** sau khi lưu thành công. Thông báo khiến giảng viên dễ hiểu nhầm loại vừa tạo. |
| QA-09 | Chuyển tab nhanh làm hiện sai nội dung | Làm chậm phản hồi Hỏi đáp 2,5 giây. Bấm **Hỏi đáp** rồi chuyển ngay sang **Thời khóa biểu**. | Lịch hiện trước, sau đó nội dung **Đặt câu hỏi** ghi đè dù tab **Thời khóa biểu** vẫn được chọn. Tái hiện hai lần. | Nội dung khớp tab đang chọn khi phản hồi về. [Mã nguồn](https://github.com/Kiwii1105/Project_SE/blob/0f47905/src/static/index.html#L438-L441) | [Ảnh](evidence/QA-09.jpg) · [Video](evidence/QA-09.mp4) | Mỗi lần chọn tab bắt đầu tải nội dung riêng. Khi phản hồi Hỏi đáp về sau, nó vẫn ghi vào vùng nội dung dù người dùng đã chọn Thời khóa biểu. Vì vậy tab được tô sáng và nội dung bên dưới có thể lệch nhau. |
| QA-10 | Lịch sinh viên chồng nhau sau khi đã đăng ký | Sinh viên đăng ký QA101 có lịch thứ Hai 08:00–09:00 và QA104 khi môn chưa có lịch. Sau đó giảng viên thêm QA104 từ 08:05 đến 08:25 cùng ngày. | Cả hai buổi xuất hiện trên lịch sinh viên, không có cảnh báo trùng. | Cảnh báo người bị ảnh hưởng. Đây là hạn chế đã ghi trong README dự án. | [Ảnh](evidence/QA-10.jpg) | Lịch được đối chiếu khi sinh viên đăng ký môn. Nếu giảng viên thêm buổi sau đó, bước thêm buổi kiểm tra lịch dạy của người thao tác mà chưa kiểm tra lịch của các sinh viên đã đăng ký. Hai môn từng đăng ký hợp lệ vì thế có thể phát sinh trùng giờ. |
| QA-11 | Bỏ tick nhanh nhưng vẫn lưu hoàn thành | Mô phỏng lần lưu tick bị chậm, rồi tick và bỏ tick ngay trên cùng bài tập. | Ô tự được tick lại khi phản hồi về và vẫn được tick sau khi tải lại trang. | Thao tác cuối là bỏ tick, nên trạng thái phải là chưa hoàn thành. | [Ảnh](evidence/QA-11.jpg) · [Video](evidence/QA-11.mp4) | Hai thao tác tick và bỏ tick gửi hai yêu cầu riêng. Ca thử làm chậm yêu cầu tick nên yêu cầu bỏ tick được xử lý trước. Khi yêu cầu tick xử lý xong, nó lưu đè lựa chọn cuối của sinh viên. |
| QA-12 | Bấm đúp Đăng ký gửi hai yêu cầu | Với phản hồi chậm, bấm đúp **Đăng ký** trên QA105. | Chỉ một đăng ký được tạo. Thẻ môn hiện **Đã đăng ký**, sau đó giao diện hiện thông báo trùng từ yêu cầu thứ hai. | Một thao tác đăng ký đang chờ chỉ gửi một yêu cầu và hiển thị một kết quả nhất quán. | [Ảnh](evidence/QA-12.jpg) | Nút **Đăng ký** vẫn nhận lần bấm thứ hai trong lúc lần đầu đang xử lý. API chặn bản ghi trùng, nhưng hai phản hồi làm sinh viên thấy trạng thái **Đã đăng ký** cùng với thông báo lỗi. |
| QA-13 | Form xóa các ô sau khi báo trùng lịch | QA102 đã có buổi thứ Hai 08:30–09:30. Nhập 08:45–09:15, phòng B12 và bấm **Thêm buổi học**. | Báo trùng lịch đúng, sau đó xóa giờ bắt đầu, giờ kết thúc và phòng. | Giữ nội dung để giảng viên chỉnh giờ rồi gửi lại. | [Trước](evidence/QA-13-before.jpg) · [Sau](evidence/QA-13.jpg) | API trả `409` vì giờ dạy bị trùng. Sau khi báo lỗi, giao diện dựng lại nội dung của tab và tạo form mới với các ô mặc định. Giảng viên phải nhập lại cả dữ liệu vốn hợp lệ, chẳng hạn phòng học. |
| QA-14 | Hỏi đáp bỏ sót câu chưa trả lời khi vượt 100 câu | Tạo một câu cũ chưa có phản hồi, rồi tạo và trả lời 100 câu mới hơn trong cùng môn. | API trả 100 câu mới. Câu cũ vẫn còn trong dữ liệu nhưng bị ẩn, giao diện báo **Đã trả lời hết**. | Giảng viên xem được câu chưa trả lời và chỉ báo tính cả những câu ngoài phần danh sách đang hiển thị. [Mã nguồn](https://github.com/Kiwii1105/Project_SE/blob/0f47905/src/app.py#L568-L586) | [Ảnh](evidence/QA-14.jpg) | API chỉ trả 100 câu mới nhất. Giao diện đếm câu chưa trả lời trong chính danh sách nhận được, nên câu cũ nằm ngoài giới hạn vừa biến mất khỏi danh sách vừa bị bỏ khỏi chỉ báo của giảng viên. |
| QA-15 | Đăng ký đồng thời hai môn trùng giờ đều thành công | Một sinh viên đăng ký đồng thời hai môn học thứ Hai 08:00–09:00 và 08:30–09:30. Test cho cả hai yêu cầu chạy xong bước kiểm tra trước khi ghi. | Cả hai trả `201` và lên lịch. Khi gửi lần lượt, yêu cầu sau trả `409`. | Chỉ một đăng ký được lưu. Ca này tái hiện với MemoryStore, chưa chạy trên Firestore. | [Thẻ kết quả đăng ký đồng thời](evidence/QA-15.jpg) | Trong ca mô phỏng với MemoryStore, hai yêu cầu đăng ký hai môn khác nhau cùng kiểm tra trước khi yêu cầu nào kịp ghi. Cả hai đều thấy lịch còn trống. Cơ chế chặn đăng ký trùng cùng một môn vẫn hoạt động, vì hai môn ở đây tạo hai bản ghi khác nhau. |
| QA-16 | Thêm đồng thời hai buổi trùng giờ đều thành công | Một giảng viên gửi đồng thời hai yêu cầu thêm buổi 08:00–09:00 và 08:30–09:30 cùng ngày, ở hai môn mình dạy. | Cả hai trả `201` và lên lịch. Khi gửi lần lượt, yêu cầu sau trả `409`. | Chỉ một buổi được lưu. Ca này tái hiện với MemoryStore, chưa chạy trên Firestore. | [Thẻ kết quả thêm buổi đồng thời](evidence/QA-16.jpg) | Bước kiểm tra trùng giờ và bước lưu buổi dạy tách nhau. Trong ca mô phỏng với MemoryStore, hai yêu cầu của cùng giảng viên cùng vượt qua bước kiểm tra dựa trên lịch cũ, rồi mỗi yêu cầu lưu một buổi riêng. |
| QA-17 | Tiêu đề dài làm tràn ngang toàn trang | Tạo tiêu đề bài tập 120 ký tự liền nhau hoặc tiêu đề câu hỏi 150 ký tự liền nhau. Mở ở vùng hiển thị 444 px. | Bài tập kéo trang rộng tới 1.769 px, Hỏi đáp tới 2.295 px. Mã môn dài 20 ký tự vẫn hiển thị đúng. | Tiêu đề xuống dòng trong khung và chiều rộng trang không tăng. | [Ảnh](evidence/QA-17.jpg) | Tiêu đề là một chuỗi dài liền nhau và thiếu quy tắc ngắt dòng cho chuỗi đó. Trên khung hẹp, tiêu đề bài tập và câu hỏi vượt ra khỏi thẻ, làm trang phải cuộn ngang. |

Báo cáo cũ dùng QA-04 cho lỗi đăng xuất quay lại form đăng ký. Lượt này đã thử lại cả hai vai trò với Firebase mô phỏng và đều quay về form đăng nhập.

Đối chứng cho QA-15 gồm hai yêu cầu đồng thời vào cùng một môn. API trả một `201` và một `409`, chỉ lưu một bản ghi đăng ký.

## Đối chiếu toàn bộ test plan

Nhánh `main` được kiểm tra lại và vẫn trỏ tới `0f47905`. Bộ unittest trên môi trường sạch đạt **12/12**. Bộ mở rộng đạt **55/58**, với ba ca fail QA-01, QA-02 và QA-03. Các ca trình duyệt và xử lý đồng thời trong danh sách phát hiện chạy riêng, ngoài hai bộ đếm đó.

| Ca | Kết quả trên bản cục bộ |
| --- | --- |
| TC-01 · Đăng ký | Pass với Firebase mô phỏng. Tạo được cả hai vai trò và email trùng bị từ chối. |
| TC-02 · Đăng nhập | Pass với Firebase mô phỏng. Sinh viên và giảng viên đăng nhập lại đúng vai trò. Mật khẩu sai bị từ chối, tải lại giữ phiên hợp lệ. |
| TC-03, TC-03B · Đăng xuất | Pass cục bộ. Tải lại sau đăng xuất vẫn ở form đăng nhập. Lỗi cũ quay về form đăng ký sau khi đăng xuất không tái hiện ở cả hai vai trò với Firebase mô phỏng. |
| TC-04 · Danh sách môn | Pass. Danh sách hiện mã, tên, giảng viên, lịch và phòng. |
| TC-05 · Đăng ký môn | Pass luồng một lần. Bấm đúp vẫn chỉ tạo một đăng ký, nhưng hiện thêm thông báo trùng. |
| TC-06, TC-07 · Trùng lịch sinh viên và giờ liền kề | Pass khi gửi tuần tự. Giờ chồng bị chặn, buổi liền kề và khác ngày được chấp nhận. Fail khi hai yêu cầu trùng lịch cùng vượt qua bước kiểm tra. |
| TC-08 · Hủy môn | Pass. Lịch, deadline và câu hỏi của môn bị hủy biến mất khỏi tài khoản đó, dữ liệu của môn và sinh viên khác còn nguyên. |
| TC-09 · Thời khóa biểu | Pass khi gom ngày và sắp giờ, kể cả lịch trống và Chủ nhật. Có trường hợp hiển thị sai nội dung nếu chuyển tab nhanh khi phản hồi chậm. |
| TC-10, TC-11 · Deadline | Pass theo mốc 72 giờ của code hiện tại, thứ tự và phạm vi hiển thị đúng. Quy tắc ba ngày theo lịch vẫn cần đối chiếu yêu cầu. |
| TC-12 · Đánh dấu hoàn thành | Pass khi thao tác tuần tự, trạng thái tách riêng theo sinh viên. Fail khi bỏ tick ngay sau khi tick mà lần lưu đầu phản hồi chậm. |
| TC-13 · Đặt câu hỏi | Pass. Câu hỏi hiện đúng môn và tác giả, sinh viên ngoài môn bị từ chối. |
| TC-14, TC-15 · Tạo môn, thêm và xóa buổi | Pass luồng thường và phân quyền. Sinh viên thấy lịch thay đổi. Form xóa dữ liệu đã nhập khi thêm buổi bị từ chối vì trùng lịch. |
| TC-16 · Đầu vào lịch và xung đột | Pass ca cơ bản. Fail ở lịch giảng viên đồng phụ trách và khi hai buổi chồng nhau được lưu đồng thời. API đổi số thập phân thành thứ Hai, quy tắc đầu vào cần BA chốt. |
| TC-17 · Bài tập và kỳ thi | Pass luồng thêm, xóa bình thường. Fail khi mô phỏng lỗi ghi lúc xóa deadline. Hạn trong quá khứ cần đối chiếu BR-06, thông báo thêm kỳ thi dùng sai tên loại. |
| TC-18 · Phản hồi và chỉ báo | Pass khi giảng viên trả lời. Chỉ báo báo đã trả lời nếu sinh viên phản hồi, và bỏ sót câu chưa trả lời nằm ngoài 100 câu mới nhất. |
| TC-19 · Nhận và thôi phụ trách | Pass. Nhận môn bị chặn nếu đã trùng lịch, thôi phụ trách làm mất quyền chỉnh sửa. |
| TC-20 · Phân quyền API | Pass 16 ca chưa đăng nhập và 11 ca sai vai trò trong bộ mở rộng. Có ca với câu hỏi, buổi học và deadline thật trong bộ dữ liệu mẫu. |

### Môi trường và phạm vi còn thiếu

- **Bố cục.** Kiểm tra 18 tổ hợp gồm sáu màn hình ở 360, 768 và 1440 px. Với dữ liệu ngắn thông thường, không có màn hình nào làm trang tràn ngang trong trình duyệt tích hợp. Kết quả trước đó ở 390 px cũng đạt. Ca tiêu đề dài ở QA-17 chạy riêng.
- **Tải cục bộ.** 50 người dùng và 50 môn trong RAM, 600 yêu cầu, 0 lỗi trong kịch bản tải. Kịch bản tải dùng các thao tác hợp lệ và chạy riêng với các ca trùng lịch đồng thời.
- **Render và Firebase thật.** Chưa xác minh tạo tài khoản, đăng nhập bằng hai vai trò, đọc/ghi Firestore và tải trên bản triển khai. Cần tài khoản test hoạt động hoặc môi trường Firebase QA của nhóm. Bản Firefox và Edge, phép đo băng thông 10 Mbps và lượt thử với sinh viên mới chưa được chạy.
