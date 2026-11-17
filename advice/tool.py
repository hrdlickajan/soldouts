"""Rep tool. One page plus a small JSON endpoint, served by the Python standard library. No install.

    python -m advice.tool --demo                                       # made-up data, nothing else needed
    python -m advice.tool --data <data folder> --tasks <routing input csv>
    python -m advice.tool --data <data folder> --live                  # today's sold-outs from the API
    python -m advice.tool --history-api --live                         # history and sold-outs both from the API
                                                                       # (--live and --history-api need GROUPON_API_KEY and GROUPON_API_BASE)
    python -m advice.tool --demo --auth                                # with the login (needs TOOL_PASSWORD and SESSION_SECRET)
Then open http://127.0.0.1:8080 . To open it on a phone on the same Wi-Fi add --host 0.0.0.0.

The same handler runs on Vercel: see advice/web.py and api/index.py.

Modes (config tool_mode, or --mode):
  demo  advice for every task, with the test group badge
  test  advice only for group B tasks. Group A tasks show as plain tasks with only hard facts
        (do-not-contact, promised callback, rep marks).
"""
import argparse
import html
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import config as cfgmod
from . import demo
from .adapters import load_routing_tasks, to_task
from .api import ApiError, ApiMarks, CachedMarks, Client, FileMarks, MemoryMarks
from .auth import Auth, ConfigError
from .engine import Engine
from .feed import FeedError, LiveFeed
from .history import History, load_pack

HARD = ("do_not_contact", "callback_promised", "rep_marked_no_call", "rep_marked_other")
STATIC = Path(__file__).with_name("static")
PAGE = STATIC / "index.html"
LOGIN = STATIC / "login.html"
THEME = STATIC / "theme.css"  # the style sheet (colours, type, shape)
MAX_BODY = 64 * 1024


def _r2(x):
    return None if x is None else round(x, 2)


def _order(r):
    s = r["status"]
    first = 0 if s == "callback_promised" else 1 if s == "high_value" else 2 if s in ("worth_a_call", "task") else 3 if r["kind"] == "other" else 4
    return first, -(r["gbp_high"] or 0)


class StaticSource:
    """Tasks from a list or from a function that returns a list (a routing input file, the demo)."""

    def __init__(self, tasks):
        self._tasks = tasks

    def load(self, merchants, force=False):
        tasks = self._tasks() if callable(self._tasks) else self._tasks
        return list(tasks), {"source": "file"}


class LiveSource:
    """Today's sold-outs from a LiveFeed. A row that cannot be read is skipped and counted, never fatal."""

    def __init__(self, feed):
        self.feed = feed

    def load(self, merchants, force=False):
        rows, meta = self.feed.get(force=force)
        tasks, skipped = [], 0
        for r in rows:
            try:
                tasks.append(to_task(r, merchants))
            except (KeyError, ValueError, TypeError, AttributeError):
                skipped += 1
        return tasks, dict(meta, skipped=skipped)


class Tool:
    def __init__(self, cfg, history, tasks, marks, findings=None, example=None):
        """tasks: a list, a function that returns a list, or a source with .load(merchants, force).
        example: another Tool with made-up data. The page can show it when the live list is empty. It is read only."""
        self.cfg, self.h, self.marks, self.findings = cfg, history, marks, findings or {}
        self.source = tasks if hasattr(tasks, "load") else StaticSource(tasks)
        self.engine, self.mode, self.example = Engine(cfg, history), cfg["tool_mode"], example

    def _row(self, a):
        t = a.task
        row = {"task_id": t.task_id, "merchant_id": t.merchant_id, "merchant_name": t.merchant_name, "deal_id": t.deal_id,
               "deal_name": t.deal_name, "city": t.city, "sold_out_date": t.sold_out_date.isoformat(),
               "sold_out_time": t.team_time, "mark": a.mark}
        if self.mode != "test":
            row["group"] = a.group
        full = self.mode != "test" or a.group == "B"
        if full or a.status in HARD:
            row.update(status=a.status, kind=a.kind, label=a.label, reason=a.reason,
                       gbp_low=_r2(a.gbp_low) if full else None, gbp_high=_r2(a.gbp_high) if full else None,
                       quote=a.quote if full else "", tags=a.tags if full else {})
        else:  # test mode, group A: a plain task
            row.update(status="task", kind="other", label="Task", reason="Restock task.", gbp_low=None, gbp_high=None, quote="", tags={})
        return row

    def state(self, rep_id=None, force=False):
        marks = self.marks.all()
        tasks, meta = self.source.load(self.h.merchants, force=force)
        rows, names = [], {}
        for t in tasks:
            names[t.merchant_id] = t.merchant_name
            rep = t.rep_id or self.h.merchants.get(t.merchant_id, {}).get("rep_id")
            if rep_id and rep and rep != rep_id:  # a merchant with no known rep is shown to everyone
                continue
            rows.append(self._row(self.engine.advise(t, marks, self.findings)))
        rows.sort(key=_order)
        name = lambda m: names.get(m) or self.h.merchants.get(m, {}).get("merchant_name") or m
        mine = [{"merchant_id": m, "merchant_name": name(m), **v} for m, v in marks.items()
                if not rep_id or v.get("marked_by") == rep_id]
        reps = [{"rep_id": r["rep_id"], "rep_name": r.get("rep_name") or r["rep_id"]} for r in self.h.reps]
        meta = dict(meta, example_available=self.example is not None)
        if getattr(self.marks, "error", None):
            meta["marks_error"] = self.marks.error
        return {"mode": self.mode, "reps": reps, "rows": rows, "marks": mine, "meta": meta, "auth": False, "example": False}

    def put_mark(self, merchant_id, mark, reason, marked_by):
        return self.marks.put(merchant_id, mark, reason, marked_by)

    def delete_mark(self, merchant_id):
        return self.marks.delete(merchant_id)


def render_login(error=""):
    """The login page. Everything that comes from outside is escaped."""
    user_field = '<input class="input" name="user" id="user" value="admin" autocomplete="username" autocapitalize="none" required maxlength="32">'
    notice = f'<div class="notice notice--danger" role="alert">{html.escape(error)}</div>' if error else ""
    return LOGIN.read_text(encoding="utf-8").replace("<!--USER_FIELD-->", user_field).replace("<!--NOTICE-->", notice)


def make_handler(tool, page, auth=None, login_page=None):
    """tool: a Tool, or a function that returns one (the hosted app builds it on the first request).
    auth: an Auth. With it, every route except the login and the style sheet needs a session."""
    get_tool = tool if callable(tool) else (lambda: tool)
    render = login_page or render_login

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        # ---- small helpers ----
        def _send(self, code, body, ctype="application/json", headers=(), cache="no-store"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "same-origin")
            for k, v in headers:
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj))

        def _redirect(self, where, headers=()):
            self._send(303, b"", "text/plain", headers=[("Location", where), *headers])

        def _route(self):
            """(path, query). On Vercel a rewrite sends every request to one function and puts the real path in __p."""
            u = urlparse(self.path)
            q = parse_qs(u.query, keep_blank_values=True)
            path = "/" + q.pop("__p")[0].lstrip("/") if "__p" in q else u.path
            return path, q

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return self.rfile.read(min(n, MAX_BODY))

        def _secure(self):
            return self.headers.get("X-Forwarded-Proto", "").lower() == "https"

        def _session(self):
            return auth.read_cookie(self.headers.get("Cookie")) if auth else None

        def _guard(self, api):
            if not auth or self._session():
                return True
            if api:
                self._json(401, {"error": "Sign in first."})
            else:
                self._redirect("/login")
            return False

        def _same_site(self):
            origin = self.headers.get("Origin")
            return not origin or urlparse(origin).netloc == self.headers.get("Host")

        def _write_checks(self, q):
            """A write needs a session. With a login it must also come from this site and be JSON. Returns True if it may go on."""
            if not self._guard(True):
                return False
            if auth and not self._same_site():
                self._json(403, {"error": "Not allowed from another site."})
                return False
            if (q.get("example") or [""])[0] == "1":
                self._json(400, {"error": "Marks are off for example tasks."})
                return False
            return True

        def _api_error(self, e):
            self._json(503 if e.status == 0 else 502, {"error": str(e), "retry": True})

        # ---- GET ----
        def do_GET(self):
            path, q = self._route()
            if path == "/theme.css":
                self._send(200, THEME.read_bytes(), "text/css", cache="public, max-age=3600")
            elif auth and path == "/login":
                self._redirect("/") if self._session() else self._send(200, render(), "text/html")
            elif path == "/":
                if self._guard(False):
                    self._send(200, page, "text/html")
            elif path == "/api/state":
                if self._guard(True):
                    self._state(q)
            else:
                self._json(404, {"error": "not found"})

        def _state(self, q):
            one = lambda k: (q.get(k) or [""])[0]
            try:
                t = get_tool()
                if one("example") == "1":
                    if t.example is None:
                        return self._json(404, {"error": "no example tasks"})
                    state = t.example.state(None)
                    state.update(example=True, meta=dict(state["meta"], example_available=True))
                else:
                    state = t.state(one("rep") or None, force=one("refresh") == "1")  # the dropdown: any rep, or everyone
                state["auth"] = bool(auth)
                if auth:
                    state["me"] = {"rep_id": self._session(), "rep_name": "Admin"}
                self._json(200, state)
            except FeedError as e:
                self._json(503, {"error": "Today's sold-outs could not be loaded. " + str(e), "retry": True})
            except ApiError as e:
                self._api_error(e)

        # ---- POST: login and logout ----
        def do_POST(self):
            path, _ = self._route()
            if not auth:
                return self._json(404, {"error": "not found"})
            if path == "/login":
                if not self._same_site():
                    return self._send(403, "Not allowed from another site.", "text/plain")
                form = parse_qs(self._body().decode("utf-8", "replace"))
                field = lambda k: (form.get(k) or [""])[0]
                rep = auth.check_login(field("user"), field("password"))
                if rep:
                    return self._redirect("/", [("Set-Cookie", auth.set_cookie_header(rep, self._secure()))])
                time.sleep(auth.fail_delay)
                self._send(401, render("Wrong name or password."), "text/html")
            elif path == "/logout":
                self._redirect("/login", [("Set-Cookie", auth.clear_cookie_header(self._secure()))])
            else:
                self._json(404, {"error": "not found"})

        # ---- PUT and DELETE: marks ----
        def do_PUT(self):
            path, q = self._route()
            if path != "/api/mark":
                return self._json(404, {"error": "not found"})
            if not self._write_checks(q):
                return
            if auth and not (self.headers.get("Content-Type") or "").startswith("application/json"):
                return self._json(415, {"error": "Send JSON."})
            try:
                b = json.loads(self._body() or b"{}")
                t = get_tool()
                marked_by = b.get("marked_by", "")
                if auth and marked_by not in {r["rep_id"] for r in t.h.reps}:  # the admin acts as a real rep, else as "admin"
                    marked_by = self._session()
                saved = t.put_mark(b.get("merchant_id", ""), b.get("mark", ""), b.get("reason", ""), marked_by)
                self._json(200, {"ok": True, "mark": saved})
            except (ValueError, KeyError, AttributeError) as e:
                self._json(400, {"error": str(e)})
            except ApiError as e:
                self._api_error(e)

        def do_DELETE(self):
            path, q = self._route()
            if path != "/api/mark":
                return self._json(404, {"error": "not found"})
            if not self._write_checks(q):
                return
            try:
                self._json(200, {"removed": get_tool().delete_mark((q.get("merchant_id") or [""])[0])})
            except ApiError as e:
                self._api_error(e)

    return Handler


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true", help="made-up data, nothing else needed")
    ap.add_argument("--data", help="folder with the data-pack CSV files (history)")
    ap.add_argument("--history-api", action="store_true", help="load the history from the API (4 tables, about 55 requests)")
    ap.add_argument("--tasks", help="routing input file with today's sold-outs (offline)")
    ap.add_argument("--live", action="store_true", help="read today's sold-outs from the API")
    ap.add_argument("--api-marks", action="store_true", help="keep marks in the sandbox through the API")
    ap.add_argument("--marks", default="marks.json", help="local marks file (default marks.json)")
    ap.add_argument("--findings", help="JSON file from the note reader: {merchant_id: {type, quote, ...}}")
    ap.add_argument("--auth", action="store_true", help="ask for the admin login (TOOL_PASSWORD and SESSION_SECRET in the environment)")
    ap.add_argument("--mode", choices=["demo", "test"])
    ap.add_argument("--config")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args(argv)

    cfg = cfgmod.load(args.config, **({"tool_mode": args.mode} if args.mode else {}))
    findings = json.loads(Path(args.findings).read_text(encoding="utf-8")) if args.findings else {}
    example = None
    if args.demo:
        history, tasks, demo_findings, seed = demo.tool_demo()
        marks, findings = MemoryMarks(seed), findings or demo_findings
    else:
        if not (args.data or args.history_api) or not (args.tasks or args.live):
            ap.error("use --demo, or a history (--data or --history-api) with tasks (--tasks or --live)")
        client = Client() if (args.live or args.api_marks or args.history_api) else None
        history = History(client.load_tables() if args.history_api else load_pack(args.data))
        tasks = LiveSource(LiveFeed(client, ttl=cfg["live_cache_seconds"])) if args.live \
            else load_routing_tasks(args.tasks, history.merchants)
        marks = CachedMarks(ApiMarks(client), ttl=cfg["live_cache_seconds"]) if args.api_marks else FileMarks(args.marks)
        if args.live:
            h2, t2, f2, s2 = demo.tool_demo()
            example = Tool(cfg, h2, t2, MemoryMarks(s2), f2)
    auth = None
    if args.auth:
        try:
            auth = Auth.from_env(os.environ)
        except ConfigError as e:
            ap.error(str(e))
    server = ThreadingHTTPServer((args.host, args.port),
                                 make_handler(Tool(cfg, history, tasks, marks, findings, example=example), PAGE.read_text(encoding="utf-8"), auth=auth))
    print(f"Rep tool ({cfg['tool_mode']} mode{', login on' if auth else ''}) on http://{args.host}:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
