"""EduMate QA fixtures and cases. Every fixture uses a fresh MemoryStore."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import timedelta
from threading import Barrier, BrokenBarrierError
from unittest.mock import patch
import os
import re
import subprocess
import sys

from flask import g

import app as edu
from store import MemoryStore

ACTIVE_STORE = ContextVar("active_qa_store", default=None)
LONG_ASSIGNMENT = "BaiTap-" + "W" * 113
LONG_QUESTION = "CauHoi-" + "W" * 143


class ScopedStore:
    def __getattr__(self, name):
        store = ACTIVE_STORE.get()
        return getattr(store if store is not None else g.qa_store, name)


@dataclass
class Result:
    reproduced: bool
    facts: dict
    role: str = ""
    tab: str = ""


@dataclass
class Screen:
    role: str
    course_id: str = ""
    deadline_id: str = ""


class Fixture:
    def __init__(self):
        self.store = MemoryStore()
        for uid, name, role in [
            ("a", "Giảng viên A", "lecturer"),
            ("b", "Giảng viên B", "lecturer"),
            ("s", "Sinh viên QA", "student"),
        ]:
            self.store.create("users", uid, {
                "name": name, "email": f"{uid}@example.test", "role": role,
            })

    def request(self, uid, method, path, **fields):
        context = ACTIVE_STORE.set(self.store)
        try:
            client = edu.app.test_client()
            with client.session_transaction() as session:
                session["uid"] = uid
            return client.open("/api" + path, method=method, json=fields or None)
        finally:
            ACTIVE_STORE.reset(context)

    def expect(self, uid, method, path, status, **fields):
        response = self.request(uid, method, path, **fields)
        if response.status_code != status:
            raise RuntimeError(f"Dữ liệu mẫu: {method} {path} trả {response.status_code}, cần {status}.")
        return response.get_json()

    def course(self, uid, code, name):
        return self.expect(uid, "POST", "/courses", 201, code=code, name=name)["id"]

    def lesson(self, uid, course, start, end, weekday=0):
        return self.request(uid, "POST", f"/courses/{course}/sessions",
                            weekday=weekday, start=start, end=end, room="B12")

    def seed_lesson(self, uid, course, start, end):
        if self.lesson(uid, course, start, end).status_code != 201:
            raise RuntimeError("Không tạo được buổi học mẫu.")

    def enroll(self, course):
        self.expect("s", "POST", f"/courses/{course}/enroll", 201)

    def deadline(self, course, title, kind="assignment", days=2):
        due = (edu.now_vn() + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M")
        return self.request("a", "POST", f"/courses/{course}/deadlines",
                            title=title, kind=kind, due_at=due), due

    def deadlines(self):
        return self.expect("s", "GET", "/deadlines", 200)["deadlines"]

    def question(self, course, title="Giảng viên cho em hỏi về hạn nộp"):
        self.expect("s", "POST", f"/courses/{course}/questions", 201,
                    title=title, body="Dữ liệu câu hỏi mẫu.")
        questions = self.store.where("questions", course_id=course)
        return next(question["id"] for question in questions if question["title"] == title)

    def timetable(self, uid):
        day = self.expect(uid, "GET", "/timetable", 200)["days"][0]
        return [f"{s['course_code']} · {s['start']}–{s['end']}" for s in day]


def shared_overlap(f):
    own = f.course("b", "QA101", "Môn riêng của giảng viên B")
    shared = f.course("a", "QA102", "Môn đồng phụ trách")
    f.seed_lesson("b", own, "08:00", "09:00")
    f.expect("b", "POST", f"/courses/{shared}/teach", 201)
    response = f.lesson("a", shared, "08:30", "09:30")
    schedule = f.timetable("b")
    return Result(response.status_code == 201 and len(schedule) == 2, {
        "Buổi mới": "Thứ Hai 08:30–09:30",
        "HTTP khi thêm": response.status_code,
        "Lịch thứ Hai của B": schedule,
        "Kỳ vọng": "HTTP 409; lịch của B chỉ có QA101.",
    }, "b", "timetable")


def fractional_day(f):
    course = f.course("a", "QA102", "Môn thử giá trị thứ")
    response = f.lesson("a", course, "08:00", "09:00", weekday=0.5)
    sessions = f.store.where("class_sessions", course_id=course)
    stored = sessions[0]["weekday"] if sessions else None
    return Result(response.status_code == 201 and stored == 0, {
        "Giá trị gửi": 0.5,
        "HTTP khi thêm": response.status_code,
        "Thứ lưu trong dữ liệu": stored,
        "Kỳ vọng trong bộ test": "Từ chối giá trị không nguyên. Cần BA chốt quy tắc.",
    })


def failed_delete(f):
    course = f.course("a", "QA102", "Môn thử xóa bài")
    f.enroll(course)
    title = "Bài tập bị mất dấu hoàn thành"
    response, _ = f.deadline(course, title)
    if response.status_code != 201:
        raise RuntimeError("Không tạo được bài tập mẫu.")
    task = f.deadlines()[0]
    f.expect("s", "POST", f"/deadlines/{task['id']}/done", 200, done=True)
    before = f.deadlines()[0]["done"]
    delete = f.store.delete

    def fail_at_deadline(collection, doc_id):
        if collection == "deadlines" and doc_id == task["id"]:
            raise RuntimeError("QA mô phỏng lỗi ghi khi xóa deadline")
        return delete(collection, doc_id)

    with patch.object(f.store, "delete", side_effect=fail_at_deadline), patch.object(edu.app, "log_exception"):
        failed = f.request("a", "DELETE", f"/deadlines/{task['id']}")
    remaining = f.deadlines()
    current = next((item for item in remaining if item["id"] == task["id"]), None)
    return Result(failed.status_code == 500 and before and current is not None and not current["done"], {
        "Đã tick trước khi xóa": before,
        "HTTP khi xóa": failed.status_code,
        "Bài vẫn tồn tại": current is not None,
        "Đã tick sau khi xóa lỗi": current["done"] if current else None,
        "Kỳ vọng": "Xóa thất bại thì dấu hoàn thành vẫn còn.",
    }, "s", "deadlines")


def contaminated_test(_):
    domain = "edumate-team.example.test"
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("FIREBASE_")}
    env.update(FIREBASE_AUTH_DOMAIN=domain, PYTHON_DOTENV_DISABLED="1")
    output = subprocess.run(
        [sys.executable, "-m", "unittest", "-v", "test_app.ApiTests.test_config_endpoint"],
        cwd=edu.BASE_DIR, env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=20,
    )
    match = re.search(r"^AssertionError: Tuples differ: .*$", output.stderr, re.MULTILINE)
    reproduced = output.returncode != 0 and match is not None and domain in match[0]
    if output.returncode and not reproduced:
        raise RuntimeError("Unittest dừng vì lỗi khác. Kiểm tra test_app.ApiTests.test_config_endpoint.")
    return Result(reproduced, {
        "Lệnh": "unittest test_app.ApiTests.test_config_endpoint",
        "Domain thử": domain,
        "Kết quả": "FAIL · assertion dùng domain thử" if reproduced else "PASS",
        "Assertion": match[0] if match else "Không có assertion thất bại.",
    })


def past_exam(f):
    course = f.course("a", "QA102", "Môn thử kỳ thi quá hạn")
    f.enroll(course)
    response, due = f.deadline(course, "Kỳ thi thử với hạn đã qua", kind="exam", days=-7)
    deadline = next(iter(f.deadlines()), None)
    return Result(response.status_code == 201 and bool(deadline) and deadline["status"] == "overdue", {
        "Hạn mới nhập (giờ Việt Nam)": due,
        "HTTP khi tạo": response.status_code,
        "Nhãn ở tài khoản sinh viên": "Quá hạn" if deadline and deadline["status"] == "overdue" else None,
        "Yêu cầu cần đối chiếu": "BR-06, có cho tạo kỳ thi với hạn trong quá khứ không.",
    }, "s", "deadlines")


def schedule_changed(f):
    one = f.course("b", "QA101", "Môn có lịch trước")
    two = f.course("a", "QA104", "Môn thêm lịch sau đăng ký")
    f.seed_lesson("b", one, "08:00", "09:00")
    f.enroll(one)
    f.enroll(two)
    before = f.timetable("s")
    response = f.lesson("a", two, "08:05", "08:25")
    after = f.timetable("s")
    return Result(response.status_code == 201 and len(after) == 2, {
        "Lịch sinh viên trước khi thêm": before,
        "HTTP khi thêm": response.status_code,
        "Lịch sinh viên sau khi thêm": after,
        "Ghi chú": "README dự án ghi nhận thiếu cảnh báo khi lịch thay đổi.",
    }, "s", "timetable")


def question_limit(f):
    course = f.course("a", "QA106", "Môn kiểm tra 101 câu")
    f.enroll(course)
    title = "Câu 001 · Vẫn chờ giảng viên trả lời"
    first = f.question(course, title)
    for count in range(2, 102):
        question = f.question(course, f"Câu {count:03} · Đã có phản hồi")
        f.expect("a", "POST", f"/questions/{question}/answers", 201, body="Giảng viên đã phản hồi.")
    displayed = f.expect("a", "GET", f"/questions?course_id={course}", 200)["questions"]
    missing = all(item["id"] != first for item in displayed)
    return Result(missing and len(displayed) == 100 and all(item["answers"] for item in displayed), {
        "Số câu lưu trong dữ liệu": len(f.store.where("questions", course_id=course)),
        "Số câu API trả về": len(displayed),
        "Câu chưa trả lời còn trong dữ liệu": not f.store.get("questions", first)["answers"],
        "Câu đó bị ẩn": missing,
    }, "a", "qa")


def parallel(f, role):
    uid = "s" if role == "student" else "a"
    first = f.course("a", "QA101", "Môn thứ nhất")
    second = f.course("b" if role == "student" else "a", "QA102", "Môn thứ hai")
    if role == "student":
        f.seed_lesson("a", first, "08:00", "09:00")
        f.seed_lesson("b", second, "08:30", "09:30")

        def attempt(course, start, end):
            return f.request("s", "POST", f"/courses/{course}/enroll").status_code

        collection, method = "enrollments", "create"
    else:
        def attempt(course, start, end):
            return f.lesson("a", course, start, end).status_code

        collection, method = "class_sessions", "add"

    checkpoint = Barrier(2, timeout=4)
    write = getattr(f.store, method)

    def synchronized_write(group, *args):
        if group == collection:
            try:
                checkpoint.wait()
            except BrokenBarrierError:
                pass  # A fixed implementation may serialize the requests.
        return write(group, *args)

    with patch.object(f.store, method, side_effect=synchronized_write), ThreadPoolExecutor(2) as workers:
        left = workers.submit(attempt, first, "08:00", "09:00")
        right = workers.submit(attempt, second, "08:30", "09:30")
        statuses = [left.result(timeout=8), right.result(timeout=8)]
    schedule = f.timetable(uid)
    if any(status >= 500 for status in statuses):
        raise RuntimeError("Một yêu cầu đồng thời trả 5xx. Cần xem log Flask để đối chiếu.")
    return Result(statuses == [201, 201] and len(schedule) == 2, {
        "HTTP hai yêu cầu đồng thời": statuses,
        "Lịch thứ Hai sau khi gửi": schedule,
        "Kỳ vọng": "Chỉ lưu một buổi; yêu cầu còn lại nhận HTTP 409.",
        "Mô phỏng": "Đồng bộ hai yêu cầu ngay trước khi lưu vào RAM.",
    }, uid, "timetable")


def ui_fixture(f, case):
    if case == "QA-12":
        return Screen("s", f.course("a", "QA105", "Môn thử bấm đúp đăng ký"))

    course = f.course("a", "QA102", "Môn thử giao diện")
    f.enroll(course)
    if case in {"QA-09", "QA-13"}:
        f.seed_lesson("a", course, "08:30", "09:30")
    if case in {"QA-07", "QA-09"}:
        question = f.question(course)
        if case == "QA-07":
            f.expect("s", "POST", f"/questions/{question}/answers", 201,
                     body="Em bổ sung nội dung. Giảng viên chưa phản hồi.")
    if case in {"QA-11", "QA-17"}:
        title = LONG_ASSIGNMENT if case == "QA-17" else "Bài tập thử đánh dấu nhanh"
        response, _ = f.deadline(course, title)
        if response.status_code != 201:
            raise RuntimeError("Không tạo được bài tập mẫu.")
        if case == "QA-17":
            f.question(course, LONG_QUESTION)
        return Screen("s", course, f.deadlines()[0]["id"])
    return Screen("a" if case in {"QA-07", "QA-08", "QA-13"} else "s", course)


CASES = {
    "QA-01": ("Trùng lịch giảng viên đồng phụ trách", shared_overlap),
    "QA-02": ("API lưu thứ 0.5 thành thứ Hai", fractional_day),
    "QA-03": ("Xóa deadline lỗi làm mất dấu hoàn thành", failed_delete),
    "QA-05": ("Unittest đọc lẫn cấu hình Firebase", contaminated_test),
    "QA-06": ("Tạo kỳ thi với hạn đã qua", past_exam),
    "QA-07": ("Sinh viên phản hồi làm câu hỏi hết chờ", None),
    "QA-08": ("Thêm kỳ thi báo đã thêm bài tập", None),
    "QA-09": ("Chuyển nhanh làm hiện nhầm nội dung tab", None),
    "QA-10": ("Thêm lịch sau đăng ký làm sinh viên trùng giờ", schedule_changed),
    "QA-11": ("Bỏ tick nhưng bài tự tick lại", None),
    "QA-12": ("Bấm đúp đăng ký gửi hai yêu cầu", None),
    "QA-13": ("Báo trùng lịch rồi xóa trắng form", None),
    "QA-14": ("Bỏ sót câu chưa trả lời ngoài 100 câu mới", question_limit),
    "QA-15": ("Đăng ký đồng thời hai môn trùng lịch", lambda f: parallel(f, "student")),
    "QA-16": ("Thêm đồng thời hai buổi dạy trùng lịch", lambda f: parallel(f, "lecturer")),
    "QA-17": ("Tiêu đề dài làm tràn ngang trang", None),
}
