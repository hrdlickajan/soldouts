"""Step 8. The rep tool: the ten statuses with reasons, test mode, marks round trip, a phone-sized page."""
import http.client
import json
import re
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from advice import config as cfgmod
from advice import demo
from advice.api import ApiError, ApiMarks, Client, FileMarks, MemoryMarks
from advice.engine import REASONS, STATUSES
from advice.tool import Tool, make_handler

PAGE = Path(__file__).resolve().parent.parent / "advice" / "static" / "index.html"


def make_tool(mode="demo", marks=None, **cfg):
    history, tasks, findings, seed = demo.tool_demo()
    return Tool(cfgmod.load(tool_mode=mode, **cfg), history, tasks, marks if marks is not None else MemoryMarks(seed), findings)


class FakeApi:
    """A stand-in for the sandbox API. Records every call. Needs no network."""

    def __init__(self):
        self.marks, self.calls = {}, []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, headers, body))
        path = url.split("/api/sandbox/v1")[-1]
        if method == "GET" and path == "/marks":
            return 200, {"data": [dict(merchant_id=m, **v) for m, v in self.marks.items()]}, {}
        m = re.fullmatch(r"/merchants/(\w+)/mark", path)
        if method == "PUT" and m:
            self.marks[m[1]] = json.loads(body)
            return 200, {"ok": True}, {}
        if method == "DELETE" and m:
            return (200, {"ok": True}, {}) if self.marks.pop(m[1], None) else (404, {"error": "no mark"}, {})
        return 404, {"error": "unexpected " + method + " " + path}, {}


class AllTenStatusesTest(unittest.TestCase):
    def test_demo_shows_all_ten_statuses_with_their_fixed_reasons(self):
        rows = make_tool().state()["rows"]
        seen = {r["status"] for r in rows}
        self.assertEqual(seen, set(STATUSES))
        for r in rows:
            self.assertEqual(r["reason"], REASONS[r["status"]])  # demo tasks carry callback and attempts: nothing unknown
            self.assertEqual((r["kind"], r["label"]), STATUSES[r["status"]][:2])

    def test_rows_show_range_quote_and_mark(self):
        rows = {r["merchant_id"]: r for r in make_tool().state()["rows"]}
        hv = next(r for r in rows.values() if r["status"] == "high_value")
        self.assertEqual(hv["gbp_low"], 0)
        self.assertGreater(hv["gbp_high"], 80)
        self.assertEqual(rows["M90010"]["quote"], "customers keep saying the booking page is broken")
        self.assertEqual(rows["M90011"]["mark"]["reason"], "Owner asked for a quiet month")
        self.assertEqual(rows["M90011"]["status"], "rep_marked_no_call")

    def test_promised_callbacks_come_first_and_skips_stay_visible(self):
        rows = make_tool().state()["rows"]
        cb = [i for i, r in enumerate(rows) if r["status"] == "callback_promised"]
        self.assertEqual(cb, list(range(len(cb))))
        self.assertIn("auto_top_up_soon", [r["status"] for r in rows])
        self.assertEqual(rows[-1]["kind"], "skip")


class TestModeTest(unittest.TestCase):
    def test_test_mode_shows_advice_only_for_group_b(self):
        rows = make_tool("test", share_new_routing=0.5).state()["rows"]
        hard = {"do_not_contact", "callback_promised", "rep_marked_no_call", "rep_marked_other"}
        shown_b = hidden_a = 0
        for r in rows:
            self.assertNotIn("group", r)  # reps do not see the group in test mode
            if r["status"] == "task":
                hidden_a += 1
                self.assertEqual((r["gbp_low"], r["gbp_high"], r["quote"]), (None, None, ""))
                self.assertEqual(r["label"], "Task")
            else:
                shown_b += r["status"] not in hard
        self.assertGreater(hidden_a, 0)
        self.assertGreater(shown_b, 0)
        # hard facts always show
        self.assertIn("do_not_contact", {r["status"] for r in rows})

    def test_demo_mode_shows_the_group_badge(self):
        rows = make_tool("demo").state()["rows"]
        self.assertTrue(all(r["group"] in ("A", "B") for r in rows))

    def test_share_zero_in_test_mode_shows_no_advice_at_all(self):
        rows = make_tool("test", share_new_routing=0).state()["rows"]
        self.assertFalse({r["status"] for r in rows} & {"high_value", "auto_top_up_soon", "worth_a_call"})


class MarksTest(unittest.TestCase):
    def test_marks_round_trip_against_a_stub_of_the_api(self):
        api = FakeApi()
        client = Client(base="http://stub/api/sandbox/v1", key="TEST-KEY", transport=api, sleep=lambda s: None)
        tool = make_tool(marks=ApiMarks(client))
        tool.put_mark("M90001", "no_call", "Owner is away", "R10")
        put = [c for c in api.calls if c[0] == "PUT"][0]
        self.assertTrue(put[1].endswith("/merchants/M90001/mark"))
        self.assertEqual(json.loads(put[3]), {"mark": "no_call", "reason": "Owner is away", "marked_by": "R10"})
        rows = {r["merchant_id"]: r for r in tool.state()["rows"]}
        self.assertEqual(rows["M90001"]["status"], "rep_marked_no_call")
        self.assertEqual(tool.state(rep_id="R10")["marks"][0]["merchant_id"], "M90001")
        self.assertTrue(tool.delete_mark("M90001"))
        self.assertFalse(tool.delete_mark("M90001"))  # 404 from the stub: nothing to remove
        rows = {r["merchant_id"]: r for r in tool.state()["rows"]}
        self.assertNotEqual(rows["M90001"]["status"], "rep_marked_no_call")

    def test_the_key_never_appears_in_output(self):
        client = Client(base="http://stub/api/sandbox/v1", key="TEST-KEY", transport=FakeApi())
        self.assertNotIn("TEST-KEY", repr(client))
        self.assertNotIn("TEST-KEY", json.dumps(make_tool(marks=ApiMarks(client)).state()))

    def test_only_marks_are_written_and_never_the_routing_switch(self):
        api = FakeApi()
        tool = make_tool(marks=ApiMarks(Client(base="http://stub/api/sandbox/v1", key="k", transport=api, sleep=lambda s: None)))
        tool.put_mark("M90001", "no_call", "why", "R10")
        tool.delete_mark("M90001")
        writes = [(c[0], c[1].split("/api/sandbox/v1")[-1]) for c in api.calls if c[0] != "GET"]
        self.assertEqual(writes, [("PUT", "/merchants/M90001/mark"), ("DELETE", "/merchants/M90001/mark")])

    def test_a_mark_needs_a_short_code_and_a_reason(self):
        tool = make_tool()
        for code, reason in (("", "why"), ("x" * 65, "why"), ("no_call", ""), ("no_call", "   ")):
            with self.assertRaises(ValueError):
                tool.put_mark("M90001", code, reason, "R10")

    def test_no_key_means_a_clear_error_not_a_crash_or_a_call(self):
        with self.assertRaises(ApiError):
            Client(base="", key="", transport=lambda *a: self.fail("must not call")).marks()

    def test_file_marks_survive_a_restart(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            FileMarks(Path(d) / "m.json").put("M1", "no_call", "why", "R10")
            self.assertEqual(FileMarks(Path(d) / "m.json").all()["M1"]["mark"], "no_call")


class RepTest(unittest.TestCase):
    def test_tasks_of_another_rep_are_hidden_when_the_merchant_has_a_rep(self):
        history, tasks, findings, seed = demo.tool_demo()
        history.merchants["M90001"] = {"merchant_id": "M90001", "rep_id": "R10"}
        history.merchants["M90002"] = {"merchant_id": "M90002", "rep_id": "R12"}
        tool = Tool(cfgmod.load(), history, tasks, MemoryMarks(), findings)
        mine = {r["merchant_id"] for r in tool.state(rep_id="R10")["rows"]}
        self.assertIn("M90001", mine)
        self.assertNotIn("M90002", mine)
        self.assertIn("M90003", mine)  # no rep known for this merchant: shown to everyone


class PageTest(unittest.TestCase):
    def test_page_is_made_for_a_phone(self):
        html = PAGE.read_text(encoding="utf-8")
        self.assertIn('<meta name="viewport" content="width=device-width, initial-scale=1">', html)
        self.assertNotIn("<table", html)                      # tables push the page wider than a phone
        self.assertRegex(html, r"overflow-wrap\s*:\s*anywhere")  # a long name must not widen the page
        for px in re.findall(r"(?:min-)?width\s*:\s*(\d+)px", html):
            self.assertLessEqual(int(px), 320)
        self.assertIn("textContent", html)                    # notes and quotes are never put in as HTML
        self.assertNotIn("innerHTML", html)

    def test_server_serves_the_page_and_the_json(self):
        tool = make_tool()
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(tool, PAGE.read_text(encoding="utf-8")))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            def call(method, path, body=None):
                c = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                c.request(method, path, body)
                r = c.getresponse()
                out = r.status, r.read().decode()
                c.close()
                return out
            status, body = call("GET", "/")
            self.assertEqual(status, 200)
            self.assertIn("viewport", body)
            status, body = call("GET", "/api/state")
            self.assertEqual(len(json.loads(body)["rows"]), 28)
            mark = {"merchant_id": "M90001", "mark": "no_call", "reason": "r", "marked_by": "R10"}
            self.assertEqual(call("PUT", "/api/mark", json.dumps(mark))[0], 200)
            self.assertEqual(call("PUT", "/api/mark", json.dumps(dict(mark, mark="")))[0], 400)
            self.assertEqual(call("DELETE", "/api/mark?merchant_id=M90001")[0], 200)
            self.assertEqual(call("GET", "/nope")[0], 404)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
