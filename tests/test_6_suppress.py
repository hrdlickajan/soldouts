"""Step 6. The suppression writer: group B, auto_top_up_soon, deal-level rows only."""
import csv
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

from advice import config as cfgmod
from advice.adapters import load_routing_tasks, read_csv
from advice.engine import Engine
from advice.groups import group_of
from advice.history import History
from advice.suppress import COLUMNS, main, suppression_rows

ROUTING_INPUT = Path(__file__).resolve().parent.parent / "routing-service" / "input" / "todays_soldouts.csv"


def sched(deal, end="", cadence="weekly"):
    return {"schedule_id": "S-" + deal, "deal_id": deal, "merchant_id": "M", "start_date": "2026-01-01",
            "end_date": end, "cadence": cadence, "top_up_qty": "5", "created_by": "ops"}


# Hand-made routing input (routing-service/input): weekly schedules on these deals.
#   D90005-1 T-0006 band D  best case ~3.0   -> auto_top_up_soon
#   D90013-1 T-0015 band D  best case ~3.0   -> auto_top_up_soon
#   D90003-1 T-0004 band C  best case ~5.8   -> auto_top_up_soon (just under the £6 dial)
#   D90001-1 T-0001 band A  best case ~22.7  -> worth_a_call (stays)
#   D90002-1 T-0003 band B, callback promised -> callback_promised (never written)
#   D90006-1 T-0007 do not contact            -> do_not_contact (never written)
#   D90007-1 T-0008 failed attempts 3         -> paused (never written)
#   D90020-1 T-0022 band D, schedule ended before the sold-out -> worth_a_call (stays)
SCHEDULES = [sched(d) for d in ("D90005-1", "D90013-1", "D90003-1", "D90001-1", "D90002-1", "D90006-1", "D90007-1")] + \
            [sched("D90020-1", end="2026-10-01")]


def run(share, tasks=None, schedules=SCHEDULES):
    cfg = cfgmod.load(share_new_routing=share)
    tasks = tasks or load_routing_tasks(ROUTING_INPUT)
    return suppression_rows(tasks, Engine(cfg, History({"schedules": schedules})), "2026-11-17")


class WriterTest(unittest.TestCase):
    def test_writes_only_auto_top_up_deals_when_everyone_is_group_b(self):
        rows = run(1.0)
        self.assertEqual(sorted(r["deal_id"] for r in rows), ["D90003-1", "D90005-1", "D90013-1"])

    def test_row_shape_names_a_deal_a_reason_and_a_source(self):
        row = run(1.0)[0]
        self.assertEqual(list(row), COLUMNS)
        self.assertEqual(COLUMNS, ["deal_id", "merchant_id", "reason", "source", "added_on"])
        self.assertEqual((row["reason"], row["source"], row["added_on"]), ("auto_top_up_soon", "auto_replenish", "2026-11-17"))
        self.assertTrue(row["deal_id"])
        self.assertEqual(row["merchant_id"], "")  # never a merchant-wide row

    def test_callback_do_not_contact_and_paused_tasks_are_never_written(self):
        deals = {r["deal_id"] for r in run(1.0)}
        self.assertFalse(deals & {"D90002-1", "D90006-1", "D90007-1"})

    def test_group_a_gets_nothing(self):
        self.assertEqual(run(0), [])

    def test_only_group_b_merchants_are_written(self):
        tasks = load_routing_tasks(ROUTING_INPUT)
        by_deal = {t.deal_id: t for t in tasks}
        for r in run(0.5):
            t = by_deal[r["deal_id"]]
            self.assertEqual(group_of(t.merchant_id, t.sold_out_date, 0.5), "B")

    def test_a_deal_with_a_group_a_task_is_left_out(self):
        # The same deal sold out in two ISO weeks. Find merchants where the weeks land in different groups.
        for m in range(1000):
            mid = f"MX{m}"
            d1, d2 = date(2026, 10, 19), date(2026, 10, 26)
            if (group_of(mid, d1, 0.5), group_of(mid, d2, 0.5)) == ("B", "A"):
                break
        base = dict(task_id="t", merchant_id=mid, deal_id="DX-1", size_band="D", do_not_contact=False,
                    callback_promised=False, failed_attempts=0)
        from advice.adapters import Task
        tasks = [Task(sold_out_date=d1, **{k: v for k, v in base.items()}),
                 Task(sold_out_date=d2, **{k: v for k, v in base.items()})]
        rows = run(0.5, tasks, [sched("DX-1")])
        self.assertEqual(rows, [])  # a deal-level row would also drop the group A task

    def test_one_row_per_deal(self):
        tasks = load_routing_tasks(ROUTING_INPUT)
        tasks = tasks + [t for t in tasks if t.deal_id == "D90005-1"]
        self.assertEqual([r["deal_id"] for r in run(1.0, tasks)].count("D90005-1"), 1)

    def test_command_line_writes_the_file_from_csv_history(self):
        with tempfile.TemporaryDirectory() as d:
            pack = Path(d) / "pack"
            pack.mkdir()
            with open(pack / "auto_replenish_schedules.csv", "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(SCHEDULES[0]))
                w.writeheader()
                w.writerows(SCHEDULES)
            out = Path(d) / "suppressions.csv"
            with redirect_stdout(io.StringIO()) as buf:
                main(["--routing-input", str(ROUTING_INPUT), "--data", str(pack), "--out", str(out),
                      "--added-on", "2026-11-17", "--share", "1.0"])
            rows = read_csv(out)
            self.assertEqual(sorted(r["deal_id"] for r in rows), ["D90003-1", "D90005-1", "D90013-1"])
            self.assertEqual(out.read_text().splitlines()[0], "deal_id,merchant_id,reason,source,added_on")
            self.assertIn("3 deal rows written", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
