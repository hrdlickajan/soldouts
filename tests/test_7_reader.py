"""Step 7. The result reader: files in, text and JSON out. Offline. A/A check before launch."""
import io
import json
import os
import socket
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from unittest import mock

from advice import config as cfgmod
from advice import demo
from advice.engine import Engine
from advice.groups import group_of
from advice.history import History, load_pack
from advice.result_reader import (compare, fmt_money, main, range_now, real_number_date, task_rows)

PACK = Path(os.environ.get("SOLDOUTS_DATA_PACK", Path(__file__).resolve().parent.parent / "inputs" / "data-pack"))
TABLES = demo.build(seed=3, merchants=150)


class MathTest(unittest.TestCase):
    def rows(self, a, b):
        mk = lambda g, vals: [{"group": g, "cluster": (g, i), "v": v} for i, v in enumerate(vals)]
        return mk("A", a) + mk("B", b)

    def test_difference_and_interval_use_clusters(self):
        # A: 1,0,1,0 (mean .5, variance .0625).  B: 1,1,0,1 (mean .75, variance .046875).
        c = compare(self.rows([1, 0, 1, 0], [1, 1, 0, 1]), lambda r: r["v"])
        self.assertAlmostEqual(c["diff"], 0.25)
        se = (0.0625 + 0.046875) ** 0.5
        self.assertAlmostEqual(c["lo"], 0.25 - 1.96 * se)
        self.assertAlmostEqual(c["hi"], 0.25 + 1.96 * se)
        self.assertEqual((c["n_a"], c["n_b"]), (4, 4))

    def test_tasks_of_one_merchant_week_move_together(self):
        # Two tasks in one cluster count as one draw, so the interval is wider than with two separate clusters.
        same = [{"group": "A", "cluster": "x", "v": 1}, {"group": "A", "cluster": "x", "v": 1},
                {"group": "A", "cluster": "y", "v": 0}, {"group": "A", "cluster": "y", "v": 0},
                {"group": "B", "cluster": "z", "v": 1}, {"group": "B", "cluster": "w", "v": 0}]
        split = [dict(r, cluster=i) for i, r in enumerate(same)]
        v = lambda r: r["v"]
        self.assertGreater(compare(same, v)["hi"] - compare(same, v)["lo"], compare(split, v)["hi"] - compare(split, v)["lo"])

    def test_missing_values_are_skipped_and_empty_group_gives_none(self):
        rows = self.rows([1, None], [1, 1])
        self.assertEqual(compare(rows, lambda r: r["v"])["n_a"], 1)
        self.assertIsNone(compare([r for r in rows if r["group"] == "B"], lambda r: r["v"]))

    def test_real_number_date(self):
        self.assertEqual(real_number_date(date(2027, 1, 8), 8, 30), date(2027, 4, 4))

    def test_range_now_worked_example(self):
        r = range_now(6145, 10, 11, 102.37)
        self.assertAlmostEqual(r["extra_calls_a_year"], 614.5)
        self.assertEqual(r["low_gbp"], 0)
        self.assertAlmostEqual(r["mid_gbp"], 6759.5)
        self.assertAlmostEqual(r["ceiling_gbp"], 614.5 * 102.37)
        self.assertEqual((fmt_money(r["mid_gbp"]), fmt_money(r["ceiling_gbp"])), ("£6.8k", "£62.9k"))


class ReaderOnSyntheticDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = cfgmod.load()
        cls.h = History(TABLES)

    def test_statuses_and_groups_are_rebuilt_from_the_files(self):
        start, end = self.h.window()
        rows = task_rows(self.h, self.cfg, Engine(self.cfg, self.h), start, end)
        self.assertTrue(rows)
        for r in rows[:200]:
            self.assertEqual(r["group"], group_of(r["merchant"], r["date"], self.cfg["share_new_routing"]))
        self.assertEqual({r["touched"] for r in rows if r["status"] in ("high_value", "auto_top_up_soon")}, {True})
        self.assertIn("high_value", {r["status"] for r in rows})
        self.assertIn("auto_top_up_soon", {r["status"] for r in rows})

    def run_reader(self, tables, *extra, cfg=None):
        with tempfile.TemporaryDirectory() as d:
            demo.write_pack(tables, Path(d) / "pack")
            out = Path(d) / "out.json"
            args = [str(Path(d) / "pack"), "--json", str(out), *extra]
            if cfg:
                (Path(d) / "c.json").write_text(json.dumps(cfg))
                args += ["--config", str(Path(d) / "c.json")]
            buf = io.StringIO()
            with redirect_stdout(buf):
                main(args)
            return buf.getvalue(), json.loads(out.read_text())

    def test_prints_the_three_sections_and_a_json_summary(self):
        text, js = self.run_reader(TABLES)
        for part in ("A/A check", "Range now", "Date for the real number", "Launch date: not set"):
            self.assertIn(part, text)
        self.assertIn("mode", js)
        self.assertEqual(js["mode"], "aa_check")
        self.assertIn("metrics", js)
        self.assertIn("range_now", js)
        self.assertIsNone(js["real_number_date"])

    def test_a_launch_date_gives_the_date_and_counts_tasks_from_launch_on(self):
        text, before = self.run_reader(TABLES)
        text2, after = self.run_reader(TABLES, "--launch", "2026-08-01")
        self.assertEqual(after["mode"], "since_launch")
        self.assertLess(after["tasks"], before["tasks"])
        self.assertEqual(after["real_number_date"], "2026-10-26")  # 1 Aug + 8 weeks (26 Sep) + 30 days
        self.assertIn("Result since launch", text2)
        self.assertIn("26 October 2026", text2)

    def test_piped_output_is_utf8_whatever_the_platform_default_is(self):
        import subprocess
        import sys
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
        root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as d:
            demo.write_pack(TABLES, d)
            p = subprocess.run([sys.executable, "-m", "advice.result_reader", d], capture_output=True, cwd=root, env=env)
        self.assertEqual(p.returncode, 0, p.stderr.decode(errors="replace"))
        text = p.stdout.decode("utf-8")  # strict: raises if the pound sign came out in another encoding
        self.assertIn("£", text)

    def test_it_runs_with_the_network_off(self):
        def no_network(*a, **k):
            raise AssertionError("the reader tried to use the network")
        with mock.patch.object(socket, "socket", no_network), mock.patch.object(socket, "create_connection", no_network):
            text, _ = self.run_reader(TABLES)
        self.assertIn("A/A check", text)

    def test_no_effect_planted_means_no_clear_difference_and_a_planted_lift_is_found(self):
        zs_null, zs_planted = [], []
        for seed in (11, 12, 13):
            _, js = self.run_reader(demo.build(seed=seed, merchants=300, effect=0.0))
            zs_null.append(js["metrics"]["fast"]["z"])
            _, js = self.run_reader(demo.build(seed=seed, merchants=300, effect=0.30))
            zs_planted.append(js["metrics"]["fast"]["z"])
        self.assertTrue(all(abs(z) < 3 for z in zs_null), zs_null)
        self.assertTrue(all(z > 3 for z in zs_planted), zs_planted)


@unittest.skipUnless((PACK / "sold_out_deals.csv").exists(), "data pack not present (it is not committed)")
class ReaderOnPackTest(unittest.TestCase):
    """Acceptance checks on the real pack. The numbers are the Key facts in docs/spec.md."""

    @classmethod
    def setUpClass(cls):
        buf = io.StringIO()
        with tempfile.TemporaryDirectory() as d, redirect_stdout(buf):
            main([str(PACK), "--json", str(Path(d) / "o.json")])
            cls.js = json.loads((Path(d) / "o.json").read_text())
        cls.text = buf.getvalue()

    def test_a_a_check_passes_on_the_pack(self):
        self.assertEqual(self.js["mode"], "aa_check")
        self.assertTrue(self.js["aa_pass"], self.text)

    def test_definitions_reproduce_the_key_facts(self):
        j = self.js
        self.assertAlmostEqual(j["tasks"], 30369, delta=5)
        self.assertAlmostEqual(j["logged_share"], 0.390, delta=0.003)
        # The spec's 28.2% is the share at any time. In the pack some calls come 8 and 9 days after the sold-out,
        # so within the 7-day window the share is 27.3%. The reader reports both.
        self.assertAlmostEqual(j["connected_any_share"], 0.282, delta=0.003)
        self.assertAlmostEqual(j["connected_share"], 0.273, delta=0.003)
        self.assertAlmostEqual(j["top_fifth"]["logged_share"], 0.521, delta=0.01)
        self.assertAlmostEqual(j["top_fifth"]["connected_any_share"], 0.420, delta=0.01)
        self.assertAlmostEqual(j["top_fifth"]["connected_share"], 0.408, delta=0.01)
        self.assertAlmostEqual(j["scheduled_share"], 0.191, delta=0.002)

    def test_range_now_and_date_print_as_specified(self):
        r = self.js["range_now"]
        self.assertAlmostEqual(r["top_fifth_tasks_a_year"], 6145, delta=15)
        self.assertAlmostEqual(r["extra_calls_a_year"], 615, delta=3)
        self.assertAlmostEqual(r["ceiling_per_call_gbp"], 102, delta=1.5)
        self.assertIn("£6.8k", self.text)
        self.assertIn("£62.9k", self.text)
        self.assertIn("4 April 2027", self.text)  # example in the text: launch 8 January 2027

    def test_skip_rule_numbers(self):
        s = self.js["skip_rule"]
        self.assertAlmostEqual(s["tasks_a_week"], 40.4, delta=1.5)
        self.assertAlmostEqual(s["logged_calls_a_week"], 8.4, delta=0.8)
        self.assertAlmostEqual(s["minutes_a_week"], 51, delta=5)
        self.assertAlmostEqual(s["gbp_a_week_low"], 14, delta=2)
        self.assertAlmostEqual(s["gbp_a_week_high"], 27, delta=3)


if __name__ == "__main__":
    unittest.main()
