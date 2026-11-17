"""Step 1. One sold-out in three shapes must give one equal record."""
import unittest
from datetime import date

from advice.adapters import Task, to_task

MERCHANTS = {"M10001": {"merchant_id": "M10001", "merchant_name": "Bright Skin & Spa",
                        "size_band": "A", "do_not_contact": "0"}}


class AdapterTest(unittest.TestCase):
    csv_row = {"sold_out_id": "SO-1", "deal_id": "D10001-1", "merchant_id": "M10001",
               "sold_out_date": "2026-10-25", "cap": "60", "restocked_date": "",
               "new_cap": "", "gp_30d_after_gbp": ""}
    api_row = {"sold_out_id": "SO-1", "deal_id": "D10001-1", "merchant_id": "M10001",
               "sold_out_date": "2026-10-25", "cap": 60, "restocked_date": None,
               "new_cap": None, "gp_30d_after_gbp": None}
    routing_row = {"task_id": "T-0001", "merchant_id": "M10001", "merchant_name": "Bright Skin & Spa",
                   "deal_id": "D10001-1", "category": "Health & Beauty", "size_band": "A",
                   "sold_out_date": "2026-10-25", "value_30d_gbp": "52.11", "callback_promised": "0",
                   "do_not_contact": "0", "failed_attempts": "0"}

    def test_three_shapes_give_equal_records(self):
        a = to_task(self.csv_row, MERCHANTS)
        b = to_task(self.api_row, MERCHANTS)
        c = to_task(self.routing_row)
        self.assertEqual(a, b)
        self.assertEqual(b, c)
        self.assertEqual(a.sold_out_date, date(2026, 10, 25))
        self.assertEqual(a.size_band, "A")

    def test_blank_and_null_are_equal(self):
        row = dict(self.routing_row, callback_promised="", failed_attempts="", value_30d_gbp="")
        row_null = dict(self.routing_row, callback_promised=None, failed_attempts=None, value_30d_gbp=None)
        a, b = to_task(row), to_task(row_null)
        self.assertEqual((a.callback_promised, a.failed_attempts, a.value_30d_gbp), (None, None, None))
        self.assertEqual((b.callback_promised, b.failed_attempts, b.value_30d_gbp), (None, None, None))

    def test_do_not_contact_zero_and_false_are_equal(self):
        for dnc in ("0", 0, False, "false"):
            self.assertIs(to_task(dict(self.routing_row, do_not_contact=dnc)).do_not_contact, False)
        for dnc in ("1", 1, True, "true"):
            self.assertIs(to_task(dict(self.routing_row, do_not_contact=dnc)).do_not_contact, True)

    def test_routing_row_keeps_what_the_other_shapes_lack(self):
        t = to_task(dict(self.routing_row, callback_promised="1", failed_attempts="2"))
        self.assertIs(t.callback_promised, True)
        self.assertEqual(t.failed_attempts, 2)
        self.assertEqual(t.value_30d_gbp, 52.11)
        self.assertEqual(t.task_id, "T-0001")

    def test_history_row_without_merchant_lookup_still_builds(self):
        t = to_task(self.csv_row)
        self.assertEqual((t.merchant_id, t.deal_id), ("M10001", "D10001-1"))
        self.assertIsInstance(t, Task)


if __name__ == "__main__":
    unittest.main()
