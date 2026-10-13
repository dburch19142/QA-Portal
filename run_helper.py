"""Local test runner for the QA portal.

A web page cannot start programs, so this script does it. It serves the portal
at http://localhost:8765 and the Playwright folder there gains a "Run tests on
this PC" panel, which starts a suite in a browser window you can watch.

    python run_helper.py              opens the portal in your browser
    python run_helper.py --no-browser

When a watch run finishes, each test's result is saved to the matching record
in data.json, so the portal's charts and table show the latest run.

It listens on this PC only and runs nothing but the commands in PROJECTS.
Press Ctrl+C to stop it.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
import xml.etree.ElementTree as ET
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import build

ROOT = Path(__file__).parent
WORKSPACE = ROOT.parent
PORT = 8765
HOSTS = {f"localhost:{PORT}", f"127.0.0.1:{PORT}"}
MAX_LINES = 5000
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

DATA = ROOT / "data.json"
BROWSERS = {"chromium": "Chromium", "firefox": "Firefox", "webkit": "WebKit"}
PLAYWRIGHT_STATUS = {"expected": "Pass", "unexpected": "Fail", "flaky": "Flaky", "skipped": "Skipped"}

UI_MODE = ("Open Playwright UI", ["npx", "playwright", "test", "--ui"], None)

# Keyed by the project name used in the portal's records. Each mode is a button:
# its label, the command it runs from the project's folder, and which kind of
# results file that command can write ("playwright", "pytest" or None).
PROJECTS = {
    "Congress Report Card": {
        "dir": WORKSPACE / "congress-report-card",
        "modes": {
            "watch": ("Watch run", [sys.executable, "tests/test_congress_report_card.py", "--headed", "--slowmo", "200"], "pytest"),
            "ui": UI_MODE,
        },
    },
    "GHSA Football": {
        "dir": WORKSPACE / ".claude/worktrees/ghsa/Darrell1914/ghsa-scoreboard",
        "modes": {
            "watch": ("Watch run", ["npx", "playwright", "test", "--headed", "--project=chromium", "--workers=1"], "playwright"),
            "ui": UI_MODE,
        },
    },
    "Playwright framework demo": {
        "dir": WORKSPACE / "playwright-framework",
        "modes": {
            "watch": ("Watch run", ["npx", "playwright", "test", "--headed", "--workers=1"], "playwright"),
            "ui": UI_MODE,
        },
    },
}

LOCK = threading.Lock()
current = None  # the latest run, kept after it ends so the page can show its result


class Run:
    def __init__(self, project, mode, label, proc, read_results):
        self.id = f"{time.time_ns():x}"
        self.project, self.mode, self.label, self.proc = project, mode, label, proc
        self.read_results = read_results  # None when this run records nothing
        self.status = "running"
        self.saved = False
        self.lines = []


def norm(title):
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")


def read_playwright_report(path, folder):
    report = json.loads(path.read_text(encoding="utf-8"))
    root = Path(report.get("config", {}).get("rootDir", folder))
    found = []

    def walk(suite, parents):
        for spec in suite.get("specs", []):
            try:
                file = (root / spec["file"]).relative_to(folder).as_posix()
            except ValueError:
                file = spec["file"]
            for test in spec.get("tests", []):
                last = (test.get("results") or [{}])[-1]
                found.append({
                    "title": " > ".join([*parents, spec["title"]]),
                    "spec": file,
                    "browser": BROWSERS.get(test.get("projectName"), "Chromium"),
                    "status": PLAYWRIGHT_STATUS.get(test.get("status"), "Fail"),
                    "duration": round(last.get("duration", 0) / 1000, 2),
                })
        for child in suite.get("suites", []):
            walk(child, [*parents, child["title"]])

    for file_suite in report.get("suites", []):
        walk(file_suite, [])
    return found


def read_junit(path, spec):
    found = []
    for case in ET.parse(path).iter("testcase"):
        name, _, browser = case.get("name", "").partition("[")
        failed = case.find("failure") is not None or case.find("error") is not None
        found.append({
            "title": name.removeprefix("test_").replace("_", " "),
            "spec": spec,
            "browser": BROWSERS.get(browser.rstrip("]"), "Chromium"),
            "status": "Fail" if failed else "Skipped" if case.find("skipped") is not None else "Pass",
            # The pytest run is slowed by --slowmo, so its timings would not compare with the others
            "duration": None,
        })
    return found


def save_results(project, results):
    """Writes each result to its record in data.json. Returns (updated, added)."""
    data = json.loads(DATA.read_text(encoding="utf-8"))
    records = data.setdefault("playwright", [])
    by_title = {(r.get("browser"), norm(r.get("title", ""))): r for r in records if r.get("project") == project}
    today, updated, added = date.today().isoformat(), 0, 0
    for result in results:
        # Records made before a test moved into a describe block carry only its own title
        record = (by_title.get((result["browser"], norm(result["title"])))
                  or by_title.get((result["browser"], norm(result["title"].split(" > ")[-1]))))
        if record is None:
            number = max([int(r["id"].split("-")[-1]) for r in records if r["id"].split("-")[-1].isdigit()] or [0]) + 1
            record = {"browser": result["browser"], "duration": None, "lastRun": today, "notes": "", "project": project,
                      "spec": result["spec"], "status": result["status"], "title": result["title"], "id": f"PW-{number:03d}"}
            records.append(record)
            added += 1
        else:
            updated += 1
        record["status"], record["lastRun"] = result["status"], today
        if result["duration"] is not None:
            record["duration"] = result["duration"]
    data["exported"] = today
    scratch = DATA.with_suffix(".json.tmp")
    scratch.write_text(json.dumps(data, indent=1), encoding="utf-8", newline="\n")
    scratch.replace(DATA)
    return updated, added


def follow(run):
    for raw in run.proc.stdout:
        with LOCK:
            if len(run.lines) < MAX_LINES:
                run.lines.append(ANSI.sub("", raw.rstrip("\r\n")))
            elif len(run.lines) == MAX_LINES:
                run.lines.append("(Output is longer than this panel keeps. The run continues.)")
    code = run.proc.wait()
    notes = [f"Exited with code {code}."]
    # A stopped run is incomplete, so it is not recorded
    if run.read_results and run.status == "running":
        try:
            updated, added = save_results(run.project, run.read_results())
            run.saved = True
            notes.append(f"Saved to the portal: {updated} records updated, {added} added.")
        except Exception as error:
            notes.append(f"Results were not saved: {error}")
    if run.report:
        run.report.unlink(missing_ok=True)
    with LOCK:
        if run.status == "running":
            # The UI window has no result of its own; it only gets closed
            run.status = "closed" if run.mode == "ui" else "passed" if code == 0 else "failed"
        run.lines.extend(notes)


def start(project, mode):
    """Starts a run. Returns an error message, or None when it started."""
    global current
    entry = PROJECTS.get(project)
    if not entry or mode not in entry["modes"]:
        return "That project or run type is not set up in run_helper.py."
    if not entry["dir"].is_dir():
        return f"Folder not found: {entry['dir']}"
    label, command, results = entry["modes"][mode]
    program = shutil.which(command[0])
    if not program:
        return f"'{command[0]}' is not installed or not on PATH."
    with LOCK:
        if current and current.status == "running":
            return f"{current.project} is still running. Stop it or wait for it to finish."
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONUTF8": "1", "FORCE_COLOR": "0"}
        extra, read_results, report = [], None, None
        if results:
            report = Path(tempfile.gettempdir()) / f"qa-portal-run-{time.time_ns():x}"
            if results == "playwright":
                extra, env["PLAYWRIGHT_JSON_OUTPUT_NAME"] = ["--reporter=list,json"], str(report)
                read_results = lambda: read_playwright_report(report, entry["dir"])
            else:
                extra = [f"--junitxml={report}"]
                read_results = lambda: read_junit(report, command[1])
        proc = subprocess.Popen(
            [program, *command[1:], *extra], cwd=entry["dir"], env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        current = Run(project, mode, label, proc, read_results)
        current.report = report
        current.lines.append("> " + " ".join(command))
        threading.Thread(target=follow, args=(current,), daemon=True).start()
    return None


def stop():
    with LOCK:
        run = current
        if not run or run.status != "running":
            return
        run.status = "stopped"
    # npx starts node, which starts the browsers; end the whole tree
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(run.proc.pid), "/T", "/F"], capture_output=True)
    else:
        run.proc.kill()


def state(run_id, since):
    projects = [{
        "name": name,
        "available": entry["dir"].is_dir(),
        "reason": "" if entry["dir"].is_dir() else f"Folder not found: {entry['dir']}",
        "modes": [{"id": mode, "label": label} for mode, (label, *_) in entry["modes"].items()],
    } for name, entry in PROJECTS.items()]
    with LOCK:
        run = current and {
            "id": current.id, "project": current.project, "mode": current.mode,
            "label": current.label, "status": current.status, "saved": current.saved,
            # only the lines the page has not seen yet
            "lines": current.lines[since if run_id == current.id else 0:],
        }
    return {"projects": projects, "run": run}


class Handler(BaseHTTPRequestHandler):
    def send(self, status, body, content_type):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload, status=200):
        self.send(status, json.dumps(payload), "application/json")

    def do_GET(self):
        # Refuse other host names, so a website cannot reach this through a DNS trick
        if self.headers.get("Host") not in HOSTS:
            return self.send_json({"error": "Open the portal at http://localhost:%d" % PORT}, 403)
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            self.send(200, build.render(), "text/html; charset=utf-8")
        elif url.path == "/data.json":
            self.send(200, DATA.read_bytes(), "application/json")
        elif url.path == "/api/runner":
            query = parse_qs(url.query)
            since = query.get("since", ["0"])[0]
            self.send_json(state(query.get("run", [""])[0], int(since) if since.isdigit() else 0))
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        # Only the portal page served from here may start or stop a run
        host = self.headers.get("Host")
        if host not in HOSTS or self.headers.get("Origin") != f"http://{host}":
            return self.send_json({"error": "Requests must come from the portal on this PC."}, 403)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            return self.send_json({"error": "Bad request"}, 400)
        if self.path == "/api/run":
            error = start(str(body.get("project")), str(body.get("mode")))
            self.send_json({"error": error} if error else {"ok": True}, 409 if error else 200)
        elif self.path == "/api/stop":
            stop()
            self.send_json({"ok": True})
        else:
            self.send_json({"error": "Not found"}, 404)

    def log_message(self, *args):
        pass  # the page polls every second; logging each request would bury everything else


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}/#playwright"
    print(f"QA portal with the test runner: {url}\nPress Ctrl+C to stop.")
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop()
        server.server_close()


if __name__ == "__main__":
    main()
