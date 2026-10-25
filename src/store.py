"""Lớp truy cập dữ liệu. app.py chỉ nói chuyện với 2 lớp này, nên đổi database
chỉ cần sửa file này.

- FirestoreStore: Firebase Firestore (dùng thật).
- MemoryStore:    lưu trong RAM (chạy test, không cần Firebase).

Chọn bằng biến môi trường EDUMATE_STORE = firestore (mặc định) | memory
"""
import itertools
import json
import os


class AlreadyExists(Exception):
    """create() trên document đã tồn tại (dùng để đảm bảo email / mã môn là duy nhất)."""


class MemoryStore:
    def __init__(self):
        self._data, self._n = {}, itertools.count(1)

    def _col(self, col):
        return self._data.setdefault(col, {})

    def add(self, col, data):
        doc_id = f"m{next(self._n)}"
        self._col(col)[doc_id] = dict(data)
        return doc_id

    def create(self, col, doc_id, data):
        if doc_id in self._col(col):
            raise AlreadyExists(doc_id)
        self._col(col)[doc_id] = dict(data)

    def set(self, col, doc_id, data):
        self._col(col)[doc_id] = dict(data)

    def get(self, col, doc_id):
        d = self._col(col).get(doc_id)
        return {**d, "id": doc_id} if d is not None else None

    def where(self, col, **eq):
        return [{**d, "id": i} for i, d in self._col(col).items()
                if all(d.get(k) == v for k, v in eq.items())]

    def all(self, col):
        return [{**d, "id": i} for i, d in self._col(col).items()]

    def delete(self, col, doc_id):
        self._col(col).pop(doc_id, None)

    def array_append(self, col, doc_id, field, item):
        self._col(col)[doc_id].setdefault(field, []).append(item)


class FirestoreStore:
    def __init__(self):
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            raw = os.environ.get("FIREBASE_CREDENTIALS_JSON")  # nội dung JSON (dùng khi deploy)
            path = os.environ.get("FIREBASE_CREDENTIALS")      # đường dẫn file JSON (dùng khi dev)
            if raw:
                cred = credentials.Certificate(json.loads(raw))
            elif path:
                cred = credentials.Certificate(path)
            else:
                raise RuntimeError(
                    "Chưa cấu hình Firebase: đặt FIREBASE_CREDENTIALS=<đường dẫn file serviceAccount.json> "
                    "(xem README), hoặc EDUMATE_STORE=memory để chạy thử không cần Firebase.")
            firebase_admin.initialize_app(cred)
        self.db = firestore.client()

    def add(self, col, data):
        _, ref = self.db.collection(col).add(data)
        return ref.id

    def create(self, col, doc_id, data):
        from google.api_core.exceptions import AlreadyExists as _Exists
        try:
            self.db.collection(col).document(doc_id).create(data)  # nguyên tử: lỗi nếu đã tồn tại
        except _Exists:
            raise AlreadyExists(doc_id)

    def set(self, col, doc_id, data):
        self.db.collection(col).document(doc_id).set(data)

    def get(self, col, doc_id):
        snap = self.db.collection(col).document(doc_id).get()
        return {**snap.to_dict(), "id": snap.id} if snap.exists else None

    def where(self, col, **eq):
        from google.cloud.firestore_v1.base_query import FieldFilter
        q = self.db.collection(col)
        for k, v in eq.items():  # chỉ lọc bằng (==) nên không cần tạo composite index
            q = q.where(filter=FieldFilter(k, "==", v))
        return [{**s.to_dict(), "id": s.id} for s in q.stream()]

    def all(self, col):
        return [{**s.to_dict(), "id": s.id} for s in self.db.collection(col).stream()]

    def delete(self, col, doc_id):
        self.db.collection(col).document(doc_id).delete()

    def array_append(self, col, doc_id, field, item):
        from google.cloud.firestore_v1 import ArrayUnion
        self.db.collection(col).document(doc_id).update({field: ArrayUnion([item])})


def make_store():
    kind = os.environ.get("EDUMATE_STORE", "firestore").lower()
    if kind == "memory":
        return MemoryStore()
    if kind == "firestore":
        return FirestoreStore()
    raise RuntimeError(f"EDUMATE_STORE không hợp lệ: {kind}")
