"""Parity suite. These tests describe behaviour that must be the same in the original service (2.15.0)
and in this copy (2.16.0) while the switch is off, and the rules that must hold when it is on.

Run on this copy:        python -m unittest discover -s tests
Run on the original:     ROUTING_UNDER_TEST=<path to routing-original> python -m unittest tests.test_parity
(the wiring tests at the bottom are skipped on the original, because the original never reads the file).

Each test runs the service as a subprocess in a temp copy, so it checks the real command output.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
OTHER = os.environ.get("ROUTING_UNDER_TEST")
SERVICE = Path(OTHER).resolve() if OTHER else HERE.parent
INPUT = HERE.parent / "input" / "todays_soldouts.csv"            # hand-made input, used for both services
GOLDEN = (HERE / "golden" / "plan_switch_off.txt").read_bytes()  # output of the ORIGINAL code on that input
ORIGINAL = HERE.parent.parent / "inputs" / "routing-original"    # only present on the author's machine
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}


def nl(b):
    return b.replace(b"\r\n", b"\n")


def run(svc, input_file="input/todays_soldouts.csv", check=True):
    p = subprocess.run([sys.executable, "-m", "routing.plan", input_file], cwd=svc, capture_output=True, env=ENV)
    if check:
        assert p.returncode == 0, p.stderr.decode()
    return p


class Svc:
    """A temp copy of the service under test, with the hand-made input in place."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "svc"
        shutil.copytree(SERVICE, self.dir, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "tests"))
        (self.dir / "input").mkdir(exist_ok=True)
        shutil.copyfile(INPUT, self.dir / "input" / "todays_soldouts.csv")
        return self

    def __exit__(self, *exc):
        self.tmp.cleanup()

    def json(self, rel, **changes):
        p = self.dir / rel
        data = json.loads(p.read_text())
        data.update(changes)
        p.write_text(json.dumps(data))

    def routing(self, **changes):
        self.json("config/routing.json", **changes)

    def overrides(self, **changes):
        self.json("config/env_overrides.json", **changes)

    def suppress(self, *rows, name="input/suppressions.csv"):
        lines = ["deal_id,merchant_id,reason,source,added_on"] + [",".join(r) for r in rows]
        (self.dir / name).write_text("\n".join(lines) + "\n")

    def out(self):
        return nl(run(self.dir).stdout)

    def ids(self):
        return [ln.split()[0] for ln in self.out().decode().splitlines() if ln.startswith("T-")]


def row(deal="", merchant="", reason="auto_top_up_soon", source="auto_replenish"):
    return (deal, merchant, reason, source, "2026-11-01")


class ParityTest(unittest.TestCase):
    """Must pass on the original AND on the copy."""

    def test_switch_off_output_is_identical_to_the_original_output(self):
        with Svc() as s:
            self.assertEqual(s.out(), nl(GOLDEN))

    @unittest.skipUnless((ORIGINAL / "input" / "todays_soldouts.csv").exists(), "original service not present")
    def test_switch_off_is_byte_identical_to_the_live_original_on_its_shipped_input(self):
        real = str(ORIGINAL / "input" / "todays_soldouts.csv")
        with Svc() as s:
            mine = run(s.dir, real).stdout
        theirs = run(ORIGINAL, real).stdout
        self.assertEqual(mine, theirs)

    def test_shipped_defaults(self):
        cfg = json.loads((SERVICE / "config" / "routing.json").read_text())
        self.assertIs(cfg["suppress_soldout_tasks"], False)
        self.assertEqual((SERVICE / "input" / "suppressions.csv").read_text().strip(),
                         "deal_id,merchant_id,reason,source,added_on")

    def test_file_is_ignored_while_the_switch_is_off(self):
        with Svc() as s:
            s.suppress(row("D90016-1"), row("D90001-1"))
            self.assertEqual(s.out(), nl(GOLDEN))

    def test_disputed_deal_list_still_drops_its_deals(self):
        with Svc() as s:
            ids = s.ids()
        self.assertNotIn("T-0010", ids)  # D12006-1
        self.assertNotIn("T-0017", ids)  # D12863-5

    def test_environment_override_beats_routing_config(self):
        with Svc() as s:
            s.overrides(routing={"minutes_per_day": 36})  # routing.json says 210
            self.assertEqual(len(s.ids()), 3)

    def test_priors_come_from_the_override_then_from_priors_json(self):
        with Svc() as s:
            first = s.out().decode().splitlines()[0]
            self.assertTrue(first.endswith(str(round((0.46 - 0.43) * 95.5, 2))), first)  # shipped override
            s.overrides(priors={"restock": {"called": 0.5, "left_alone": 0.4}})
            self.assertTrue(s.out().decode().splitlines()[0].endswith(str(round((0.5 - 0.4) * 95.5, 2))))
            s.json("config/env_overrides.json", priors={})
            self.assertTrue(s.out().decode().splitlines()[0].endswith(str(round((0.62 - 0.41) * 95.5, 2))))

    def test_switch_on_keeps_promised_callbacks(self):
        with Svc() as s:
            s.routing(suppress_soldout_tasks=True)
            s.suppress(row("D90002-1"), row("D90008-1"))  # both have a promised callback
            ids = s.ids()
        self.assertIn("T-0003", ids)
        self.assertIn("T-0009", ids)

    def test_switch_on_keeps_do_not_contact_dropped(self):
        with Svc() as s:
            s.routing(suppress_soldout_tasks=True)
            s.suppress(row("D90006-1"))
            self.assertNotIn("T-0007", s.ids())

    def test_switch_on_ignores_a_merchant_only_row(self):
        with Svc() as s:
            s.routing(suppress_soldout_tasks=True)
            s.suppress(row(merchant="M90001"))  # would drop every deal of the merchant. Must be ignored.
            self.assertEqual(s.out(), nl(GOLDEN))


@unittest.skipIf(OTHER, "wiring tests apply to the new copy only; the original never reads the file")
class WiringTest(unittest.TestCase):
    """Switch on: the routing service drops the deals in the suppression file."""

    def test_switch_on_drops_listed_deals_only(self):
        with Svc() as s:
            s.routing(suppress_soldout_tasks=True)
            s.suppress(row("D90016-1"), row("D90001-2"))
            ids = s.ids()
            self.assertNotEqual(s.out(), nl(GOLDEN))
        self.assertNotIn("T-0018", ids)
        self.assertNotIn("T-0002", ids)
        self.assertIn("T-0001", ids)  # same merchant, other deal: stays

    def test_override_beats_routing_json_in_both_directions(self):
        with Svc() as s:
            s.suppress(row("D90016-1"))
            s.overrides(routing={"suppress_soldout_tasks": True})  # routing.json says false
            self.assertNotIn("T-0018", s.ids())
        with Svc() as s:
            s.routing(suppress_soldout_tasks=True)
            s.suppress(row("D90016-1"))
            s.overrides(routing={"suppress_soldout_tasks": False})
            self.assertEqual(s.out(), nl(GOLDEN))

    def test_only_json_true_turns_the_switch_on(self):
        with Svc() as s:
            s.suppress(row("D90016-1"))
            s.overrides(routing={"suppress_soldout_tasks": "false"})  # a string must not switch it on
            self.assertEqual(s.out(), nl(GOLDEN))

    def test_row_with_both_ids_drops_only_the_deal(self):
        with Svc() as s:
            s.routing(suppress_soldout_tasks=True)
            s.suppress(row("D90001-1", "M90001"))
            ids = s.ids()
        self.assertNotIn("T-0001", ids)
        self.assertIn("T-0002", ids)

    def test_suppressed_tasks_free_up_the_day_for_the_next_ones(self):
        with Svc() as s:
            before = s.ids()
            s.routing(suppress_soldout_tasks=True)
            s.suppress(row("D90016-1"))
            after = s.ids()
        self.assertEqual(len(after), len(before))  # the day was full, so a carried-over task moved up
        self.assertEqual(len(set(after) - set(before)), 1)

    def test_missing_file_means_nothing_is_suppressed(self):
        with Svc() as s:
            s.routing(suppress_soldout_tasks=True, suppression_file="input/does_not_exist.csv")
            self.assertEqual(s.out(), nl(GOLDEN))

    def test_other_file_path_is_used(self):
        with Svc() as s:
            s.suppress(row("D90016-1"), name="input/other.csv")
            s.routing(suppress_soldout_tasks=True, suppression_file="input/other.csv")
            self.assertNotIn("T-0018", s.ids())

    def test_a_bad_file_stops_the_run_and_switching_off_restores_it(self):
        with Svc() as s:
            s.routing(suppress_soldout_tasks=True)
            s.suppress(("", "", "no id", "ops", "2026-11-01"))
            p = run(s.dir, check=False)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("needs a deal_id or a merchant_id", p.stderr.decode())
            s.routing(suppress_soldout_tasks=False)  # rollback = switch off
            self.assertEqual(s.out(), nl(GOLDEN))


if __name__ == "__main__":
    unittest.main()
