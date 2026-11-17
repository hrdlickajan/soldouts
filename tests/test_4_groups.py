"""Step 4. Group assignment is one pure function, shared by the tool, the writer and the reader."""
import hashlib
import os
import unittest
from datetime import date, timedelta
from pathlib import Path

from advice.groups import group_of

PACK = Path(os.environ.get("SOLDOUTS_DATA_PACK", Path(__file__).resolve().parent.parent / "inputs" / "data-pack"))


class GroupTest(unittest.TestCase):
    def test_matches_the_written_rule(self):
        # SHA-256 of "<merchant>|<ISO year>-W<week>", first 8 hex digits over 2^32, below the share is B.
        h = hashlib.sha256(b"M10001|2026-W43").hexdigest()
        expected = "B" if int(h[:8], 16) / 2 ** 32 < 0.5 else "A"
        self.assertEqual(group_of("M10001", date(2026, 10, 22), 0.5), expected)

    def test_deterministic(self):
        self.assertEqual({group_of("M1", date(2026, 3, 3), 0.5) for _ in range(5)}.__len__(), 1)

    def test_one_merchant_and_week_is_one_group(self):
        monday = date(2026, 10, 19)
        for m in ("M10001", "M10002", "M12345"):
            self.assertEqual(len({group_of(m, monday + timedelta(days=i), 0.5) for i in range(7)}), 1)

    def test_iso_week_edges(self):
        # 2026-01-01 is a Thursday in ISO week 1 of 2026. 2025-12-29 (Monday) is in the same ISO week.
        self.assertEqual(group_of("M1", date(2025, 12, 29), 0.5), group_of("M1", date(2026, 1, 1), 0.5))

    def test_share_zero_is_all_a_and_share_one_is_all_b(self):
        for i in range(200):
            d = date(2026, 1, 1) + timedelta(days=i)
            self.assertEqual(group_of(f"M{i}", d, 0), "A")
            self.assertEqual(group_of(f"M{i}", d, 1.0), "B")

    def test_share_is_about_one_half(self):
        pairs = [(f"M{10000 + m}", date(2026, 1, 5) + timedelta(weeks=w)) for m in range(1500) for w in range(40)]
        b = sum(group_of(m, d, 0.5) == "B" for m, d in pairs) / len(pairs)
        self.assertAlmostEqual(b, 0.5, delta=0.01)

    @unittest.skipUnless((PACK / "sold_out_deals.csv").exists(), "data pack not present (it is not committed)")
    def test_share_on_the_pack_is_half_within_one_point(self):
        from advice.history import History, load_pack
        h = History(load_pack(PACK))
        start, end = h.window()
        rows = [so for so in h.sold_outs if start <= so.date <= end]
        b = sum(group_of(so.merchant, so.date, 0.5) == "B" for so in rows) / len(rows)
        self.assertAlmostEqual(b, 0.5, delta=0.01)


if __name__ == "__main__":
    unittest.main()
