"""Tạo dữ liệu demo:  python seed.py
GHI THẬT vào Firestore VÀ tạo 2 tài khoản trong Firebase Authentication (cần FIREBASE_CREDENTIALS).
Tài khoản demo (mật khẩu đều là 123456): gv@edumate.test, sv@edumate.test
-> mật khẩu yếu, hãy xóa 2 tài khoản này trong Firebase Console trước khi deploy."""
from datetime import timedelta

from firebase_admin import auth

import app as edumate
from app import key, store


def ensure_auth_user(email, name, password="123456"):
    """Lấy uid của tài khoản Firebase Auth, tạo mới nếu chưa có."""
    try:
        return auth.get_user_by_email(email).uid
    except auth.UserNotFoundError:
        return auth.create_user(email=email, password=password, display_name=name).uid


gv = ensure_auth_user("gv@edumate.test", "GV Demo")
sv = ensure_auth_user("sv@edumate.test", "SV Demo")
if store.get("users", gv):
    raise SystemExit("Dữ liệu demo đã tồn tại.")

store.create("users", gv, {"name": "GV Demo", "email": "gv@edumate.test", "role": "lecturer"})
store.create("users", sv, {"name": "SV Demo", "email": "sv@edumate.test", "role": "student"})

courses = {}
for code, name in [("CS101", "Nhập môn lập trình"), ("MA101", "Giải tích 1"), ("PH101", "Vật lý đại cương")]:
    courses[code] = key(code)
    store.create("courses", courses[code], {"code": code, "name": name, "lecturer_id": gv})
for code, wd, a, b, room in [("CS101", 0, "07:00", "09:30", "A101"), ("CS101", 3, "13:00", "15:30", "Lab 2"),
                             ("MA101", 1, "07:00", "09:30", "B204"), ("PH101", 2, "09:30", "12:00", "C305")]:
    store.add("class_sessions", {"course_id": courses[code], "weekday": wd, "room": room,
                                 "start_min": edumate.parse_hhmm(a), "end_min": edumate.parse_hhmm(b)})
now = edumate.now_vn()
for code, title, kind, days in [("CS101", "Bài tập 1: Vòng lặp", "assignment", 2), ("MA101", "Kiểm tra giữa kỳ", "exam", 9),
                                ("PH101", "Báo cáo thí nghiệm", "assignment", 5)]:
    due = (now + timedelta(days=days)).replace(hour=23, minute=59).strftime("%Y-%m-%dT%H:%M")
    store.add("deadlines", {"course_id": courses[code], "title": title, "kind": kind, "due_at": due})
print("Đã tạo dữ liệu demo.")
