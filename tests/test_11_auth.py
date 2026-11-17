"""Step 12. The hosted tool: login with a signed cookie, a guard on every route, the rep comes from the session.

Every test uses a fake transport and a local server on a free port. Nothing here calls the network or needs a key.
"""
import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode

from advice import config as cfgmod
from advice import demo
from advice.api import ApiError, MemoryMarks
from advice.auth import Auth, ConfigError
from advice.feed import LiveFeed
from advice.tool import LiveSource, Tool, make_handler
from advice.web import build_handler
from tests.test_10_live import BASE, Script, client, live_row

PAGE = (Path(__file__).resolve().parent.parent / "advice" / "static" / "index.html").read_text(encoding="utf-8")
SECRET = "s" * 32


def demo_tool(example=True):
    history, tasks, findings, seed = demo.tool_demo()
    ex = None
    if example:
        h2, t2, f2, s2 = demo.tool_demo()
        ex = Tool(cfgmod.load(), h2, t2, MemoryMarks(s2), f2)
    return Tool(cfgmod.load(), history, tasks, MemoryMarks(seed), findings, example=ex)


class Resp:
    def __init__(self, r):
        self.status, self.body, self.headers = r.status, r.read().decode("utf-8"), r
        self.cookie = r.getheader("Set-Cookie")
        self.location = r.getheader("Location")

    def json(self):
        return json.loads(self.body)


class Running:
    """A server on a free port. Use as a context manager."""

    def __init__(self, handler):
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.srv.server_port

    def __enter__(self):
        threading.Thread(target=lambda: self.srv.serve_forever(poll_interval=0.01), daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.srv.shutdown()
        self.srv.server_close()

    def call(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request(method, path, body, headers or {})
        out = Resp(c.getresponse())
        c.close()
        return out

    def login(self, user="admin", password="demo-password"):
        r = self.call("POST", "/login", urlencode({"user": user, "password": password}),
                      {"Content-Type": "application/x-www-form-urlencoded"})
        return r, (r.cookie or "").split(";")[0]


class AuthUnitTest(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.auth = Auth("demo-password", SECRET, clock=lambda: self.now, fail_delay=0)

    def test_only_the_admin_name_with_the_right_password_logs_in(self):
        self.assertEqual(self.auth.check_login("admin", "demo-password"), "admin")
        self.assertEqual(self.auth.check_login(" Admin ", "demo-password"), "admin")  # case and spaces do not matter

    def test_wrong_or_odd_input_does_not(self):
        for user, pw in (("admin", "nope"), ("admin", ""), ("", "demo-password"), ("R10", "demo-password"),
                         ("x" * 40, "demo-password"), (None, None), ("admin", None)):
            self.assertIsNone(self.auth.check_login(user, pw), (user, pw))

    def test_a_cookie_round_trips_and_a_changed_one_does_not(self):
        value = self.auth.make_cookie("R10")
        self.assertEqual(self.auth.read_cookie("a=1; session=" + value + "; b=2"), "R10")
        rep, exp, sig = value.split(".")
        for bad in (f"R11.{exp}.{sig}", f"{rep}.{int(exp) + 99999}.{sig}", f"{rep}.{exp}.{sig[:-1]}0", f"{rep}.{exp}", "", "a.b.c"):
            self.assertIsNone(self.auth.read_cookie("session=" + bad), bad)
        self.assertIsNone(self.auth.read_cookie(None))
        self.assertIsNone(self.auth.read_cookie("other=1"))

    def test_a_cookie_ends(self):
        value = self.auth.make_cookie("R10")
        self.now += 12 * 3600 - 1
        self.assertEqual(self.auth.read_cookie("session=" + value), "R10")
        self.now += 2
        self.assertIsNone(self.auth.read_cookie("session=" + value))

    def test_a_cookie_from_another_secret_is_refused(self):
        other = Auth("demo-password", "t" * 32, clock=lambda: self.now)
        self.assertIsNone(self.auth.read_cookie("session=" + other.make_cookie("R10")))

    def test_the_cookie_header_is_safe(self):
        h = self.auth.set_cookie_header("R10", secure=False)
        self.assertTrue(h.startswith("session="))
        for part in ("HttpOnly", "SameSite=Lax", "Path=/", "Max-Age=43200"):
            self.assertIn(part, h)
        self.assertNotIn("Secure", h)
        self.assertIn("Secure", self.auth.set_cookie_header("R10", secure=True))
        self.assertIn("Max-Age=0", self.auth.clear_cookie_header(secure=False))

    def test_the_config_needs_a_password_and_a_long_secret(self):
        with self.assertRaises(ConfigError) as cm:
            Auth.from_env({})
        self.assertIn("TOOL_PASSWORD", str(cm.exception))
        self.assertIn("SESSION_SECRET", str(cm.exception))
        with self.assertRaises(ConfigError) as cm:
            Auth.from_env({"TOOL_PASSWORD": "demo-password", "SESSION_SECRET": "tiny-secret"})
        self.assertNotIn("tiny-secret", str(cm.exception))         # the message never shows a value
        a = Auth.from_env({"TOOL_PASSWORD": "demo-password", "SESSION_SECRET": SECRET})
        self.assertEqual(a.check_login("admin", "demo-password"), "admin")


class GuardedRoutesTest(unittest.TestCase):
    def serve(self, tool=None):
        auth = Auth("demo-password", SECRET, fail_delay=0)
        return Running(make_handler(tool or demo_tool(), PAGE, auth=auth))

    def test_nothing_but_the_style_sheet_and_the_login_is_open(self):
        with self.serve() as s:
            r = s.call("GET", "/")
            self.assertEqual((r.status, r.location), (303, "/login"))
            self.assertEqual(s.call("GET", "/api/state").status, 401)
            self.assertEqual(s.call("PUT", "/api/mark", "{}", {"Content-Type": "application/json"}).status, 401)
            self.assertEqual(s.call("DELETE", "/api/mark?merchant_id=M1").status, 401)
            self.assertEqual(s.call("GET", "/theme.css").status, 200)
            login = s.call("GET", "/login")
            self.assertEqual(login.status, 200)
            for needle in ('name="user"', 'name="password"', 'action="/login"', 'name="viewport"'):
                self.assertIn(needle, login.body)

    def test_a_wrong_password_gives_no_cookie_and_no_echo(self):
        with self.serve() as s:
            r, _ = s.login("<script>alert(1)</script>", "nope")
            self.assertEqual(r.status, 401)
            self.assertIsNone(r.cookie)
            self.assertIn("Wrong name or password", r.body)
            self.assertNotIn("<script>alert", r.body)

    def test_a_good_login_opens_the_page_and_the_state(self):
        with self.serve() as s:
            r, cookie = s.login()
            self.assertEqual((r.status, r.location), (303, "/"))
            self.assertIn("HttpOnly", r.cookie)
            self.assertIn("SameSite=Lax", r.cookie)
            self.assertIn("viewport", s.call("GET", "/", headers={"Cookie": cookie}).body)
            state = s.call("GET", "/api/state", headers={"Cookie": cookie}).json()
            self.assertTrue(state["auth"])
            self.assertEqual(state["me"], {"rep_id": "admin", "rep_name": "Admin"})
            self.assertEqual(s.call("GET", "/login", headers={"Cookie": cookie}).location, "/")   # already in

    def test_a_changed_cookie_is_refused(self):
        with self.serve() as s:
            _, cookie = s.login()
            self.assertEqual(s.call("GET", "/api/state", headers={"Cookie": cookie[:-1] + "0"}).status, 401)

    def test_logout_ends_the_session_in_the_browser(self):
        with self.serve() as s:
            _, cookie = s.login()
            r = s.call("POST", "/logout", "", {"Cookie": cookie})
            self.assertEqual((r.status, r.location), (303, "/login"))
            self.assertIn("Max-Age=0", r.cookie)

    def test_the_admin_marks_as_a_real_rep_and_an_unknown_name_becomes_admin(self):
        tool = demo_tool()
        with self.serve(tool) as s:
            _, cookie = s.login()
            h = {"Content-Type": "application/json", "Cookie": cookie}
            mark = lambda by: json.dumps({"merchant_id": "M90001", "mark": "no_call", "reason": "r", "marked_by": by})
            self.assertEqual(s.call("PUT", "/api/mark", mark("R11"), h).status, 200)
            self.assertEqual(tool.marks.all()["M90001"]["marked_by"], "R11")
            self.assertEqual(s.call("PUT", "/api/mark", mark("R99"), h).status, 200)
            self.assertEqual(tool.marks.all()["M90001"]["marked_by"], "admin")

    def test_a_write_from_another_site_is_refused(self):
        with self.serve() as s:
            _, cookie = s.login()
            body = json.dumps({"merchant_id": "M90001", "mark": "no_call", "reason": "r"})
            evil = {"Content-Type": "application/json", "Cookie": cookie, "Origin": "http://evil.example"}
            self.assertEqual(s.call("PUT", "/api/mark", body, evil).status, 403)
            self.assertEqual(s.call("DELETE", "/api/mark?merchant_id=M90011", headers={"Cookie": cookie, "Origin": "http://evil.example"}).status, 403)
            same = dict(evil, Origin=f"http://127.0.0.1:{s.port}")
            self.assertEqual(s.call("PUT", "/api/mark", body, same).status, 200)

    def test_a_write_must_be_json(self):
        with self.serve() as s:
            _, cookie = s.login()
            r = s.call("PUT", "/api/mark", "merchant_id=M1", {"Content-Type": "text/plain", "Cookie": cookie})
            self.assertEqual(r.status, 415)

    def test_the_hosted_route_parameter_reaches_the_right_route(self):
        with self.serve() as s:
            _, cookie = s.login()
            h = {"Cookie": cookie}
            self.assertIn("viewport", s.call("GET", "/api/index?__p=", headers=h).body)
            self.assertIn("rows", s.call("GET", "/api/index?__p=api/state", headers=h).json())
            self.assertEqual(s.call("GET", "/api/index?__p=login").status, 200)
            self.assertEqual(s.call("GET", "/api/index?__p=api/state").status, 401)  # still guarded

    def test_pages_are_not_kept_by_the_phone_or_a_proxy(self):
        with self.serve() as s:
            _, cookie = s.login()
            r = s.call("GET", "/api/state", headers={"Cookie": cookie})
            self.assertEqual(r.headers.getheader("Cache-Control"), "no-store")
            self.assertEqual(r.headers.getheader("X-Content-Type-Options"), "nosniff")

    def test_the_dropdown_gets_every_rep(self):
        with self.serve() as s:
            _, cookie = s.login()
            state = s.call("GET", "/api/state", headers={"Cookie": cookie}).json()
            self.assertEqual([r["rep_id"] for r in state["reps"]], ["R10", "R11", "R12"])


class ExampleAndErrorsTest(unittest.TestCase):
    def serve(self, tool, auth=True):
        return Running(make_handler(tool, PAGE, auth=Auth("demo-password", SECRET, fail_delay=0) if auth else None))

    def test_example_tasks_are_read_only(self):
        with self.serve(demo_tool()) as s:
            _, cookie = s.login()
            h = {"Cookie": cookie}
            ex = s.call("GET", "/api/state?example=1", headers=h).json()
            self.assertTrue(ex["example"])
            self.assertEqual(len(ex["rows"]), 28)
            body = json.dumps({"merchant_id": "M90001", "mark": "no_call", "reason": "r"})
            r = s.call("PUT", "/api/mark?example=1", body, dict(h, **{"Content-Type": "application/json"}))
            self.assertEqual(r.status, 400)
            self.assertFalse(s.call("GET", "/api/state", headers=h).json().get("example"))

    def test_no_example_data_means_not_found(self):
        with self.serve(demo_tool(example=False)) as s:
            _, cookie = s.login()
            self.assertEqual(s.call("GET", "/api/state?example=1", headers={"Cookie": cookie}).status, 404)

    def test_an_api_that_is_down_gives_a_clear_503_not_a_dropped_connection(self):
        c = client({("GET", "/soldouts/today"): ApiError(0, "network: down")})
        tool = Tool(cfgmod.load(), demo.tool_demo()[0], LiveSource(LiveFeed(c)), MemoryMarks())
        with self.serve(tool) as s:
            _, cookie = s.login()
            r = s.call("GET", "/api/state", headers={"Cookie": cookie})
            self.assertEqual(r.status, 503)
            self.assertIn("network: down", r.json()["error"])
            self.assertTrue(r.json()["retry"])

    def test_a_failed_mark_save_is_a_502(self):
        class Broken(MemoryMarks):
            def put(self, *a):
                raise ApiError(500, "boom")

        history, tasks, findings, seed = demo.tool_demo()
        with self.serve(Tool(cfgmod.load(), history, tasks, Broken(seed), findings)) as s:
            _, cookie = s.login()
            body = json.dumps({"merchant_id": "M90001", "mark": "no_call", "reason": "r"})
            r = s.call("PUT", "/api/mark", body, {"Content-Type": "application/json", "Cookie": cookie})
            self.assertEqual(r.status, 502)

    def test_without_auth_the_local_tool_works_as_before(self):
        with self.serve(demo_tool(), auth=False) as s:
            self.assertEqual(s.call("GET", "/").status, 200)
            state = s.call("GET", "/api/state").json()
            self.assertFalse(state["auth"])
            self.assertEqual(len(state["rows"]), 28)
            self.assertEqual(s.call("GET", "/login").status, 404)


def api_routes():
    paged = lambda rows: (200, {"data": rows, "next_cursor": None, "total": len(rows)})
    merchant = lambda m, rep: {"merchant_id": m, "merchant_name": f"Merchant {m}", "size_band": "B", "rep_id": rep, "do_not_contact": False}
    return {
        ("GET", "/merchants"): paged([merchant("M10001", "R10"), merchant("M10002", "R11")]),
        ("GET", "/reps"): paged([{"rep_id": "R10", "rep_name": "Rep Ten", "team": "N"}, {"rep_id": "R11", "rep_name": "Rep Eleven", "team": "N"}]),
        ("GET", "/automation/schedules"): paged([]),
        ("GET", "/soldouts"): paged([]),
        ("GET", "/soldouts/today"): (200, {"date": "2026-11-11", "team_time": "09:30", "data": [live_row(1, "M10001", "R10"), live_row(2, "M10002", "R11")],
                                           "next_cursor": None, "total": 2}),
        ("GET", "/marks"): (200, {"data": []}),
        ("PUT", "/merchants/M10001/mark"): lambda path, body: (200, dict(json.loads(body), merchant_id="M10001", marked_at="2026-11-11T09:00:00Z")),
        ("DELETE", "/merchants/M10001/mark"): (200, {"merchant_id": "M10001", "removed": True}),
    }


ENV = {"TOOL_PASSWORD": "demo-password", "SESSION_SECRET": SECRET, "GROUPON_API_BASE": BASE, "GROUPON_API_KEY": "TEST-KEY"}


class HostedAppTest(unittest.TestCase):
    """build_handler: what the Vercel entry file serves, with the sandbox API replaced by a fake."""

    def test_a_missing_setting_fails_closed(self):
        for env in ({}, {"TOOL_PASSWORD": "demo-password"}, {"TOOL_PASSWORD": "demo-password", "SESSION_SECRET": "tiny-secret"}):
            with Running(build_handler(env)) as s:
                for path in ("/", "/login", "/api/state"):
                    r = s.call("GET", path)
                    self.assertEqual(r.status, 503, (env, path))
                    self.assertNotIn("tiny-secret", r.body)
                    self.assertNotIn("demo-password", r.body)
                self.assertIn("SESSION_SECRET", s.call("GET", "/").body)

    def test_the_whole_flow_against_a_fake_api(self):
        api = Script(api_routes())
        with Running(build_handler(ENV, transport=api, sleep=lambda s: None)) as s:
            r, cookie = s.login()
            self.assertEqual(r.status, 303)
            h = {"Cookie": cookie}
            mine = s.call("GET", "/api/state?rep=R10", headers=h).json()
            self.assertEqual([x["merchant_id"] for x in mine["rows"]], ["M10001"])
            self.assertEqual(mine["me"], {"rep_id": "admin", "rep_name": "Admin"})
            self.assertEqual([r["rep_id"] for r in mine["reps"]], ["R10", "R11"])        # every rep, for the dropdown
            self.assertEqual(mine["meta"]["source"], "live")
            self.assertEqual(mine["meta"]["team_time"], "09:30")
            self.assertTrue(mine["meta"]["example_available"])
            everyone = s.call("GET", "/api/state", headers=h).json()
            self.assertEqual(len(everyone["rows"]), 2)
            self.assertEqual(sum(1 for c in api.calls if c[1].startswith("/merchants?")), 1)   # history loaded once

            body = json.dumps({"merchant_id": "M10001", "mark": "no_call", "reason": "Owner asked", "marked_by": "R10"})
            put = s.call("PUT", "/api/mark", body, dict(h, **{"Content-Type": "application/json"}))
            self.assertEqual(put.status, 200)
            marked = s.call("GET", "/api/state?rep=R10", headers=h).json()
            row = marked["rows"][0]
            self.assertEqual((row["status"], row["mark"]["marked_by"]), ("rep_marked_no_call", "R10"))
            self.assertEqual(row["mark"]["marked_at"], "2026-11-11T09:00:00Z")
            self.assertEqual(len([c for c in api.calls if c[1] == "/marks"]), 1)               # no extra read after our own save
            gone = s.call("DELETE", "/api/mark?merchant_id=M10001", headers=h)
            self.assertEqual(gone.status, 200)
            self.assertEqual(s.call("GET", "/api/state?rep=R10", headers=h).json()["rows"][0]["mark"], None)

    def test_only_marks_are_written_and_never_the_routing_switch(self):
        api = Script(api_routes())
        with Running(build_handler(ENV, transport=api, sleep=lambda s: None)) as s:
            _, cookie = s.login()
            h = {"Cookie": cookie}
            s.call("GET", "/api/state", headers=h)
            s.call("PUT", "/api/mark", json.dumps({"merchant_id": "M10001", "mark": "no_call", "reason": "r"}), dict(h, **{"Content-Type": "application/json"}))
            s.call("DELETE", "/api/mark?merchant_id=M10001", headers=h)
        writes = {(m, p) for m, p in api.calls if m != "GET"}
        self.assertEqual(writes, {("PUT", "/merchants/M10001/mark"), ("DELETE", "/merchants/M10001/mark")})

    def test_the_login_page_works_before_the_history_is_loaded(self):
        api = Script(api_routes())
        with Running(build_handler(ENV, transport=api, sleep=lambda s: None)) as s:
            self.assertEqual(s.call("GET", "/login").status, 200)
            self.assertEqual(api.calls, [])                       # no API call for the login page

    def test_a_missing_api_key_is_a_clear_503_after_login(self):
        env = {k: v for k, v in ENV.items() if k != "GROUPON_API_KEY"}
        with Running(build_handler(env)) as s:
            _, cookie = s.login()
            r = s.call("GET", "/api/state", headers={"Cookie": cookie})
            self.assertEqual(r.status, 503)
            self.assertNotIn("TEST-KEY", r.body)

    def test_the_cookie_is_secure_behind_https(self):
        with Running(build_handler(ENV, transport=Script(api_routes()), sleep=lambda s: None)) as s:
            r = s.call("POST", "/login", urlencode({"user": "admin", "password": "demo-password"}),
                       {"Content-Type": "application/x-www-form-urlencoded", "X-Forwarded-Proto": "https"})
            self.assertIn("Secure", r.cookie)


if __name__ == "__main__":
    unittest.main()


class VercelEntryTest(unittest.TestCase):
    """api/index.py is what Vercel builds. Vercel finds the handler by reading the file, so the class must be written out."""
    ENTRY = Path(__file__).resolve().parent.parent / "api" / "index.py"

    def test_the_handler_class_is_written_out_where_vercel_can_see_it(self):
        text = self.ENTRY.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^class handler\(BaseHTTPRequestHandler\):")

    def _load(self, env):
        import importlib.util
        import os
        from unittest import mock
        spec = importlib.util.spec_from_file_location("vercel_entry_under_test", self.ENTRY)
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(os.environ, env, clear=True):
            spec.loader.exec_module(module)
        return module.handler

    def test_without_settings_the_entry_answers_503_everywhere(self):
        with Running(self._load({})) as s:
            for path in ("/", "/login", "/api/state"):
                self.assertEqual(s.call("GET", path).status, 503, path)

    def test_with_settings_the_entry_serves_the_login_and_guards_the_rest(self):
        with Running(self._load(dict(ENV))) as s:
            self.assertEqual(s.call("GET", "/login").status, 200)
            self.assertEqual(s.call("GET", "/").status, 303)
            self.assertEqual(s.call("GET", "/api/state").status, 401)
            r, cookie = s.login()
            self.assertEqual(r.status, 303)
