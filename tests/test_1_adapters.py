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

    # The live feed (GET /soldouts/today), as the OpenAPI file in the sandbox describes it (Go 1, 2026-11-11).
    # It has no sold_out_date. It has sold_out_at. It carries the merchant name, band and do-not-contact itself.
    live_row = {"sold_out_id": "SO-1", "restock_task_id": "RT-1", "deal_id": "D10001-1", "deal_name": "60-minute facial",
                "merchant_id": "M10001", "merchant_name": "Bright Skin & Spa", "category": "Health & Beauty",
                "region": "North West", "city": "Manchester", "size_band": "A", "rep_id": "R10", "rep_name": "Rep Ten",
                "do_not_contact": False, "cap": 60, "sold_out_at": "2026-10-25T09:14:00.000Z",
                "team_time": "09:14", "world_day": "d2", "posted_in_channel": True}

    def test_live_feed_row_gives_the_same_record(self):
        live = to_task(self.live_row)  # no merchant lookup needed: the row carries what the engine needs
        self.assertEqual(live, to_task(self.csv_row, MERCHANTS))
        self.assertEqual(live.sold_out_date, date(2026, 10, 25))
        self.assertEqual((live.merchant_name, live.size_band, live.do_not_contact), ("Bright Skin & Spa", "A", False))
        self.assertEqual(live.task_id, "RT-1")  # the task the rep sees
        self.assertEqual((live.callback_promised, live.failed_attempts, live.value_30d_gbp), (None, None, None))

    def test_live_feed_date_is_the_day_on_the_timestamp(self):
        for stamp in ("2026-10-25T00:05:00Z", "2026-10-25T23:59:59.999Z", "2026-10-25T23:30:00+01:00"):
            self.assertEqual(to_task(dict(self.live_row, sold_out_at=stamp)).sold_out_date, date(2026, 10, 25))

    def test_live_feed_do_not_contact_true_is_kept(self):
        self.assertIs(to_task(dict(self.live_row, do_not_contact=True)).do_not_contact, True)

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
