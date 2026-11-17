"""Made-up data for tests and the rep tool demo. Same table shapes as the data pack. Seeded. Not real data.

build()      a synthetic history (merchants, schedules, sold-outs, calls, refunds) for the result reader tests
write_pack() writes those tables as CSV files with the data-pack names
tool_demo()  history, today's tasks and note findings that show all ten statuses in the rep tool
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

from .adapters import load_routing_tasks
from .groups import group_of
from .history import PACK_FILES, History

WAIT = {"weekly": 5, "fortnightly": 9, "monthly": 17, None: 22}
PROFIT_PER_DAY = {"A": 5.1, "B": 2.4, "C": 1.3, "D": 0.65}
CALL_RATE = {"A": 0.55, "B": 0.45, "C": 0.30, "D": 0.20}


def build(seed=1, merchants=200, end=date(2026, 10, 27), days=420, effect=0.0):
    """effect: extra chance of a connected call for group B tasks of band A without a schedule (a planted lift)."""
    rnd = random.Random(seed)
    start = end - timedelta(days=days)
    t = {k: [] for k in PACK_FILES}
    act = 0
    for i in range(merchants):
        mid, band = f"M{20000 + i}", rnd.choices("ABCD", [12, 25, 35, 28])[0]
        t["merchants"].append({"merchant_id": mid, "merchant_name": f"Demo Merchant {i}", "category": "Demo",
                               "region": "North", "city": "Leeds", "size_band": band, "rep_id": f"R{1 + i % 5:02d}",
                               "joined": "2020-01-01", "do_not_contact": "1" if rnd.random() < 0.01 else "0"})
        for k in range(1 + i % 3):
            deal = f"D{20000 + i}-{k + 1}"
            cadence = rnd.choice(["weekly", "fortnightly", "monthly"]) if rnd.random() < 0.3 else None
            if cadence:
                t["schedules"].append({"schedule_id": f"AR-{len(t['schedules'])}", "deal_id": deal, "merchant_id": mid,
                                       "start_date": (start - timedelta(days=30)).isoformat(), "end_date": "",
                                       "cadence": cadence, "top_up_qty": "5", "created_by": "merchant_ops"})
            when = start + timedelta(days=rnd.randint(0, 20))
            while when <= end:
                restocked = rnd.random() > (0.04 if cadence else 0.30)
                lag = max(1, round(rnd.gauss(WAIT[cadence], WAIT[cadence] * 0.3))) if restocked else None
                observed = when <= end - timedelta(days=30)
                gp = ""
                if observed:
                    gp = f"{PROFIT_PER_DAY[band] * (30 - min(lag, 29)) * rnd.uniform(0.6, 1.4):.2f}" if lag else "0"
                so_id = f"SO-{len(t['sold_outs']) + 1:06d}"
                t["sold_outs"].append({"sold_out_id": so_id, "deal_id": deal, "merchant_id": mid,
                                       "sold_out_date": when.isoformat(), "cap": "50",
                                       "restocked_date": (when + timedelta(days=lag)).isoformat() if lag and when + timedelta(days=lag) <= end else "",
                                       "new_cap": "55" if lag else "", "gp_30d_after_gbp": gp})
                p = CALL_RATE[band] * (0.5 if cadence else 1)
                if effect and not cadence and band == "A" and group_of(mid, when, 0.5) == "B":
                    p += effect
                if rnd.random() < p:
                    connected = rnd.random() < 0.7
                    act += 1
                    t["activities"].append({
                        "activity_id": f"A-{act:07d}", "merchant_id": mid, "sold_out_id": so_id,
                        "activity_date": (when + timedelta(days=rnd.randint(0, 6))).isoformat(), "type": "call",
                        "owner_id": f"R{1 + i % 5:02d}", "duration_s": str(rnd.randint(120, 700) if connected else rnd.randint(20, 70)),
                        "subject": "Restock call - no change" if connected else "No answer"})
                if rnd.random() < 0.03:
                    t["refunds"].append({"refund_id": f"RF-{len(t['refunds'])}", "merchant_id": mid, "deal_id": deal,
                                         "created_at": f"{(when + timedelta(days=rnd.randint(1, 20))).isoformat()} 10:00:00",
                                         "amount_gbp": "25.00", "reason_text": "demo"})
                when += timedelta(days=(lag or 30) + rnd.randint(3, 25))
        y, m = end.year, end.month
        for _ in range(14):
            gp = PROFIT_PER_DAY[band] * 30 * rnd.uniform(0.5, 1.5)
            t["merchant_months"].append({"merchant_id": mid, "month": f"{y}-{m:02d}", "gp_gbp": f"{gp:.2f}",
                                         "vouchers_sold": "10", "refunds_gbp": f"{gp * 0.07:.2f}",
                                         "live_deals": "1", "sold_out_events": "1"})
            y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    t["reps"] = [{"rep_id": f"R{n:02d}", "rep_name": f"Demo Rep {n}", "team": "Demo"} for n in range(1, 6)]
    return t


def write_pack(tables, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for name, fn in PACK_FILES.items():
        rows = tables.get(name, [])
        if rows:
            with open(folder / fn, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)


def tool_demo():
    """(history, tasks, findings, marks) built around routing-service/input/todays_soldouts.csv.

    Weekly schedules on a few deals give the auto top-up cases. A stub note reader gives two note findings.
    """
    root = Path(__file__).resolve().parent.parent / "routing-service" / "input" / "todays_soldouts.csv"
    sched = lambda deal, end="": {"schedule_id": "S-" + deal, "deal_id": deal, "merchant_id": "", "start_date": "2026-01-01",
                                  "end_date": end, "cadence": "weekly", "top_up_qty": "5", "created_by": "demo"}
    schedules = [sched(d) for d in ("D90005-1", "D90013-1", "D90003-1", "D90001-1", "D90002-1", "D90007-1")]
    reps = [{"rep_id": f"R{n}", "rep_name": f"Demo Rep {n}", "team": "Demo"} for n in (10, 11, 12)]
    history = History({"schedules": schedules, "reps": reps})
    tasks = load_routing_tasks(root)
    findings = {
        "M90010": {"type": "fix_problem_first", "confidence": 0.9, "source": "demo stub",
                   "quote": "customers keep saying the booking page is broken"},
        "M90021": {"type": "check_capacity_first", "confidence": 0.8, "source": "demo stub",
                   "quote": "we only have two rooms and they are fully booked until December"},
    }
    marks = {"M90011": {"mark": "no_call", "reason": "Owner asked for a quiet month", "marked_by": "R10"},
             "M90019": {"mark": "wrong_number", "reason": "Phone goes to a plumber", "marked_by": "R10"}}
    return history, tasks, findings, marks
