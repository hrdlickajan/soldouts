"""Step 3. The advice engine: ten statuses, rule order, boundaries, schedule edges, £ range."""
import unittest
from datetime import date

from advice import config as cfgmod
from advice.adapters import Task
from advice.engine import REASONS, STATUSES, Engine
from advice.groups import group_of
from advice.history import History

D = date(2026, 10, 20)


def merchants():
    return [
        {"merchant_id": "MA", "merchant_name": "Big", "size_band": "A", "do_not_contact": "0"},
        {"merchant_id": "MD", "merchant_name": "Small", "size_band": "D", "do_not_contact": "0"},
    ]


def sched(deal, start="2026-01-01", end="", cadence="weekly"):
    return {"schedule_id": "S-" + deal, "deal_id": deal, "merchant_id": "MD", "start_date": start,
            "end_date": end, "cadence": cadence, "top_up_qty": "5", "created_by": "ops"}


def history(schedules=(), sold_outs=(), activities=()):
    return History({"merchants": merchants(), "schedules": list(schedules),
                    "sold_outs": list(sold_outs), "activities": list(activities)})


def task(merchant="MD", band="D", deal="D1-1", when=D, **kw):
    return Task(merchant, deal, when, band, **kw)


def engine(h=None, **cfg):
    return Engine(cfgmod.load(**cfg), h or history())


class StatusTest(unittest.TestCase):
    """One test per status. Band D on a weekly schedule has a best case near £3. Band A with no schedule is near £102."""

    def status(self, t, h=None, **kw):
        marks, findings = kw.pop("marks", None), kw.pop("findings", None)
        return engine(h, **kw).advise(t, marks=marks, findings=findings).status

    def test_there_are_ten_statuses_in_three_groups(self):
        self.assertEqual(len(STATUSES), 10)
        self.assertEqual({g for g, _, _ in STATUSES.values()}, {"call", "skip", "other"})

    def test_do_not_contact(self):
        self.assertEqual(self.status(task(do_not_contact=True)), "do_not_contact")

    def test_callback_promised(self):
        self.assertEqual(self.status(task(callback_promised=True)), "callback_promised")

    def test_rep_marked_no_call(self):
        self.assertEqual(self.status(task(), marks={"MD": {"mark": "no_call", "reason": "r"}}), "rep_marked_no_call")

    def test_rep_marked_other(self):
        self.assertEqual(self.status(task(), marks={"MD": {"mark": "wrong_number", "reason": "r"}}), "rep_marked_other")

    def test_paused_failed_attempts(self):
        self.assertEqual(self.status(task(failed_attempts=3)), "paused_failed_attempts")
        self.assertEqual(self.status(task(failed_attempts=2)), "worth_a_call")

    def test_note_findings(self):
        f = lambda kind: {"MD": {"type": kind, "quote": "q", "confidence": 0.9}}
        self.assertEqual(self.status(task(), findings=f("fix_problem_first")), "fix_problem_first")
        self.assertEqual(self.status(task(), findings=f("check_capacity_first")), "check_capacity_first")
        self.assertEqual(self.status(task(), findings=f("merchant_said_no")), "worth_a_call")  # no status for it

    def test_high_value(self):
        self.assertEqual(self.status(task("MA", "A")), "high_value")

    def test_auto_top_up_soon(self):
        self.assertEqual(self.status(task(), history([sched("D1-1")])), "auto_top_up_soon")

    def test_worth_a_call(self):
        self.assertEqual(self.status(task()), "worth_a_call")

    def test_labels_and_groups(self):
        self.assertEqual(STATUSES["high_value"][:2], ("call", "Call first"))
        self.assertEqual(STATUSES["worth_a_call"][:2], ("call", "Normal"))
        self.assertEqual(STATUSES["auto_top_up_soon"][:2], ("skip", "Skip"))
        self.assertEqual(STATUSES["rep_marked_other"][:2], ("other", "Other"))


class OrderTest(unittest.TestCase):
    def test_do_not_contact_beats_a_promised_callback(self):
        a = engine().advise(task(do_not_contact=True, callback_promised=True))
        self.assertEqual(a.status, "do_not_contact")

    def test_callback_beats_a_mark(self):
        a = engine().advise(task(callback_promised=True), marks={"MD": {"mark": "no_call"}})
        self.assertEqual(a.status, "callback_promised")

    def test_mark_beats_failed_attempts_and_other_mark_beats_findings(self):
        a = engine().advise(task(failed_attempts=5), marks={"MD": {"mark": "no_call"}})
        self.assertEqual(a.status, "rep_marked_no_call")
        a = engine().advise(task(), marks={"MD": {"mark": "x"}}, findings={"MD": {"type": "fix_problem_first", "quote": "q"}})
        self.assertEqual(a.status, "rep_marked_other")

    def test_failed_attempts_beat_findings_and_findings_beat_high_value(self):
        f = {"MA": {"type": "check_capacity_first", "quote": "q"}}
        self.assertEqual(engine().advise(task("MA", "A", failed_attempts=3), findings=f).status, "paused_failed_attempts")
        self.assertEqual(engine().advise(task("MA", "A"), findings=f).status, "check_capacity_first")

    def test_high_value_beats_auto_top_up(self):
        h = History({"merchants": merchants(), "schedules": [dict(sched("D9-1"), merchant_id="MA")]})
        t = task("MA", "A", deal="D9-1")  # band A, weekly: best case about £22, so not high value
        self.assertEqual(Engine(cfgmod.load(top_fifth_cut_gbp=10), h).advise(t).status, "high_value")


class BoundaryTest(unittest.TestCase):
    def test_dial_boundary(self):
        h = history([sched("D1-1")])
        best, _ = h.best_case(task(), cfgmod.load()["fitted"])
        self.assertEqual(engine(h, dial_gbp=best).advise(task()).status, "worth_a_call")        # at the dial: not hidden
        self.assertEqual(engine(h, dial_gbp=best + 0.01).advise(task()).status, "auto_top_up_soon")
        self.assertEqual(engine(h, dial_gbp=best - 0.01).advise(task()).status, "worth_a_call")

    def test_cut_point_boundary(self):
        best, _ = history().best_case(task("MA", "A"), cfgmod.load()["fitted"])
        self.assertEqual(engine(top_fifth_cut_gbp=best).advise(task("MA", "A")).status, "high_value")  # at the cut: in
        self.assertEqual(engine(top_fifth_cut_gbp=best + 0.01).advise(task("MA", "A")).status, "worth_a_call")


class ScheduleEdgeTest(unittest.TestCase):
    def test_blank_end_date_means_it_still_runs(self):
        self.assertEqual(engine(history([sched("D1-1", end="")])).advise(task(when=date(2030, 1, 1))).status, "auto_top_up_soon")

    def test_sold_out_on_start_date(self):
        h = history([sched("D1-1", start="2026-10-20")])
        self.assertEqual(engine(h).advise(task(when=date(2026, 10, 20))).status, "auto_top_up_soon")
        self.assertEqual(engine(h).advise(task(when=date(2026, 10, 19))).status, "worth_a_call")

    def test_sold_out_on_end_date(self):
        h = history([sched("D1-1", start="2026-01-01", end="2026-10-20")])
        self.assertEqual(engine(h).advise(task(when=date(2026, 10, 20))).status, "auto_top_up_soon")
        self.assertEqual(engine(h).advise(task(when=date(2026, 10, 21))).status, "worth_a_call")

    def test_no_active_schedule_is_never_auto_top_up_soon(self):
        sold = [{"sold_out_id": "S1", "deal_id": "D0-1", "merchant_id": "MD", "sold_out_date": "2026-01-01",
                 "restocked_date": "2026-01-02", "gp_30d_after_gbp": "0.29"}]  # tiny own profit per day
        h = history(sold_outs=sold)
        a = engine(h).advise(task())
        self.assertLess(a.best_case, 6)
        self.assertEqual(a.status, "worth_a_call")


class AdviceFieldsTest(unittest.TestCase):
    def test_reason_text_is_fixed_per_status(self):
        for status in STATUSES:
            self.assertIn(status, REASONS)
        self.assertEqual(REASONS["worth_a_call"], "Worth a call.")
        self.assertEqual(REASONS["do_not_contact"], "Do not contact this merchant.")
        a = engine().advise(task(callback_promised=False, failed_attempts=0))
        self.assertEqual(a.reason, REASONS["worth_a_call"])

    def test_unknown_callback_is_said_in_the_reason(self):
        a = engine().advise(task(failed_attempts=0))  # callback flag missing
        self.assertEqual(a.reason, REASONS["worth_a_call"] + " Unknown: callback promised.")

    def test_money_range_and_tags(self):
        a = engine().advise(task("MA", "A", callback_promised=False, failed_attempts=0))
        self.assertAlmostEqual(a.best_case, 5.10 * 22.33 * (1 - 0.100), places=6)
        self.assertAlmostEqual(a.gbp_high, a.best_case - 6.1 / 60 * 33000 / 1950, places=6)
        self.assertEqual(a.gbp_low, 0)  # realization 0: a call may change nothing, so the page says "up to"
        self.assertEqual(a.tags["best_case"], "computed")
        self.assertEqual(a.tags["pay_rate"], "assumed")
        self.assertEqual(a.tags["realization"], "assumed")

    def test_range_is_floored_at_zero(self):
        a = engine(dial_gbp=0).advise(task(callback_promised=False, failed_attempts=0), )
        self.assertGreaterEqual(a.gbp_low, 0)
        self.assertGreaterEqual(a.gbp_high, 0)
        a = engine().advise(Task("M?", "D1-1", D, "Z", callback_promised=False, failed_attempts=0))  # unknown band
        self.assertIsNone(a.best_case)
        self.assertEqual(a.tags["best_case"], "missing")
        self.assertEqual(a.status, "worth_a_call")

    def test_group_and_would_be_status(self):
        a = engine().advise(task("MA", "A", callback_promised=False, failed_attempts=0))
        self.assertEqual(a.group, group_of("MA", D, 0.5))
        self.assertEqual(a.would_be_status, "high_value" if a.group == "A" else None)
        self.assertTrue(a.touched)
        b = engine(share_new_routing=1.0).advise(task("MA", "A"))
        self.assertEqual((b.group, b.would_be_status), ("B", None))
        a = engine(share_new_routing=0).advise(task("MA", "A"))
        self.assertEqual((a.group, a.would_be_status), ("A", "high_value"))

    def test_value_30d_gbp_is_not_used(self):
        a = engine().advise(task(value_30d_gbp=1.0, callback_promised=False, failed_attempts=0))
        b = engine().advise(task(value_30d_gbp=900.0, callback_promised=False, failed_attempts=0))
        self.assertEqual((a.status, a.best_case, a.reason), (b.status, b.best_case, b.reason))

    def test_merchant_history_beats_band_mean_and_leaves_the_task_out(self):
        sold = [
            {"sold_out_id": "S1", "deal_id": "D0-1", "merchant_id": "MD", "sold_out_date": "2026-01-01",
             "restocked_date": "2026-01-05", "gp_30d_after_gbp": "130"},   # 5 per day
            {"sold_out_id": "S2", "deal_id": "D0-1", "merchant_id": "MD", "sold_out_date": "2026-02-01",
             "restocked_date": "2026-02-11", "gp_30d_after_gbp": "200"},   # 10 per day
        ]
        h = history(sold_outs=sold)
        own = Task("MD", "D0-1", date(2026, 1, 1), "D")  # S1 itself: only S2 counts, 10 per day
        a = engine(h).advise(own)
        self.assertAlmostEqual(a.best_case, 10 * 22.33 * (1 - 0.061), places=6)
        self.assertEqual(a.best_case_source, "merchant")
        live = engine(h).advise(task())  # a new task: both rows count, 7.5 per day
        self.assertAlmostEqual(live.best_case, 7.5 * 22.33 * (1 - 0.061), places=6)

    def test_failed_attempts_proxy_counts_no_answer_and_resets_on_a_connected_call(self):
        def act(i, day, subject, secs):
            return {"activity_id": f"A{i}", "merchant_id": "MD", "sold_out_id": f"S{i}", "activity_date": day,
                    "type": "call", "owner_id": "R1", "duration_s": str(secs), "subject": subject}
        three = [act(i, f"2026-10-{10 + i:02d}", "No answer", 30) for i in range(3)]
        h = history(activities=three)
        a = engine(h).advise(task(callback_promised=False))   # failed attempts unknown: proxy gives 3
        self.assertEqual(a.status, "paused_failed_attempts")
        self.assertIn("failed attempts estimated", a.reason)
        reset = three[:2] + [act(5, "2026-10-13", "Restock call - no change", 300), act(6, "2026-10-14", "No answer", 30)]
        a = engine(history(activities=reset)).advise(task(callback_promised=False))
        self.assertEqual(a.status, "worth_a_call")
        old = [act(i, f"2026-08-{10 + i:02d}", "No answer", 30) for i in range(3)]   # older than 30 days
        self.assertEqual(engine(history(activities=old)).advise(task(callback_promised=False)).status, "worth_a_call")


if __name__ == "__main__":
    unittest.main()
