"""EduMate - backend tối giản (Flask + Firebase Authentication + Firestore).

Chạy:  python app.py   ->  http://127.0.0.1:5000
Các thuật toán cốt lõi nằm ở phần "THUẬT TOÁN" (hàm thuần, dễ test).
Truy cập dữ liệu đi qua store.py (Firestore, hoặc RAM khi EDUMATE_STORE=memory).
Đăng nhập: trình duyệt đăng nhập bằng Firebase Auth, gửi ID token lên /api/login hoặc
/api/register; backend xác minh token rồi giữ phiên bằng cookie Flask.
"""
import hashlib
import os
import re
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, g, jsonify, request, send_from_directory, session
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

try:  # đọc file .env nếu có (tùy chọn)
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from store import AlreadyExists, make_store  # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VN_TZ = timezone(timedelta(hours=7))  # Asia/Ho_Chi_Minh (không có DST)
WEEKDAYS = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"), static_url_path="/static")
app.secret_key = os.environ.get("SECRET_KEY") or "dev-only-change-me"
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

store = make_store()

# Collections trong Firestore: users, courses, class_sessions, enrollments,
# deadlines, deadline_done, questions (mỗi question chứa mảng `answers`).


def key(s):
    """ID document cố định từ email / mã môn -> create() nguyên tử đảm bảo không trùng."""
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:20]


# --------------------------------------------------------------------------
# THUẬT TOÁN (hàm thuần, không đụng database)
# --------------------------------------------------------------------------
class ApiError(Exception):
    def __init__(self, msg, status=400):
        super().__init__(msg)
        self.msg, self.status = msg, status


def now_vn():
    return datetime.now(VN_TZ)


def parse_hhmm(s):
    """'07:30' -> 450 (phút kể từ 00:00)."""
    m = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", str(s or "").strip())
    if not m:
        raise ApiError("Giờ phải có dạng HH:MM")
    return int(m[1]) * 60 + int(m[2])


def fmt_hhmm(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def overlaps(a, b):
    """Hai buổi học trùng nhau nếu cùng thứ và khoảng [start, end) giao nhau.
    Học liền kề (a.end == b.start) KHÔNG tính là trùng."""
    return a["weekday"] == b["weekday"] and a["start_min"] < b["end_min"] and b["start_min"] < a["end_min"]


def find_conflicts(candidates, existing):
    """Trả về danh sách cặp (candidate, existing) bị trùng. Độ phức tạp O(n*m) - đủ cho
    vài chục buổi/tuần; nếu dữ liệu lớn thì nhóm theo weekday rồi sort + quét."""
    return [(c, e) for c in candidates for e in existing if overlaps(c, e)]


def build_timetable(sessions):
    """Gom các buổi học thành 7 danh sách (Thứ 2..CN), mỗi ngày sắp theo giờ bắt đầu."""
    days = [[] for _ in range(7)]
    for s in sorted(sessions, key=lambda s: (s["weekday"], s["start_min"])):
        days[s["weekday"]].append(s)
    return days


def parse_due(s):
    try:
        return datetime.strptime(str(s), "%Y-%m-%dT%H:%M").replace(tzinfo=VN_TZ)
    except ValueError:
        raise ApiError("Hạn nộp phải có dạng YYYY-MM-DDTHH:MM")


def classify_deadline(due, now):
    """overdue | today | soon (<= 3 ngày) | upcoming"""
    if due < now:
        return "overdue"
    if due.date() == now.date():
        return "today"
    if due - now <= timedelta(days=3):
        return "soon"
    return "upcoming"


def rank_deadlines(items):
    """Việc chưa xong lên trước, trong mỗi nhóm sắp theo hạn tăng dần
    (quá hạn chưa làm sẽ nằm trên cùng vì hạn sớm nhất)."""
    return sorted(items, key=lambda d: (d["done"], d["due_at"]))


# --------------------------------------------------------------------------
# TIỆN ÍCH HTTP / PHÂN QUYỀN
# --------------------------------------------------------------------------
@app.errorhandler(ApiError)
def handle_api_error(e):
    return jsonify(error=e.msg), e.status


def body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def text(data, field, maxlen, required=True):
    v = str(data.get(field) or "").strip()
    if required and not v:
        raise ApiError(f"Thiếu trường '{field}'")
    if len(v) > maxlen:
        raise ApiError(f"'{field}' tối đa {maxlen} ký tự")
    return v


def current_user():
    uid = session.get("uid")
    return store.get("users", uid) if uid else None


def require(role=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                raise ApiError("Chưa đăng nhập", 401)
            if role and user["role"] != role:
                raise ApiError("Bạn không có quyền thực hiện thao tác này", 403)
            g.user = user
            return fn(*args, **kwargs)
        return wrapper
    return deco


def get_course(cid):
    c = store.get("courses", cid)
    if not c:
        raise ApiError("Không tìm thấy môn học", 404)
    return c


def own_course(cid):
    c = get_course(cid)
    if c["lecturer_id"] != g.user["id"]:
        raise ApiError("Bạn không phụ trách môn học này", 403)
    return c


def is_member(user, course_id):
    if user["role"] == "lecturer":
        c = store.get("courses", course_id)
        return bool(c) and c["lecturer_id"] == user["id"]
    return store.get("enrollments", f"{user['id']}_{course_id}") is not None


def my_course_ids(user):
    if user["role"] == "student":
        return [e["course_id"] for e in store.where("enrollments", student_id=user["id"])]
    return [c["id"] for c in store.where("courses", lecturer_id=user["id"])]


def courses_map(ids):
    return {cid: store.get("courses", cid) for cid in ids}


def user_dict(u):
    return {"id": u["id"], "name": u["name"], "email": u["email"], "role": u["role"]}


def session_dict(r, course):
    return {
        "id": r["id"], "course_id": r["course_id"], "course_code": course["code"],
        "course_name": course["name"], "weekday": r["weekday"], "room": r.get("room", ""),
        "start_min": r["start_min"], "end_min": r["end_min"],
        "start": fmt_hhmm(r["start_min"]), "end": fmt_hhmm(r["end_min"]),
    }


def sessions_of(course_ids):
    """Tất cả buổi học (dạng dict đã kèm mã/tên môn) của các môn trong course_ids."""
    out = []
    for cid, course in courses_map(course_ids).items():
        if course:
            out += [session_dict(r, course) for r in store.where("class_sessions", course_id=cid)]
    return out


def conflict_message(e, what="Trùng lịch"):
    return (f"{what} với {e['course_code']} ({WEEKDAYS[e['weekday']]} "
            f"{fmt_hhmm(e['start_min'])}–{fmt_hhmm(e['end_min'])})")


# --------------------------------------------------------------------------
# TÀI KHOẢN
# --------------------------------------------------------------------------
@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


def firebase_config():
    """Cấu hình web của Firebase (apiKey không phải bí mật) - đọc từ biến môi trường / .env."""
    api_key = os.environ.get("FIREBASE_API_KEY", "").strip()
    project_id = os.environ.get("FIREBASE_PROJECT_ID", "").strip()
    if not api_key or not project_id:
        raise ApiError("Chưa cấu hình Firebase Authentication: đặt FIREBASE_API_KEY và "
                       "FIREBASE_PROJECT_ID trong file .env (xem README)", 503)
    cfg = {"apiKey": api_key, "projectId": project_id,
           "authDomain": os.environ.get("FIREBASE_AUTH_DOMAIN", "").strip() or f"{project_id}.firebaseapp.com"}
    if os.environ.get("FIREBASE_APP_ID", "").strip():
        cfg["appId"] = os.environ["FIREBASE_APP_ID"].strip()
    return cfg


def verify_token(id_token):
    """Xác minh Firebase ID token: chữ ký (khóa công khai của Google), hạn dùng, audience = projectId,
    và issuer. Trả về claims (có 'sub' = uid, 'email'). Không cần service account."""
    project_id = firebase_config()["projectId"]
    if not isinstance(id_token, str) or not id_token:
        raise ApiError("Thiếu id_token", 401)
    try:
        claims = google_id_token.verify_firebase_token(
            id_token, google_requests.Request(), audience=project_id, clock_skew_in_seconds=10)
    except ValueError:
        raise ApiError("Phiên đăng nhập Firebase không hợp lệ hoặc đã hết hạn", 401)
    except GoogleAuthError:
        raise ApiError("Không kết nối được máy chủ xác thực của Google, hãy thử lại", 503)
    if (not claims or claims.get("iss") != f"https://securetoken.google.com/{project_id}"
            or not claims.get("sub") or not claims.get("email")):
        raise ApiError("Token không hợp lệ", 401)
    return claims


def start_session(uid):
    session.clear()
    session["uid"] = uid
    return jsonify(user=user_dict(store.get("users", uid)))


@app.get("/api/config")
def config():
    return jsonify(firebase_config())


@app.post("/api/register")
def register():
    """Gọi sau khi trình duyệt đã tạo tài khoản trên Firebase Auth: lưu hồ sơ (tên, vai trò)."""
    d = body()
    claims = verify_token(d.get("id_token"))
    name = text(d, "name", 80)
    role = d.get("role")
    if role not in ("student", "lecturer"):
        raise ApiError("Vai trò không hợp lệ")
    uid = claims["sub"]
    try:
        store.create("users", uid, {"name": name, "email": claims["email"].lower(), "role": role})
    except AlreadyExists:
        raise ApiError("Tài khoản này đã có hồ sơ, hãy đăng nhập", 409)
    resp = start_session(uid)
    resp.status_code = 201
    return resp


@app.post("/api/login")
def login():
    claims = verify_token(body().get("id_token"))
    uid = claims["sub"]
    if not store.get("users", uid):
        # Tài khoản có trên Firebase nhưng chưa có hồ sơ (VD: tạo từ Firebase Console):
        # tạo hồ sơ với quyền thấp nhất (sinh viên).
        email = claims["email"].lower()
        try:
            store.create("users", uid, {"name": (claims.get("name") or email.split("@")[0])[:80],
                                        "email": email, "role": "student"})
        except AlreadyExists:
            pass
    return start_session(uid)


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
def me():
    u = current_user()
    return jsonify(user=user_dict(u) if u else None)


# --------------------------------------------------------------------------
# MÔN HỌC + LỊCH HỌC
# --------------------------------------------------------------------------
@app.get("/api/courses")
@require()
def list_courses():
    u = g.user
    courses = sorted(store.all("courses"), key=lambda c: c["code"])
    cmap = {c["id"]: c for c in courses}
    by_course = {}
    for r in store.all("class_sessions"):
        if r["course_id"] in cmap:
            by_course.setdefault(r["course_id"], []).append(session_dict(r, cmap[r["course_id"]]))
    enrollments = store.all("enrollments")
    counts = Counter(e["course_id"] for e in enrollments)
    enrolled = {e["course_id"] for e in enrollments if e["student_id"] == u["id"]}
    lecturer_names = {}
    out = []
    for c in courses:
        lid = c["lecturer_id"]
        if lid not in lecturer_names:
            lecturer_names[lid] = (store.get("users", lid) or {}).get("name", "?")
        out.append({
            "id": c["id"], "code": c["code"], "name": c["name"],
            "lecturer_name": lecturer_names[lid], "student_count": counts[c["id"]],
            "mine": lid == u["id"], "enrolled": c["id"] in enrolled,
            "sessions": sorted(by_course.get(c["id"], []), key=lambda s: (s["weekday"], s["start_min"])),
        })
    return jsonify(courses=out)


@app.post("/api/courses")
@require("lecturer")
def create_course():
    d = body()
    code = text(d, "code", 20).upper()
    name = text(d, "name", 100)
    cid = key(code)
    try:
        store.create("courses", cid, {"code": code, "name": name, "lecturer_id": g.user["id"]})
    except AlreadyExists:
        raise ApiError("Mã môn học đã tồn tại", 409)
    return jsonify(id=cid), 201


@app.post("/api/courses/<cid>/sessions")
@require("lecturer")
def add_session(cid):
    own_course(cid)
    d = body()
    try:
        weekday = int(d.get("weekday"))
    except (TypeError, ValueError):
        raise ApiError("Thứ không hợp lệ")
    if not 0 <= weekday <= 6:
        raise ApiError("Thứ không hợp lệ")
    start, end = parse_hhmm(d.get("start")), parse_hhmm(d.get("end"))
    if end <= start:
        raise ApiError("Giờ kết thúc phải sau giờ bắt đầu")
    room = text(d, "room", 30, required=False)

    # Giảng viên không thể dạy 2 lớp cùng lúc
    mine = sessions_of(my_course_ids(g.user))
    conflicts = find_conflicts([{"weekday": weekday, "start_min": start, "end_min": end}], mine)
    if conflicts:
        raise ApiError(conflict_message(conflicts[0][1], "Trùng lịch dạy"), 409)
    store.add("class_sessions", {"course_id": cid, "weekday": weekday,
                                 "start_min": start, "end_min": end, "room": room})
    return jsonify(ok=True), 201


@app.delete("/api/sessions/<sid>")
@require("lecturer")
def delete_session(sid):
    s = store.get("class_sessions", sid)
    if not s:
        raise ApiError("Không tìm thấy buổi học", 404)
    own_course(s["course_id"])
    store.delete("class_sessions", sid)
    return jsonify(ok=True)


@app.post("/api/courses/<cid>/enroll")
@require("student")
def enroll(cid):
    get_course(cid)
    uid = g.user["id"]
    eid = f"{uid}_{cid}"
    if store.get("enrollments", eid):
        raise ApiError("Bạn đã đăng ký môn này", 409)
    conflicts = find_conflicts(sessions_of([cid]), sessions_of(my_course_ids(g.user)))
    if conflicts:
        raise ApiError(conflict_message(conflicts[0][1]), 409)
    try:
        store.create("enrollments", eid, {"student_id": uid, "course_id": cid})
    except AlreadyExists:
        raise ApiError("Bạn đã đăng ký môn này", 409)
    return jsonify(ok=True), 201


@app.delete("/api/courses/<cid>/enroll")
@require("student")
def unenroll(cid):
    store.delete("enrollments", f"{g.user['id']}_{cid}")
    return jsonify(ok=True)


@app.get("/api/timetable")
@require()
def timetable():
    return jsonify(days=build_timetable(sessions_of(my_course_ids(g.user))))


# --------------------------------------------------------------------------
# DEADLINE / KỲ THI
# --------------------------------------------------------------------------
@app.get("/api/deadlines")
@require()
def list_deadlines():
    u, now = g.user, now_vn()
    ids = my_course_ids(u)
    cmap = courses_map(ids)
    done_ids = {r["deadline_id"] for r in store.where("deadline_done", student_id=u["id"])} \
        if u["role"] == "student" else set()
    items = []
    for cid in ids:
        for r in store.where("deadlines", course_id=cid):
            due = parse_due(r["due_at"])
            items.append({
                "id": r["id"], "course_id": cid, "course_code": cmap[cid]["code"],
                "course_name": cmap[cid]["name"], "title": r["title"], "kind": r["kind"],
                "due_at": r["due_at"], "done": r["id"] in done_ids,
                "status": classify_deadline(due, now), "days_left": (due.date() - now.date()).days,
            })
    return jsonify(deadlines=rank_deadlines(items))


@app.post("/api/courses/<cid>/deadlines")
@require("lecturer")
def add_deadline(cid):
    own_course(cid)
    d = body()
    title = text(d, "title", 120)
    kind = d.get("kind")
    if kind not in ("assignment", "exam"):
        raise ApiError("Loại phải là assignment hoặc exam")
    due = parse_due(d.get("due_at")).strftime("%Y-%m-%dT%H:%M")  # chuẩn hóa để sort theo chuỗi
    store.add("deadlines", {"course_id": cid, "title": title, "kind": kind, "due_at": due})
    return jsonify(ok=True), 201


@app.delete("/api/deadlines/<did>")
@require("lecturer")
def delete_deadline(did):
    d = store.get("deadlines", did)
    if not d:
        raise ApiError("Không tìm thấy deadline", 404)
    own_course(d["course_id"])
    for r in store.where("deadline_done", deadline_id=did):  # dọn dữ liệu liên quan
        store.delete("deadline_done", r["id"])
    store.delete("deadlines", did)
    return jsonify(ok=True)


@app.post("/api/deadlines/<did>/done")
@require("student")
def mark_done(did):
    d = store.get("deadlines", did)
    if not d:
        raise ApiError("Không tìm thấy deadline", 404)
    if not is_member(g.user, d["course_id"]):
        raise ApiError("Bạn chưa đăng ký môn học này", 403)
    rid = f"{g.user['id']}_{did}"
    if body().get("done", True):
        store.set("deadline_done", rid, {"student_id": g.user["id"], "deadline_id": did})
    else:
        store.delete("deadline_done", rid)
    return jsonify(ok=True)


# --------------------------------------------------------------------------
# HỎI ĐÁP VỚI GIẢNG VIÊN
# --------------------------------------------------------------------------
@app.get("/api/questions")
@require()
def list_questions():
    ids = my_course_ids(g.user)
    cid = request.args.get("course_id")
    if cid:
        if cid not in ids:
            raise ApiError("Bạn không thuộc môn học này", 403)
        ids = [cid]
    cmap = courses_map(ids)
    qs = [q for i in ids for q in store.where("questions", course_id=i)]
    qs.sort(key=lambda q: q["ts"], reverse=True)
    return jsonify(questions=[{
        "id": q["id"], "course_id": q["course_id"], "course_code": cmap[q["course_id"]]["code"],
        "title": q["title"], "body": q["body"], "created_at": q["created_at"],
        "author_name": q["author_name"], "author_role": q["author_role"],
        "answers": sorted(({k: a[k] for k in ("id", "body", "created_at", "author_name", "author_role")}
                           for a in q.get("answers", [])), key=lambda a: a["created_at"]),
    } for q in qs[:100]])


def new_post(user, body_text):
    return {"author_id": user["id"], "author_name": user["name"], "author_role": user["role"],
            "body": body_text, "created_at": now_vn().strftime("%Y-%m-%dT%H:%M"), "ts": time.time()}


@app.post("/api/courses/<cid>/questions")
@require("student")
def ask_question(cid):
    get_course(cid)
    if not is_member(g.user, cid):
        raise ApiError("Bạn chưa đăng ký môn học này", 403)
    d = body()
    title, content = text(d, "title", 150), text(d, "body", 2000)
    store.add("questions", {**new_post(g.user, content), "course_id": cid, "title": title, "answers": []})
    return jsonify(ok=True), 201


@app.post("/api/questions/<qid>/answers")
@require()
def answer_question(qid):
    q = store.get("questions", qid)
    if not q:
        raise ApiError("Không tìm thấy câu hỏi", 404)
    if not is_member(g.user, q["course_id"]):
        raise ApiError("Bạn không thuộc môn học này", 403)
    content = text(body(), "body", 2000)
    store.array_append("questions", qid, "answers", {**new_post(g.user, content), "id": uuid.uuid4().hex})
    return jsonify(ok=True), 201


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=int(os.environ.get("PORT", 5000)))
