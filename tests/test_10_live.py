"""Step 11. The live feed on a phone: a safe client, history from the API, a short cache, a stale copy, bad rows.

Every test uses a fake transport. Nothing here calls the network or needs a key.
"""
import threading
import time
import unittest

from advice import config as cfgmod
from advice.adapters import to_task
from advice.api import ApiError, ApiMarks, CachedMarks, Client, MemoryMarks
from advice.engine import Engine
from advice.feed import FeedError, LiveFeed
from advice.history import History
from advice.tool import LiveSource, Tool

BASE = "http://stub/api/sandbox/v1"


def live_row(n=1, merchant="M10001", rep="R10", **kw):
    """A row of GET /soldouts/today, as the OpenAPI file in the sandbox describes it."""
    row = {"sold_out_id": f"SO-{n}", "restock_task_id": f"RT-{n}", "deal_id": f"D{merchant[1:]}-{n}",
           "deal_name": f"Deal number {n}", "merchant_id": merchant, "merchant_name": f"Merchant {merchant}",
           "category": "Health & Beauty", "region": "North West", "city": "Manchester", "size_band": "B",
           "rep_id": rep, "rep_name": f"Rep {rep}", "do_not_contact": False, "cap": 60,
           "sold_out_at": "2026-11-11T09:14:00.000Z", "team_time": "09:14", "world_day": "d2", "posted_in_channel": True}
    row.update(kw)
    return row


class Script:
    """A fake transport. routes: (method, path without query) -> (status, payload) | exception | list of those | function.

    A list is used up from the front and its last item then repeats. Every call is recorded as (method, path).
    """

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, method, url, headers, body):
        path = url.split("/api/sandbox/v1")[-1]
        self.calls.append((method, path))
        out = self.routes[(method, path.split("?")[0])]
        if isinstance(out, list):
            out = out.pop(0) if len(out) > 1 else out[0]
        if callable(out):
            out = out(path, body)
        if isinstance(out, Exception):
            raise out
        status, payload = out
        return status, payload, {}


def client(routes, **kw):
    return Client(base=BASE, key="TEST-KEY", transport=Script(routes), sleep=lambda s: None, **kw)


class ClientSafetyTest(unittest.TestCase):
    def test_a_network_error_is_an_api_error_and_a_read_is_tried_twice(self):
        c = client({("GET", "/me"): ApiError(0, "network: timed out")})
        with self.assertRaises(ApiError) as cm:
            c.request("GET", "/me")
        self.assertEqual(cm.exception.status, 0)
        self.assertEqual(len(c._transport.calls), 2)

    def test_a_read_that_gets_503_once_then_works(self):
        c = client({("GET", "/me"): [(503, {"error": "busy"}), (200, {"ok": 1})]})
        self.assertEqual(c.request("GET", "/me"), {"ok": 1})
        self.assertEqual(len(c._transport.calls), 2)

    def test_a_write_is_never_tried_twice(self):
        c = client({("PUT", "/merchants/M1/mark"): (503, {"error": "busy"})})
        with self.assertRaises(ApiError):
            c.put_mark("M1", "no_call", "why", "R10")
        self.assertEqual(len(c._transport.calls), 1)

    def test_the_cursor_is_url_encoded(self):
        pages = [(200, {"data": [{"a": 1}], "next_cursor": "a b+c=", "total": 2}),
                 (200, {"data": [{"a": 2}], "next_cursor": None, "total": 2})]
        c = client({("GET", "/reps"): pages})
        self.assertEqual(len(c.reps()), 2)
        self.assertIn("cursor=a+b%2Bc%3D", c._transport.calls[1][1])

    def test_the_limiter_holds_when_two_phones_ask_at_once(self):
        c = Client(base=BASE, key="k", transport=lambda *a: (200, {"ok": True}, {}), per_second=50)
        started = time.monotonic()
        threads = [threading.Thread(target=lambda: [c.request("GET", "/me") for _ in range(5)]) for _ in range(4)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertGreaterEqual(time.monotonic() - started, 0.30)  # 20 requests at 50 a second need 0.38 seconds

    def test_the_timeout_is_short(self):
        self.assertLessEqual(Client(base=BASE, key="k").timeout, 10)

    def test_today_comes_with_the_team_clock(self):
        page = {"world_day": "d2", "date": "2026-11-11", "team_time": "01:36", "data": [live_row()], "next_cursor": None, "total": 1}
        rows, meta = client({("GET", "/soldouts/today"): (200, page)}).soldouts_today_page()
        self.assertEqual(len(rows), 1)
        self.assertEqual(meta, {"world_day": "d2", "date": "2026-11-11", "team_time": "01:36", "total": 1})


class HistoryFromApiTest(unittest.TestCase):
    def test_four_tables_come_from_the_api_and_build_a_history(self):
        paged = lambda rows: (200, {"data": rows, "next_cursor": None, "total": len(rows)})
        so = lambda n, d, r, gp: {"sold_out_id": f"SO-{n}", "deal_id": "D10001-1", "merchant_id": "M10001", "sold_out_date": d,
                                  "cap": 60, "restocked_date": r, "new_cap": 70, "gp_30d_after_gbp": gp}
        c = client({
            ("GET", "/merchants"): paged([{"merchant_id": "M10001", "merchant_name": "Bright Skin", "size_band": "A",
                                           "rep_id": "R10", "do_not_contact": False}]),
            ("GET", "/reps"): paged([{"rep_id": "R10", "rep_name": "Rep Ten", "team": "N"}]),
            ("GET", "/automation/schedules"): paged([{"schedule_id": "S1", "deal_id": "D10001-1", "start_date": "2026-01-01",
                                                      "end_date": None, "cadence": "weekly"}]),
            ("GET", "/soldouts"): [(200, {"data": [so(1, "2026-09-01", "2026-09-05", 26)], "next_cursor": "c2", "total": 2}),
                                   paged([so(2, "2026-09-10", "2026-09-12", 28)])],
        })
        tables = c.load_tables()
        self.assertEqual(set(tables), {"merchants", "reps", "schedules", "sold_outs"})
        h = History(tables)
        self.assertEqual(h.merchants["M10001"]["merchant_name"], "Bright Skin")
        self.assertAlmostEqual(h.merchant_pd("M10001"), 1.0)  # 26 / (30 - 4) and 28 / (30 - 2)
        self.assertEqual(h.cadence_on("D10001-1", to_task(live_row()).sold_out_date), "weekly")

    def test_one_failed_table_fails_the_whole_load(self):
        paged = (200, {"data": [], "next_cursor": None, "total": 0})
        c = client({("GET", "/merchants"): paged, ("GET", "/reps"): paged, ("GET", "/automation/schedules"): paged,
                    ("GET", "/soldouts"): (500, {"error": "boom"})})
        with self.assertRaises(ApiError):
            c.load_tables()


class FeedTest(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        page = {"date": "2026-11-11", "team_time": "09:30", "world_day": "d2", "data": [live_row()], "next_cursor": None, "total": 1}
        self.routes = {("GET", "/soldouts/today"): (200, page)}
        self.c = client(self.routes)
        self.feed = LiveFeed(self.c, ttl=30, retry_after=10, clock=lambda: self.now)
        self.calls = lambda: len(self.c._transport.calls)

    def test_it_keeps_the_list_for_the_cache_time_and_then_asks_again(self):
        self.feed.get()
        self.now += 29
        self.feed.get()
        self.assertEqual(self.calls(), 1)
        self.now += 2
        self.feed.get()
        self.assertEqual(self.calls(), 2)

    def test_it_reports_what_the_page_needs(self):
        rows, meta = self.feed.get()
        self.assertEqual(len(rows), 1)
        self.assertEqual((meta["source"], meta["date"], meta["team_time"], meta["total"]), ("live", "2026-11-11", "09:30", 1))
        self.assertFalse(meta["stale"])
        self.assertIsNone(meta["error"])
        self.assertTrue(meta["updated_at"])

    def test_force_asks_again_at_once(self):
        self.feed.get()
        self.feed.get(force=True)
        self.assertEqual(self.calls(), 2)

    def test_when_the_api_fails_the_last_list_is_shown_as_stale(self):
        self.feed.get()
        self.routes[("GET", "/soldouts/today")] = ApiError(0, "network: down")
        self.now += 31
        rows, meta = self.feed.get()
        self.assertEqual(len(rows), 1)
        self.assertTrue(meta["stale"])
        self.assertIn("network: down", meta["error"])

    def test_after_a_failure_it_waits_before_it_calls_again(self):
        self.feed.get()
        self.routes[("GET", "/soldouts/today")] = ApiError(0, "network: down")
        self.now += 31
        self.feed.get()
        before = self.calls()
        self.now += 5
        self.assertTrue(self.feed.get()[1]["stale"])
        self.assertEqual(self.calls(), before)        # inside the wait: no call
        self.now += 6
        self.feed.get()
        self.assertGreater(self.calls(), before)      # after the wait: it tries again

    def test_force_ignores_the_wait(self):
        self.feed.get()
        self.routes[("GET", "/soldouts/today")] = ApiError(0, "network: down")
        self.now += 31
        self.feed.get()
        before = self.calls()
        self.feed.get(force=True)
        self.assertGreater(self.calls(), before)

    def test_with_no_list_yet_a_failure_is_an_error(self):
        self.routes[("GET", "/soldouts/today")] = ApiError(0, "network: down")
        with self.assertRaises(FeedError):
            self.feed.get()

    def test_it_recovers_when_the_api_is_back(self):
        self.routes[("GET", "/soldouts/today")] = ApiError(0, "network: down")
        with self.assertRaises(FeedError):
            self.feed.get()
        self.routes[("GET", "/soldouts/today")] = (200, {"data": [], "next_cursor": None, "total": 0, "team_time": "10:00"})
        rows, meta = self.feed.get()
        self.assertEqual((rows, meta["stale"], meta["total"]), ([], False, 0))


class CachedMarksTest(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.inner = MemoryMarks({"M1": {"mark": "no_call", "reason": "r", "marked_by": "R10"}})
        self.reads = 0
        real_all = self.inner.all

        def counting_all():
            self.reads += 1
            return real_all()

        self.inner.all = counting_all
        self.marks = CachedMarks(self.inner, ttl=30, clock=lambda: self.now)

    def test_it_reads_the_marks_once_inside_the_cache_time(self):
        self.marks.all()
        self.marks.all()
        self.assertEqual(self.reads, 1)
        self.now += 31
        self.marks.all()
        self.assertEqual(self.reads, 2)

    def test_our_own_save_and_remove_show_at_once_without_another_read(self):
        self.marks.all()
        self.marks.put("M2", "call_first", "big deal", "R10")
        self.assertIn("M2", self.marks.all())
        self.assertTrue(self.marks.delete("M1"))
        self.assertNotIn("M1", self.marks.all())
        self.assertEqual(self.reads, 1)
        self.assertIn("M2", self.inner.all())          # and the real store has it

    def test_when_the_api_fails_the_last_marks_stay(self):
        self.marks.all()
        self.inner.all = lambda: (_ for _ in ()).throw(ApiError(0, "network: down"))
        self.now += 31
        self.assertIn("M1", self.marks.all())
        self.assertIn("network: down", self.marks.error)

    def test_with_no_marks_yet_a_failure_is_raised(self):
        self.inner.all = lambda: (_ for _ in ()).throw(ApiError(0, "network: down"))
        with self.assertRaises(ApiError):
            self.marks.all()

    def test_the_api_save_keeps_the_time_the_api_gives(self):
        saved = {}

        class Fake:
            def put_mark(self, merchant_id, mark, reason, marked_by):
                return {"merchant_id": merchant_id, "mark": mark, "reason": reason, "marked_by": marked_by,
                        "marked_at": "2026-11-11T09:00:00Z"}

            def marks(self):
                return []

        m = CachedMarks(ApiMarks(Fake()), ttl=30, clock=lambda: 0.0)
        m.all()
        m.put("M9", "no_call", "why", "R10")
        self.assertEqual(m.all()["M9"]["marked_at"], "2026-11-11T09:00:00Z")


class LiveToolTest(unittest.TestCase):
    def make(self, rows, **page):
        body = dict({"date": "2026-11-11", "team_time": "09:30", "data": rows, "next_cursor": None, "total": len(rows)}, **page)
        c = client({("GET", "/soldouts/today"): (200, body)})
        feed = LiveFeed(c, ttl=30)
        history = History({"reps": [{"rep_id": "R10", "rep_name": "Rep Ten"}, {"rep_id": "R11", "rep_name": "Rep Eleven"}]})
        return Tool(cfgmod.load(), history, LiveSource(feed), MemoryMarks()), feed

    def test_a_bad_row_is_skipped_and_counted_not_fatal(self):
        bad = live_row(3)
        del bad["sold_out_at"]
        tool, _ = self.make([live_row(1), live_row(2, merchant="M10002"), bad])
        state = tool.state()
        self.assertEqual(len(state["rows"]), 2)
        self.assertEqual(state["meta"]["skipped"], 1)

    def test_a_live_row_shows_the_deal_name_the_city_and_the_time(self):
        tool, _ = self.make([live_row(1)])
        row = tool.state()["rows"][0]
        self.assertEqual((row["deal_name"], row["city"], row["sold_out_time"]), ("Deal number 1", "Manchester", "09:14"))

    def test_a_rep_sees_the_rows_that_carry_their_rep_id(self):
        tool, _ = self.make([live_row(1, "M10001", "R10"), live_row(2, "M10002", "R11")])
        self.assertEqual([r["merchant_id"] for r in tool.state("R10")["rows"]], ["M10001"])
        self.assertEqual(len(tool.state()["rows"]), 2)

    def test_an_empty_feed_is_a_normal_state_with_the_team_clock(self):
        tool, _ = self.make([], team_time="01:36")
        state = tool.state()
        self.assertEqual(state["rows"], [])
        self.assertEqual((state["meta"]["source"], state["meta"]["team_time"]), ("live", "01:36"))

    def test_the_feed_error_reaches_the_caller_when_there_is_no_list(self):
        c = client({("GET", "/soldouts/today"): ApiError(0, "network: down")})
        tool = Tool(cfgmod.load(), History({}), LiveSource(LiveFeed(c)), MemoryMarks())
        with self.assertRaises(FeedError):
            tool.state()

    def test_stale_and_marks_error_are_passed_on(self):
        now = [0.0]
        body = {"data": [live_row()], "next_cursor": None, "total": 1}
        routes = {("GET", "/soldouts/today"): (200, body)}
        feed = LiveFeed(client(routes), ttl=30, retry_after=10, clock=lambda: now[0])
        tool = Tool(cfgmod.load(), History({}), LiveSource(feed), MemoryMarks())
        tool.state()
        routes[("GET", "/soldouts/today")] = ApiError(0, "network: down")
        now[0] += 31
        meta = tool.state()["meta"]
        self.assertTrue(meta["stale"])
        self.assertIn("network: down", meta["error"])

    def test_a_refresh_asks_the_api_again(self):
        tool, feed = self.make([live_row()])
        tool.state()
        tool.state(force=True)
        self.assertEqual(len(feed.client._transport.calls), 2)

    def test_a_task_with_a_live_row_gets_a_status(self):
        tool, _ = self.make([live_row()])
        self.assertIn(tool.state()["rows"][0]["status"], {"worth_a_call", "high_value", "auto_top_up_soon"})


class NoCallDataTest(unittest.TestCase):
    def test_without_call_data_failed_attempts_are_unknown_not_estimated(self):
        advice = Engine(cfgmod.load(), History({})).advise(to_task(live_row()))
        self.assertIn("failed attempts", advice.reason)
        self.assertNotIn("estimated", advice.reason)

    def test_with_call_data_the_proxy_still_says_estimated(self):
        h = History({"activities": [{"activity_id": "A1", "merchant_id": "M10001", "sold_out_id": "SO-9", "activity_date": "2026-11-01",
                                     "type": "call", "owner_id": "R10", "duration_s": "30", "subject": "No answer"}]})
        self.assertIn("failed attempts estimated", Engine(cfgmod.load(), h).advise(to_task(live_row())).reason)


if __name__ == "__main__":
    unittest.main()
