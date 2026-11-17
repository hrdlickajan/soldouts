"""Step 9. The note reader. Runs against a stub: no network, no key. The quote check is the safety net."""
import json
import unittest
from datetime import date

from advice import config as cfgmod
from advice.adapters import Task
from advice.engine import Engine
from advice.history import History
from advice.notes import (BudgetStop, NoteReader, SpendGuard, best_finding, items_from_tables, stub_call)

NOTE = "Spoke to the owner. Customers keep saying the booking page is broken, so fix that first. Nice chap."
QUOTE = "Customers keep saying the booking page is broken"


def reply(obj, stop="end_turn", usage=(100, 50)):
    text = obj if isinstance(obj, str) else json.dumps(obj)
    return {"stop_reason": stop, "content": [{"type": "text", "text": text}],
            "usage": {"input_tokens": usage[0], "output_tokens": usage[1]}}


class Scripted:
    """A fake gateway that returns the given responses in order and records every request."""

    def __init__(self, *responses):
        self.responses, self.requests = list(responses), []

    def __call__(self, payload):
        self.requests.append(payload)
        return self.responses.pop(0)


def reader(call, budget=5.0, **kw):
    return NoteReader(call, SpendGuard(budget, 5, 25), sleep=lambda s: None, **kw)


class QuoteCheckTest(unittest.TestCase):
    def test_a_real_quote_is_kept(self):
        f = reader(Scripted(reply({"type": "fix_problem_first", "quote": QUOTE, "confidence": 0.9}))).read(NOTE)
        self.assertEqual((f["type"], f["quote"], f["confidence"]), ("fix_problem_first", QUOTE, 0.9))

    def test_a_made_up_quote_drops_the_finding(self):
        f = reader(Scripted(reply({"type": "fix_problem_first", "quote": "the owner wants to leave us", "confidence": 0.99}))).read(NOTE)
        self.assertEqual(f["type"], "none")
        self.assertEqual(f["quote"], "")
        self.assertIn("quote not in the text", f["dropped"])

    def test_quote_match_ignores_extra_spaces_and_line_breaks_only(self):
        f = reader(Scripted(reply({"type": "fix_problem_first", "quote": "Customers keep   saying\nthe booking page is broken", "confidence": 0.8}))).read(NOTE)
        self.assertEqual(f["type"], "fix_problem_first")
        f = reader(Scripted(reply({"type": "fix_problem_first", "quote": "customers keep saying the booking page is BROKEN", "confidence": 0.8}))).read(NOTE)
        self.assertEqual(f["type"], "none")  # not exact: dropped

    def test_a_finding_without_a_quote_is_dropped_and_none_needs_no_quote(self):
        self.assertEqual(reader(Scripted(reply({"type": "check_capacity_first", "quote": "", "confidence": 1}))).read(NOTE)["type"], "none")
        self.assertEqual(reader(Scripted(reply({"type": "none", "quote": "", "confidence": 0.5}))).read(NOTE)["type"], "none")


class RetryTest(unittest.TestCase):
    good = reply({"type": "fix_problem_first", "quote": QUOTE, "confidence": 0.9})

    def test_one_retry_on_a_bad_response(self):
        for bad in (reply("not json at all"), reply({"type": "banana", "quote": QUOTE}), reply("{", stop="max_tokens"),
                    reply(json.dumps({"type": "fix_problem_first", "quote": QUOTE}), stop="max_tokens")):
            g = Scripted(bad, self.good)
            self.assertEqual(reader(g).read(NOTE)["type"], "fix_problem_first")
            self.assertEqual(len(g.requests), 2)

    def test_two_bad_responses_give_none_and_stop_at_two_calls(self):
        g = Scripted(reply("nope"), reply("still nope"), self.good)
        f = reader(g).read(NOTE)
        self.assertEqual(f["type"], "none")
        self.assertIn("bad response", f["dropped"])
        self.assertEqual(len(g.requests), 2)

    def test_json_in_a_code_fence_is_accepted(self):
        fenced = reply("```json\n" + json.dumps({"type": "fix_problem_first", "quote": QUOTE, "confidence": 0.7}) + "\n```")
        self.assertEqual(reader(Scripted(fenced)).read(NOTE)["type"], "fix_problem_first")


class GatewayRulesTest(unittest.TestCase):
    def test_request_follows_the_gateway_rules(self):
        g = Scripted(reply({"type": "none", "quote": "", "confidence": 0}))
        reader(g).read(NOTE)
        p = g.requests[0]
        self.assertGreaterEqual(p["max_tokens"], 2000)
        self.assertEqual(p["thinking"], {"type": "disabled"})
        self.assertNotIn("tool_choice", p)
        self.assertEqual(p["model"], "claude-haiku-5-5")
        self.assertIn(NOTE, p["messages"][0]["content"])

    def test_rate_stays_under_the_limit(self):
        stamps, now = [], [0.0]
        def sleep(s): now[0] += s
        r = NoteReader(lambda p: (stamps.append(now[0]), reply({"type": "none", "quote": "", "confidence": 0}))[1],
                       SpendGuard(5, 5, 25), sleep=sleep, clock=lambda: now[0], per_second=5)
        for _ in range(12):
            r.read(NOTE)
        stamps = [round(s, 6) for s in stamps]
        for t in stamps:
            self.assertLessEqual(sum(1 for s in stamps if t <= s < t + 1.0), 5)
        self.assertLess(5, 10)  # the gateway limit is 10 a second. We stay well under.

    def test_spend_guard_stops_the_run_at_the_limit(self):
        # 1,000,000 input tokens at $5 per million = $5 on the first call. The budget is $4, so it stops after one call.
        g = Scripted(*[reply({"type": "none", "quote": "", "confidence": 0}, usage=(1_000_000, 0)) for _ in range(5)])
        r = reader(g, budget=4.0)
        out = r.read_all([("M1", "rep note N1", NOTE), ("M2", "rep note N2", NOTE), ("M3", "rep note N3", NOTE)])
        self.assertEqual(len(g.requests), 1)
        self.assertTrue(r.stopped)
        self.assertAlmostEqual(r.guard.spent, 5.0)
        self.assertEqual(out, {})

    def test_a_guard_that_has_tripped_refuses_more_calls(self):
        guard = SpendGuard(1.0, 5, 25)
        guard.add({"input_tokens": 1_000_000, "output_tokens": 0})
        with self.assertRaises(BudgetStop):
            guard.check()

    def test_missing_usage_is_counted_with_a_cautious_estimate(self):
        guard = SpendGuard(5.0, 5, 25)
        guard.add({})
        self.assertGreater(guard.spent, 0)


class ReadAllAndEngineTest(unittest.TestCase):
    def test_read_all_keeps_the_best_finding_per_merchant_and_its_source(self):
        g = Scripted(reply({"type": "check_capacity_first", "quote": "fully booked", "confidence": 0.6}),
                     reply({"type": "fix_problem_first", "quote": QUOTE, "confidence": 0.9}))
        out = reader(g).read_all([("M1", "rep note N1", "We are fully booked until May."), ("M1", "alert reply R9", NOTE)])
        self.assertEqual(out["M1"]["type"], "fix_problem_first")
        self.assertEqual(out["M1"]["source"], "alert reply R9")

    def test_best_finding_ignores_none(self):
        self.assertIsNone(best_finding([{"type": "none", "confidence": 1.0}]))

    def test_stub_runs_offline_and_its_finding_reaches_the_engine(self):
        out = NoteReader(stub_call, SpendGuard(5, 5, 25), sleep=lambda s: None).read_all([("MD", "rep note N1", NOTE)])
        self.assertEqual(out["MD"]["type"], "fix_problem_first")
        self.assertIn(out["MD"]["quote"], NOTE)
        h = History({"merchants": [{"merchant_id": "MD", "size_band": "D", "do_not_contact": "0"}]})
        a = Engine(cfgmod.load(), h).advise(Task("MD", "D1-1", date(2026, 10, 20), "D", callback_promised=False, failed_attempts=0), findings=out)
        self.assertEqual(a.status, "fix_problem_first")
        self.assertEqual(a.quote, out["MD"]["quote"])

    def test_stub_never_invents_a_quote(self):
        for text in ("fully booked until May", "Please call me back on Friday", "not interested, stop calling", "all fine", ""):
            f = NoteReader(stub_call, SpendGuard(5, 5, 25), sleep=lambda s: None).read(text)
            if f["type"] != "none":
                self.assertIn(f["quote"], text)

    def test_items_come_from_rep_notes_then_alert_replies(self):
        t = {"rep_notes": [{"note_id": "N1", "merchant_id": "M1", "text": "a"}],
             "alert_replies": [{"reply_id": "R1", "merchant_id": "M1", "text": "b"}]}
        self.assertEqual(items_from_tables(t, ["M1"]), [("M1", "rep note N1", "a"), ("M1", "alert reply R1", "b")])
        self.assertEqual(items_from_tables(t, ["M2"]), [])


if __name__ == "__main__":
    unittest.main()
