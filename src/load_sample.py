"""Nạp dữ liệu mẫu từ sample_data.json vào database đang cấu hình:  python load_sample.py [file.json]

- Các môn được gắn cho giảng viên có email = "lecturer_email" trong file JSON
  (mặc định gv@edumate.test, tạo bởi seed.py; có thể đổi thành email giảng viên của bạn).
- Chạy lại an toàn: môn đã có (theo mã môn) sẽ bị bỏ qua, không tạo trùng.
- Môn nào có buổi học trùng giờ với lịch dạy hiện có của giảng viên sẽ bị bỏ qua và báo rõ.
- Hạn nộp tính từ hôm nay (due_in_days) nên dữ liệu mẫu luôn còn mới.
GHI THẬT vào Firestore (trừ khi đặt EDUMATE_STORE=memory)."""
import json
import os
import sys
from datetime import timedelta

import app as edumate
from app import key, store

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_data.json")
with open(path, encoding="utf-8") as f:
    data = json.load(f)

email = data["lecturer_email"].strip().lower()
found = store.where("users", email=email)
if not found or found[0]["role"] != "lecturer":
    raise SystemExit(f"Không có giảng viên '{email}'. Hãy chạy seed.py trước, hoặc đổi 'lecturer_email' trong "
                     f"{os.path.basename(path)} thành email một tài khoản đã đăng ký với vai trò Giảng viên.")
lecturer = found[0]

now = edumate.now_vn()
added, skipped = 0, []
for c in data["courses"]:
    code = c["code"].strip().upper()
    cid = key(code)
    if store.get("courses", cid):
        skipped.append(f"{code}: đã tồn tại")
        continue
    sessions = [{"weekday": s["weekday"], "start_min": edumate.parse_hhmm(s["start"]),
                 "end_min": edumate.parse_hhmm(s["end"]), "room": s.get("room", "")} for s in c.get("sessions", [])]
    mine = edumate.sessions_of(edumate.my_course_ids(lecturer))  # đọc lại để tính cả môn vừa nạp
    clash = edumate.find_conflicts(sessions, mine)
    if clash:
        skipped.append(f"{code}: {edumate.conflict_message(clash[0][1], 'trùng lịch dạy')}")
        continue
    store.create("courses", cid, {"code": code, "name": c["name"], "lecturer_id": lecturer["id"]})
    for s in sessions:
        store.add("class_sessions", {"course_id": cid, **s})
    for d in c.get("deadlines", []):
        minutes = edumate.parse_hhmm(d["due_time"])
        due = (now + timedelta(days=d["due_in_days"])).replace(hour=minutes // 60, minute=minutes % 60)
        store.add("deadlines", {"course_id": cid, "title": d["title"], "kind": d["kind"],
                                "due_at": due.strftime("%Y-%m-%dT%H:%M")})
    added += 1
    print(f"+ {code} {c['name']}: {len(sessions)} buổi học, {len(c.get('deadlines', []))} deadline")

print(f"Đã nạp {added} môn.")
for line in skipped:
    print(f"- Bỏ qua {line}")
