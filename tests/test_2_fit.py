"""Step 2. The fit step turns history files into the parameters in config.json."""
import os
import unittest
from datetime import date
from pathlib import Path

from advice import config as cfgmod
from advice.fit import fit
from advice.history import History, load_pack

PACK = Path(os.environ.get("SOLDOUTS_DATA_PACK", Path(__file__).resolve().parent.parent / "inputs" / "data-pack"))

TABLES = {
    "merchants": [
        {"merchant_id": "M1", "merchant_name": "One", "size_band": "A", "rep_id": "R1", "do_not_contact": "0"},
        {"merchant_id": "M2", "merchant_name": "Two", "size_band": "B", "rep_id": "R1", "do_not_contact": "0"},
    ],
    "schedules": [
        {"schedule_id": "S1", "deal_id": "D1-1", "merchant_id": "M1", "start_date": "2025-01-01",
         "end_date": "", "cadence": "weekly", "top_up_qty": "5", "created_by": "ops"},
    ],
    "sold_outs": [
        {"sold_out_id": "SO1", "deal_id": "D1-1", "merchant_id": "M1", "sold_out_date": "2025-06-01",
         "cap": "50", "restocked_date": "2025-06-05", "new_cap": "55", "gp_30d_after_gbp": "130"},
        {"sold_out_id": "SO2", "deal_id": "D1-1", "merchant_id": "M1", "sold_out_date": "2025-06-10",
         "cap": "50", "restocked_date": "2025-06-20", "new_cap": "55", "gp_30d_after_gbp": "200"},
        {"sold_out_id": "SO3", "deal_id": "D2-1", "merchant_id": "M2", "sold_out_date": "2025-06-01",
         "cap": "50", "restocked_date": "", "new_cap": "", "gp_30d_after_gbp": "0"},
        {"sold_out_id": "SO4", "deal_id": "D2-1", "merchant_id": "M2", "sold_out_date": "2025-08-01",
         "cap": "50", "restocked_date": "", "new_cap": "", "gp_30d_after_gbp": ""},
    ],
    "merchant_months": [
        {"merchant_id": "M1", "month": "2025-07", "gp_gbp": "90", "refunds_gbp": "10"},
        {"merchant_id": "M2", "month": "2025-08", "gp_gbp": "93", "refunds_gbp": "7"},
        {"merchant_id": "M1", "month": "2023-12", "gp_gbp": "1", "refunds_gbp": "99"},  # too old
    ],
    "activities": [
        {"activity_id": "A1", "merchant_id": "M1", "sold_out_id": "SO1", "activity_date": "2025-06-02",
         "type": "call", "owner_id": "R1", "duration_s": "360", "subject": "Restock call - no change"},
        {"activity_id": "A2", "merchant_id": "M1", "sold_out_id": "SO1", "activity_date": "2025-06-02",
         "type": "call", "owner_id": "R1", "duration_s": "360", "subject": "Restock call - no change"},  # repeat
        {"activity_id": "A3", "merchant_id": "M1", "sold_out_id": "SO2", "activity_date": "2025-06-11",
         "type": "call", "owner_id": "R1", "duration_s": "240", "subject": "Restock call - cap raised"},
        {"activity_id": "A4", "merchant_id": "M1", "sold_out_id": "SO2", "activity_date": "2025-06-11",
         "type": "note", "owner_id": "R1", "duration_s": "", "subject": "Left voicemail"},
    ],
}


class HistoryTest(unittest.TestCase):
    def setUp(self):
        self.h = History(TABLES)

    def test_schedule_active_on_start_date_and_open_end(self):
        self.assertEqual(self.h.cadence_on("D1-1", date(2025, 1, 1)), "weekly")
        self.assertEqual(self.h.cadence_on("D1-1", date(2030, 1, 1)), "weekly")
        self.assertIsNone(self.h.cadence_on("D1-1", date(2024, 12, 31)))
        self.assertIsNone(self.h.cadence_on("D2-1", date(2025, 6, 1)))

    def test_schedule_end_date_is_inclusive(self):
        t = dict(TABLES, schedules=[dict(TABLES["schedules"][0], end_date="2025-06-05")])
        h = History(t)
        self.assertEqual(h.cadence_on("D1-1", date(2025, 6, 5)), "weekly")
        self.assertIsNone(h.cadence_on("D1-1", date(2025, 6, 6)))

    def test_exact_repeat_activities_are_removed(self):
        self.assertEqual(len(self.h.task_calls["SO1"]), 1)

    def test_leave_one_out_profit_per_day(self):
        # SO1 is 130 / (30 - 4) = 5.0 and SO2 is 200 / (30 - 10) = 10.0
        self.assertAlmostEqual(self.h.merchant_pd("M1", ("M1", "D1-1", date(2025, 6, 1))), 10.0)
        self.assertAlmostEqual(self.h.merchant_pd("M1", ("M1", "D1-1", date(2025, 6, 10))), 5.0)
        self.assertAlmostEqual(self.h.merchant_pd("M1", ("M1", "D9-9", date(2026, 1, 1))), 7.5)
        self.assertIsNone(self.h.merchant_pd("M2", ("M2", "D2-1", date(2025, 6, 1))))


class FitTest(unittest.TestCase):
    def test_fit_on_small_tables(self):
        out = fit(History(TABLES), cfgmod.load())
        self.assertAlmostEqual(out["wait_days"]["weekly"], 7.0)   # lags 4 and 10
        self.assertAlmostEqual(out["wait_days"]["none"], 30.0)    # never restocked counts as 30
        self.assertAlmostEqual(out["profit_per_day"]["A"], 7.5)
        self.assertAlmostEqual(out["refund_share"]["A"], 0.10)
        self.assertAlmostEqual(out["refund_share"]["B"], 0.07)   # the 2023 row is outside 12 months
        self.assertAlmostEqual(out["mean_logged_minutes"], 5.0)  # 360 s and 240 s, repeat removed


@unittest.skipUnless((PACK / "sold_out_deals.csv").exists(), "data pack not present (it is not committed)")
class FitOnPackTest(unittest.TestCase):
    """Must reproduce the Key facts in docs/spec.md, within rounding."""

    @classmethod
    def setUpClass(cls):
        cls.h = History(load_pack(PACK))
        cls.out = fit(cls.h, cfgmod.load())

    def test_waits(self):
        w = self.out["wait_days"]
        for k, v in {"weekly": 4.94, "fortnightly": 8.38, "monthly": 16.12, "none": 22.33}.items():
            self.assertAlmostEqual(w[k], v, delta=0.01, msg=k)

    def test_profit_per_day(self):
        p = self.out["profit_per_day"]
        for k, v in {"A": 5.10, "B": 2.38, "C": 1.26, "D": 0.65}.items():
            self.assertAlmostEqual(p[k], v, delta=0.01, msg=k)

    def test_refund_share(self):
        r = self.out["refund_share"]
        for k, v in {"A": 0.100, "B": 0.070, "C": 0.062, "D": 0.061}.items():
            self.assertAlmostEqual(r[k], v, delta=0.001, msg=k)

    def test_cut_points(self):
        self.assertAlmostEqual(self.out["top_fifth_cut_gbp"], 87.60, delta=0.05)
        self.assertAlmostEqual(self.out["bottom_fifth_cut_gbp"], 13.64, delta=0.05)

    def test_call_length_and_window(self):
        self.assertAlmostEqual(self.out["mean_logged_minutes"], 6.1, delta=0.05)
        start, end = self.h.window()
        self.assertEqual((start, end), (date(2025, 11, 1), date(2026, 10, 27)))
        tasks = [so for so in self.h.sold_outs if start <= so.date <= end]
        self.assertEqual(len(tasks), 30369)
        self.assertEqual(sum(1 for so in tasks if self.h.cadence_on(so.deal, so.date)), 5799)


if __name__ == "__main__":
    unittest.main()
