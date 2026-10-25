"""Test nhanh: python -m unittest -v"""
import os
import unittest
from datetime import datetime, timedelta

os.environ["EDUMATE_STORE"] = "memory"  # test không đụng tới Firebase thật
os.environ["FIREBASE_API_KEY"] = "test-key"
os.environ["FIREBASE_PROJECT_ID"] = "edumate-test"

import app as edumate  # noqa: E402  (phải import sau khi đặt biến môi trường)


def fake_verify(token):
    """Thay verify_token khi test API: token có dạng 'uid|email|tên'."""
    if not isinstance(token, str) or token.count("|") != 2:
        raise edumate.ApiError("Phiên đăng nhập Firebase không hợp lệ hoặc đã hết hạn", 401)
    uid, email, name = token.split("|")
    return {"sub": uid, "email": email, "name": name}


class AlgorithmTests(unittest.TestCase):
    def s(self, wd, a, b):
        return {"weekday": wd, "start_min": edumate.parse_hhmm(a), "end_min": edumate.parse_hhmm(b)}

    def test_overlap(self):
        self.assertTrue(edumate.overlaps(self.s(0, "07:00", "09:00"), self.s(0, "08:00", "10:00")))
        self.assertTrue(edumate.overlaps(self.s(0, "07:00", "11:00"), self.s(0, "08:00", "09:00")))  # lồng nhau
        self.assertFalse(edumate.overlaps(self.s(0, "07:00", "09:00"), self.s(0, "09:00", "11:00")))  # liền kề
        self.assertFalse(edumate.overlaps(self.s(0, "07:00", "09:00"), self.s(1, "07:00", "09:00")))  # khác thứ

    def test_timetable_sorted(self):
        days = edumate.build_timetable([self.s(2, "13:00", "15:00"), self.s(2, "07:00", "09:00"), self.s(0, "10:00", "11:00")])
        self.assertEqual([x["start_min"] for x in days[2]], [420, 780])
        self.assertEqual(len(days[0]), 1)

    def test_classify_and_rank(self):
        now = datetime(2026, 10, 23, 12, 0, tzinfo=edumate.VN_TZ)
        mk = lambda **kw: now + timedelta(**kw)
        self.assertEqual(edumate.classify_deadline(mk(hours=-1), now), "overdue")
        self.assertEqual(edumate.classify_deadline(mk(hours=5), now), "today")
        self.assertEqual(edumate.classify_deadline(mk(days=2), now), "soon")
        self.assertEqual(edumate.classify_deadline(mk(days=10), now), "upcoming")
        items = [{"done": True, "due_at": "2026-10-01T10:00"}, {"done": False, "due_at": "2026-11-01T10:00"},
                 {"done": False, "due_at": "2026-10-25T10:00"}]
        self.assertEqual([i["due_at"] for i in edumate.rank_deadlines(items)],
                         ["2026-10-25T10:00", "2026-11-01T10:00", "2026-10-01T10:00"])

    def test_bad_input(self):
        with self.assertRaises(edumate.ApiError):
            edumate.parse_hhmm("25:00")
        with self.assertRaises(edumate.ApiError):
            edumate.parse_due("23/10/2026")


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._orig_verify, edumate.verify_token = edumate.verify_token, fake_verify
        cls.lect, cls.stu, cls.stu2 = (edumate.app.test_client() for _ in range(3))
        reg = lambda c, n, e, r: c.post("/api/register", json={"id_token": f"uid-{e}|{e}|{n}", "name": n, "role": r})
        assert reg(cls.lect, "GV A", "gv@x.vn", "lecturer").status_code == 201
        assert reg(cls.stu, "SV A", "sv@x.vn", "student").status_code == 201
        assert reg(cls.stu2, "SV B", "sv2@x.vn", "student").status_code == 201

    @classmethod
    def tearDownClass(cls):
        edumate.verify_token = cls._orig_verify

    def test_flow(self):
        L, S, S2 = self.lect, self.stu, self.stu2
        # đăng ký lại cùng tài khoản Firebase -> 409; token sai -> 401; vai trò sai -> 400
        again = {"id_token": "uid-sv@x.vn|sv@x.vn|SV A", "name": "x", "role": "student"}
        self.assertEqual(S.post("/api/register", json=again).status_code, 409)
        self.assertEqual(S.post("/api/register", json={**again, "id_token": "bad"}).status_code, 401)
        self.assertEqual(S.post("/api/register", json={**again, "id_token": "u9|n@x.vn|N", "role": "admin"}).status_code, 400)
        # chưa đăng nhập
        self.assertEqual(edumate.app.test_client().get("/api/courses").status_code, 401)
        # sinh viên không được tạo môn
        self.assertEqual(S.post("/api/courses", json={"code": "X", "name": "X"}).status_code, 403)
        # giảng viên tạo 2 môn, buổi học trùng giờ nhau
        c1 = L.post("/api/courses", json={"code": "cs101", "name": "Intro"}).get_json()["id"]
        c2 = L.post("/api/courses", json={"code": "ma101", "name": "Calculus"}).get_json()["id"]
        ok = L.post(f"/api/courses/{c1}/sessions", json={"weekday": 0, "start": "07:00", "end": "09:00", "room": "A1"})
        self.assertEqual(ok.status_code, 201)
        # GV không dạy 2 lớp cùng lúc
        self.assertEqual(L.post(f"/api/courses/{c2}/sessions", json={"weekday": 0, "start": "08:00", "end": "10:00"}).status_code, 409)
        self.assertEqual(L.post(f"/api/courses/{c2}/sessions", json={"weekday": 0, "start": "09:00", "end": "11:00"}).status_code, 201)
        # sinh viên đăng ký cả 2 môn: liền kề nên OK
        self.assertEqual(S.post(f"/api/courses/{c1}/enroll").status_code, 201)
        self.assertEqual(S.post(f"/api/courses/{c1}/enroll").status_code, 409)
        self.assertEqual(S.post(f"/api/courses/{c2}/enroll").status_code, 201)
        # thời khóa biểu tự sinh
        days = S.get("/api/timetable").get_json()["days"]
        self.assertEqual([x["course_code"] for x in days[0]], ["CS101", "MA101"])
        # deadline: GV tạo, SV thấy; SV khác (chưa đăng ký) không thấy
        due = (datetime.now(edumate.VN_TZ) + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
        self.assertEqual(L.post(f"/api/courses/{c1}/deadlines", json={"title": "BT1", "kind": "assignment", "due_at": due}).status_code, 201)
        self.assertEqual(S.post(f"/api/courses/{c1}/deadlines", json={"title": "x", "kind": "exam", "due_at": due}).status_code, 403)
        dls = S.get("/api/deadlines").get_json()["deadlines"]
        self.assertEqual((len(dls), dls[0]["status"], dls[0]["done"]), (1, "soon", False))
        self.assertEqual(S2.get("/api/deadlines").get_json()["deadlines"], [])
        self.assertEqual(S2.post(f"/api/deadlines/{dls[0]['id']}/done", json={"done": True}).status_code, 403)
        S.post(f"/api/deadlines/{dls[0]['id']}/done", json={"done": True})
        self.assertTrue(S.get("/api/deadlines").get_json()["deadlines"][0]["done"])
        # hỏi đáp: SV chưa đăng ký không được hỏi; SV đã đăng ký hỏi, GV trả lời
        self.assertEqual(S2.post(f"/api/courses/{c1}/questions", json={"title": "t", "body": "b"}).status_code, 403)
        self.assertEqual(S.post(f"/api/courses/{c1}/questions", json={"title": "Hỏi", "body": "<b>?</b>"}).status_code, 201)
        q = S.get("/api/questions").get_json()["questions"][0]
        self.assertEqual(L.post(f"/api/questions/{q['id']}/answers", json={"body": "Trả lời"}).status_code, 201)
        self.assertEqual(S2.post(f"/api/questions/{q['id']}/answers", json={"body": "chen ngang"}).status_code, 403)
        q = L.get("/api/questions").get_json()["questions"][0]
        self.assertEqual((len(q["answers"]), q["answers"][0]["author_role"]), (1, "lecturer"))
        # hủy đăng ký rồi không còn thấy môn trong thời khóa biểu
        S.delete(f"/api/courses/{c1}/enroll")
        self.assertEqual(len(S.get("/api/timetable").get_json()["days"][0]), 1)

    def test_login_logout(self):
        c = edumate.app.test_client()
        self.assertEqual(c.post("/api/login", json={"id_token": "bad"}).status_code, 401)
        self.assertEqual(c.post("/api/login", json={}).status_code, 401)
        self.assertIsNone(c.get("/api/me").get_json()["user"])
        r = c.post("/api/login", json={"id_token": "uid-gv@x.vn|gv@x.vn|GV A"})
        self.assertEqual((r.status_code, r.get_json()["user"]["role"]), (200, "lecturer"))  # giữ nguyên vai trò đã đăng ký
        c.post("/api/logout")
        self.assertIsNone(c.get("/api/me").get_json()["user"])

    def test_login_without_profile_creates_student(self):
        c = edumate.app.test_client()
        r = c.post("/api/login", json={"id_token": "uid-new|new@x.vn|"})  # tạo từ Firebase Console, chưa có hồ sơ
        self.assertEqual(r.status_code, 200)
        u = c.get("/api/me").get_json()["user"]
        self.assertEqual((u["role"], u["email"], u["name"]), ("student", "new@x.vn", "new"))

    def test_config_endpoint(self):
        c = edumate.app.test_client()
        cfg = c.get("/api/config").get_json()
        self.assertEqual((cfg["apiKey"], cfg["projectId"], cfg["authDomain"]), ("test-key", "edumate-test", "edumate-test.firebaseapp.com"))
        saved = os.environ.pop("FIREBASE_API_KEY")
        try:
            self.assertEqual(c.get("/api/config").status_code, 503)
        finally:
            os.environ["FIREBASE_API_KEY"] = saved


try:
    import cryptography  # noqa: F401
    from google.auth import crypt, jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from unittest import mock
    import time
    HAVE_CRYPTO = True
except ImportError:
    HAVE_CRYPTO = False


@unittest.skipUnless(HAVE_CRYPTO, "cần gói cryptography")
class VerifyTokenTests(unittest.TestCase):
    """Kiểm tra verify_token THẬT bằng JWT ký cục bộ (không gọi mạng tới Google)."""
    PID = "edumate-test"

    @classmethod
    def setUpClass(cls):
        def make_key():
            k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            priv = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
            pub = k.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
            return crypt.RSASigner.from_string(priv, key_id="k1"), pub.decode()
        cls.signer, pub = make_key()
        cls.other_signer, _ = make_key()  # khóa lạ: kẻ giả mạo
        cls.patch = mock.patch("google.oauth2.id_token._fetch_certs", return_value={"k1": pub})
        cls.patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.patch.stop()

    def token(self, signer=None, **over):
        now = int(time.time())
        claims = {"iss": f"https://securetoken.google.com/{self.PID}", "aud": self.PID, "sub": "uid1",
                  "email": "a@x.vn", "iat": now, "exp": now + 3600, "auth_time": now, **over}
        return jwt.encode(signer or self.signer, claims).decode()

    def test_valid(self):
        c = edumate.verify_token(self.token())
        self.assertEqual((c["sub"], c["email"]), ("uid1", "a@x.vn"))

    def test_rejects(self):
        bad = {
            "sai audience": self.token(aud="project-khac"),
            "sai issuer": self.token(iss="https://accounts.google.com"),
            "hết hạn": self.token(iat=int(time.time()) - 7200, exp=int(time.time()) - 3600),
            "ký bằng khóa lạ": self.token(signer=self.other_signer),
            "thiếu email": self.token(email=""),
            "rác": "khong.phai.jwt",
        }
        for why, tok in bad.items():
            with self.subTest(why):
                with self.assertRaises(edumate.ApiError) as cm:
                    edumate.verify_token(tok)
                self.assertEqual(cm.exception.status, 401)
        with self.assertRaises(edumate.ApiError) as cm:
            edumate.verify_token(None)
        self.assertEqual(cm.exception.status, 401)


if __name__ == "__main__":
    unittest.main()
