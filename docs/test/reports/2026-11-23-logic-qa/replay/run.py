"""Open the click-to-replay EduMate QA menu on a loopback-only server."""
import argparse
from collections import OrderedDict
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from threading import Lock
from time import sleep
from unittest.mock import patch
import json
import os
import secrets
import subprocess
import sys
import webbrowser

HERE = Path(__file__).resolve().parent
default_repo = next((directory for directory in HERE.parents
                     if (directory / "src" / "app.py").is_file()), Path.cwd())
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--repo", type=Path, default=default_repo, help="EduMate checkout containing src/app.py")
parser.add_argument("--port", type=int, default=5080)
parser.add_argument("--no-browser", action="store_true")
args = parser.parse_args()
repo = args.repo.resolve()
src = repo / "src"
if not (src / "app.py").is_file():
    parser.error("Không tìm thấy src/app.py. Chỉ đường dẫn checkout EduMate bằng --repo.")

sys.path.insert(0, str(src))
for key in list(os.environ):
    if key.startswith("FIREBASE_"):
        del os.environ[key]
os.environ.update(
    EDUMATE_STORE="memory",
    SECRET_KEY=secrets.token_hex(32),
    FLASK_DEBUG="0",
    FIREBASE_API_KEY="qa-local-key",
    FIREBASE_PROJECT_ID="edumate-qa-local",
    PYTHON_DOTENV_DISABLED="1",
)

try:
    from flask import abort, g, redirect, render_template, request, send_from_directory, session, url_for
    from werkzeug.serving import make_server
    import dotenv
    with patch.object(dotenv, "load_dotenv", return_value=False):
        import app as edu
except ModuleNotFoundError as error:
    parser.exit(1, f"Thiếu thư viện {error.name}. Chạy python -m pip install -r src/requirements.txt.\n")

from scenarios import ACTIVE_STORE, CASES, LONG_ASSIGNMENT, LONG_QUESTION, Fixture, ScopedStore, ui_fixture

app = edu.app
app.template_folder = str(HERE)
app.config.update(SESSION_COOKIE_SECURE=False, PROPAGATE_EXCEPTIONS=False,
                  TRUSTED_HOSTS=["127.0.0.1", "localhost"])
edu.store = ScopedStore()
runs = OrderedDict()
runs_lock = Lock()

try:
    revision = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, timeout=4, check=True,
    ).stdout.strip()
except (OSError, subprocess.SubprocessError):
    revision = "Không rõ commit"


def show(**context):
    return render_template("viewer.html", revision=revision, **context)


@app.before_request
def scope_browser_requests():
    if not request.path.startswith("/api/") or ACTIVE_STORE.get() is not None:
        return
    token = request.headers.get("X-EduMate-QA-Run", "")
    with runs_lock:
        current = runs.get(token)
    if current is None or not current["role"]:
        abort(403)
    g.qa_store = current["fixture"].store
    session["uid"] = current["role"]

    if current["code"] == "QA-09" and request.method == "GET" and request.path == "/api/questions":
        sleep(1.5)
    elif current["code"] == "QA-11" and request.method == "POST":
        fields = request.get_json(silent=True) or {}
        if request.path == f"/api/deadlines/{current['deadline_id']}/done" and fields.get("done") is True:
            sleep(1.8)
    elif current["code"] == "QA-12" and request.method == "POST":
        if request.path == f"/api/courses/{current['course_id']}/enroll":
            with runs_lock:
                current["clicks"] += 1
                number = current["clicks"]
            sleep(0.35 if number == 1 else 0.95)


@app.get("/__qa/")
def menu():
    return show(cases=CASES)


@app.get("/__qa/run/<code>")
def run_case(code):
    if code not in CASES:
        abort(404)
    title, execute = CASES[code]
    fixture = Fixture()
    token = secrets.token_urlsafe(18)
    try:
        if execute is None:
            screen = ui_fixture(fixture, code)
            state = {**asdict(screen), "tab": "", "auto": True}
            result = None
        else:
            result = execute(fixture)
            state = {"role": result.role, "tab": result.tab, "auto": False}
    except Exception as error:
        app.logger.exception("Unable to run %s", code)
        return show(code=code, title=title, error=str(error)), 500

    with runs_lock:
        runs[token] = {**state, "code": code, "fixture": fixture, "clicks": 0}
        if len(runs) > 24:
            runs.popitem(last=False)
    if result is None:
        return redirect(url_for("app_view", token=token))
    return show(code=code, title=title, result=result, token=token)


@app.get("/__qa/view/<token>")
def app_view(token):
    with runs_lock:
        current = runs.get(token)
    if current is None or not current["role"]:
        abort(404)
    code = current["code"]
    bootstrap = {
        "token": token, "code": code, "title": CASES[code][0], "auto": current["auto"],
        "tab": current["tab"], "courseId": current.get("course_id"),
        "deadlineId": current.get("deadline_id"), "longAssignment": LONG_ASSIGNMENT,
        "longQuestion": LONG_QUESTION,
        "futureDate": (edu.now_vn() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M"),
    }
    encoded = json.dumps(bootstrap, ensure_ascii=True).replace("<", "\\u003c")
    original = (Path(app.static_folder) / "index.html").read_text(encoding="utf-8")
    if "</head>" not in original or "</body>" not in original:
        return show(code=code, title=CASES[code][0], error="Không tìm thấy khung HTML của EduMate."), 500
    early = f'<script>window.eduMateQa = {encoded};</script><script src="/__qa/browser.js"></script>'
    return original.replace("</head>", early + "</head>", 1)


@app.get("/__qa/browser.js")
def script():
    return send_from_directory(HERE, "browser.js", mimetype="text/javascript")


@app.get("/__qa/evidence/<name>")
def image(name):
    if not name.endswith(".jpg") or name[:-4] not in {*CASES, "QA-13-before"}:
        abort(404)
    return send_from_directory(HERE.parent / "evidence", name)


if __name__ == "__main__":
    server = make_server("127.0.0.1", args.port, app, threaded=True)
    url = f"http://127.0.0.1:{server.server_port}/__qa/"
    print(f"EduMate QA · {revision} · {url}", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
