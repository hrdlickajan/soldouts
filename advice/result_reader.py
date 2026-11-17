"""Result reader. Reads CSV files only, needs no network and no key.

    python -m advice.result_reader <folder with the data-pack CSV files> [--config FILE] [--launch YYYY-MM-DD] [--json FILE]

It rebuilds the test group and the status of every sold-out from the files, joins what happened (logged and
connected calls, first-call day, 30-day GP) and compares group B with group A on the tasks where the two
routings differ (status high_value or auto_top_up_soon).

No launch date: it prints an A/A check on history. Nothing was applied, so every difference must sit inside its
interval. With a launch date: it counts tasks from that date on. It also prints a range now (a scenario, not an
estimate) and the date when the real number arrives.
"""
import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from . import config as cfgmod
from .engine import Engine
from .history import History, load_pack


# ---------- rows ----------
def task_rows(h, cfg, engine, start, end):
    """One dict per sold-out in [start, end]: group, status and outcomes."""
    window, seconds = cfg["window_days"], cfg["connected_seconds"]
    rows = []
    for so in h.sold_outs:
        if not start <= so.date <= end:
            continue
        a = engine.advise(h.task_of(so))
        calls = [(d, s) for d, s in h.task_calls.get(so.id, ()) if d is not None]
        in_window = [(d, s) for d, s in calls if 0 <= (d - so.date).days <= window]
        connected = [1 for _, s in in_window if s is not None and s >= seconds]
        connected_any = any(s is not None and s >= seconds for _, s in calls)
        key = (so.merchant, so.deal, so.date)
        year, week, _ = so.date.isocalendar()
        rows.append({
            "id": so.id, "merchant": so.merchant, "deal": so.deal, "date": so.date, "band": a.task.size_band,
            "cluster": (so.merchant, year, week),  # the unit that was randomised
            "group": a.group, "status": a.status, "touched": a.touched, "best_case": a.best_case,
            "scheduled": h.cadence_on(so.deal, so.date) is not None,
            "logged": bool(calls), "connected": bool(connected), "connected_any": connected_any, "n_connected": len(connected),
            "first_call_days": min((d - so.date).days for d, _ in calls) if calls else None,
            "gp": so.gp,
            "refund": any(0 <= (d - so.date).days <= cfg["followup_days"] for d, _ in h.refunds.get((so.merchant, so.deal), ()) if d),
            "realized": h.realized.get(key),
        })
    return rows


# ---------- statistics ----------
def _stats(rows, value):
    clusters = defaultdict(list)
    for r in rows:
        v = value(r)
        if v is not None:
            clusters[r["cluster"]].append(v)
    n = sum(len(v) for v in clusters.values())
    if not n:
        return None
    mean = sum(sum(v) for v in clusters.values()) / n
    var = sum((sum(v) - mean * len(v)) ** 2 for v in clusters.values()) / n ** 2  # variance of the mean, by cluster
    return n, mean, var


def compare(rows, value):
    """B minus A with a 95% interval. Tasks of one merchant-week move together, so the interval uses clusters."""
    a = _stats([r for r in rows if r["group"] == "A"], value)
    b = _stats([r for r in rows if r["group"] == "B"], value)
    if not a or not b:
        return None
    diff, se = b[1] - a[1], math.sqrt(a[2] + b[2])
    return {"n_a": a[0], "n_b": b[0], "mean_a": a[1], "mean_b": b[1], "diff": diff,
            "lo": diff - 1.96 * se, "hi": diff + 1.96 * se, "z": diff / se if se else 0.0}


def range_now(top_tasks_a_year, lift_points, memo_gbp, ceiling_gbp):
    """A scenario, not an estimate. Extra connected calls a year for a lift of L points on the top fifth."""
    extra = top_tasks_a_year * lift_points / 100
    return {"extra_calls_a_year": extra, "low_gbp": 0.0, "mid_gbp": extra * memo_gbp, "ceiling_gbp": extra * ceiling_gbp}


def real_number_date(launch, accrual_weeks, followup_days):
    return launch + timedelta(weeks=accrual_weeks) + timedelta(days=followup_days)


def fmt_money(x):
    return f"£{x / 1000:.1f}k" if abs(x) >= 1000 else f"£{x:,.0f}"


def fmt_date(d):
    return f"{d.day} {d:%B %Y}"


def share(rows, key):
    return sum(1 for r in rows if r[key]) / len(rows) if rows else 0.0


# ---------- report ----------
def metrics(rows, cfg, has_refunds):
    hv = [r for r in rows if r["status"] == "high_value"]
    touched = [r for r in rows if r["touched"]]
    spec = [
        ("fast", f"Connected call within {cfg['window_days']} days, share of high_value tasks (points)", hv, lambda r: 100.0 * r["connected"]),
        ("slow", "30-day GP per touched task (GBP)", touched, lambda r: r["gp"]),
        ("refunds", f"Refund within {cfg['followup_days']} days, share of touched tasks (points)", touched, lambda r: 100.0 * r["refund"]),
        ("calls", "Connected calls per touched task (guard)", touched, lambda r: r["n_connected"]),
    ]
    out = {}
    for key, label, subset, value in spec:
        if key == "refunds" and not has_refunds:
            out[key] = {"label": label, "status": "missing", "why": "no refunds file"}
            continue
        c = compare(subset, value)
        out[key] = dict(label=label, **c) if c else {"label": label, "status": "missing", "why": "no tasks in one group"}
    out["callbacks"] = {"label": "Promised callbacks kept (guard)", "status": "missing",
                        "why": "the data files carry no callback flag"}
    for m in out.values():
        if "diff" in m:
            m["inside"] = m["lo"] <= 0 <= m["hi"]
    return out


def build_summary(h, cfg, folder, launch_override=None):
    engine = Engine(cfg, h)
    start, end = h.window()
    base = task_rows(h, cfg, engine, start, end)
    launch_text = launch_override or cfg.get("launch_date") or ""
    launch = date.fromisoformat(launch_text) if launch_text else None
    scope = [r for r in base if r["date"] >= launch] if launch else base
    days = (end - start).days + 1  # both end dates count
    weeks = days / 7

    cut = cfg["top_fifth_cut_gbp"]
    top = [r for r in base if r["best_case"] is not None and r["best_case"] >= cut]
    realized = [r["realized"] for r in top if r["realized"] is not None]
    ceiling = statistics.mean(realized) if realized else 0.0
    top_a_year = len(top) * 365 / days
    rn = range_now(top_a_year, cfg["lift_points"], cfg["memo_gbp_per_call"], ceiling)
    rn.update(top_fifth_tasks_a_year=top_a_year, ceiling_per_call_gbp=ceiling, memo_per_call_gbp=cfg["memo_gbp_per_call"],
              lift_points=cfg["lift_points"])

    hidden = [r for r in base if r["status"] == "auto_top_up_soon"]
    low_rate, high_rate = cfgmod.pay_rates(cfg)
    per_week = len(hidden) / weeks
    logged = per_week * share(hidden, "logged")
    minutes = logged * cfg["mean_logged_minutes"]
    skip = {"tasks_a_week": per_week, "share_of_all_tasks": len(hidden) / len(base) if base else 0.0,
            "connected_calls_a_week": per_week * share(hidden, "connected"), "logged_calls_a_week": logged,
            "minutes_a_week": minutes, "gbp_a_week_low": minutes / 60 * low_rate, "gbp_a_week_high": minutes / 60 * high_rate}

    m = metrics(scope, cfg, bool(h.refunds))
    firsts = sorted(r["first_call_days"] for r in scope if r["first_call_days"] is not None)
    when = real_number_date(launch, cfg["accrual_weeks"], cfg["followup_days"]) if launch else None
    return {
        "mode": "since_launch" if launch else "aa_check",
        "folder": str(folder), "period": [start.isoformat(), end.isoformat()], "launch_date": launch.isoformat() if launch else None,
        "tasks": len(scope), "tasks_a_week": len(base) / weeks, "share_b": share([dict(r, b=r["group"] == "B") for r in scope], "b"),
        "scheduled_share": share(scope, "scheduled"), "logged_share": share(scope, "logged"), "connected_share": share(scope, "connected"),
        "connected_any_share": share(scope, "connected_any"),
        "first_call_days_median": statistics.median(firsts) if firsts else None,
        "first_call_days_p90": firsts[int(0.9 * len(firsts))] if firsts else None,
        "touched_tasks": sum(1 for r in scope if r["touched"]),
        "top_fifth": {"tasks": len(top), "logged_share": share(top, "logged"), "connected_share": share(top, "connected"),
                      "connected_any_share": share(top, "connected_any")},
        "metrics": m,
        "aa_pass": None if launch else all(v["inside"] for v in m.values() if "inside" in v),
        "range_now": rn, "skip_rule": skip,
        "real_number_date": when.isoformat() if when else None,
    }


def render(s, cfg):
    pct = lambda x: f"{100 * x:.1f}%"
    L = []
    add = L.append
    add("RESULT READER (offline, reads CSV files only)")
    add(f"Folder: {s['folder']}")
    add(f"Period: {s['period'][0]} to {s['period'][1]}")
    add("Launch date: " + (s["launch_date"] if s["launch_date"] else "not set (so this is an A/A check on history)"))
    add("")
    add(f"Tasks: {s['tasks']:,}  ({s['tasks_a_week']:.0f} a week over the period)")
    add(f"Group B share: {pct(s['share_b'])}. On a scheduled deal: {pct(s['scheduled_share'])}.")
    add(f"Logged call: {pct(s['logged_share'])}. Connected call within {cfg['window_days']} days: {pct(s['connected_share'])} ({pct(s['connected_any_share'])} at any time).")
    if s["first_call_days_median"] is not None:
        add(f"First call after a sold-out: median {s['first_call_days_median']:g} days, 90% within {s['first_call_days_p90']} days.")
    t = s["top_fifth"]
    add(f"Top fifth by best case: {t['tasks']:,} tasks, logged {pct(t['logged_share'])}, connected {pct(t['connected_share'])} ({pct(t['connected_any_share'])} at any time).")
    add(f"Touched tasks (high_value or auto_top_up_soon): {s['touched_tasks']:,}")
    add("")
    if s["mode"] == "aa_check":
        add("== A/A check on history ==")
        add("Nothing was applied, so no difference should show. Each B minus A must sit inside its 95% interval.")
    else:
        add("== Result since launch ==")
        add("B minus A on touched tasks, from the launch date on. 95% interval. 'clear' means 0 is outside it.")
    for m in s["metrics"].values():
        if "diff" not in m:
            add(f"- {m['label']}: missing ({m['why']})")
            continue
        flag = ("inside" if m["inside"] else "OUTSIDE") if s["mode"] == "aa_check" else ("no clear difference" if m["inside"] else "clear")
        add(f"- {m['label']}")
        add(f"    A {m['mean_a']:.2f} (n={m['n_a']:,}), B {m['mean_b']:.2f} (n={m['n_b']:,})")
        add(f"    B minus A {m['diff']:+.2f}, interval {m['lo']:+.2f} to {m['hi']:+.2f}: {flag}")
    if s["mode"] == "aa_check":
        add("Verdict: " + ("PASS. Every difference sits inside its interval." if s["aa_pass"] else "CHECK. A difference sits outside its interval. Look before you trust the reader."))
    add("")
    r = s["range_now"]
    add("== Range now (a scenario, not an estimate) ==")
    add(f"Lift of L = {r['lift_points']:g} points in the connected-call share of top-fifth tasks.")
    add(f"Extra connected calls a year = {r['top_fifth_tasks_a_year']:,.0f} top-fifth tasks x L = about {r['extra_calls_a_year']:,.0f}.")
    add("Value of one extra call, and what that gives a year:")
    add(f"  low      {fmt_money(0)}  (the call changes nothing)  ->  {fmt_money(r['low_gbp'])}")
    add(f"  middle   {fmt_money(r['memo_per_call_gbp'])}  (the memo's figure, not validated)  ->  about {fmt_money(r['mid_gbp'])}")
    add(f"  ceiling  {fmt_money(r['ceiling_per_call_gbp'])}  (mean realised best case of the top fifth; a call wins back the whole wait)  ->  about {fmt_money(r['ceiling_gbp'])}")
    k = s["skip_rule"]
    add(f"Skip rule (dial £{cfg['dial_gbp']:g}): {k['tasks_a_week']:.1f} tasks a week hidden ({pct(k['share_of_all_tasks'])} of all tasks).")
    add(f"  Saves about {k['connected_calls_a_week']:.0f} connected calls a week ({k['logged_calls_a_week']:.1f} logged, {k['minutes_a_week']:.0f} minutes),")
    add(f"  worth about £{k['gbp_a_week_low']:.0f} to £{k['gbp_a_week_high']:.0f} a week of rep time at the assumed pay rates. It can only show it does little harm.")
    add("")
    add("== Date for the real number ==")
    add(f"Launch date + {cfg['accrual_weeks']} weeks of tasks + {cfg['followup_days']} days of GP follow-up.")
    if s["real_number_date"]:
        add("The real number arrives on " + fmt_date(date.fromisoformat(s["real_number_date"])) + ".")
    else:
        example = real_number_date(date(2027, 1, 8), cfg["accrual_weeks"], cfg["followup_days"])
        add(f"Example: launch 8 January 2027 gives {fmt_date(example)}.")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="folder with the data-pack CSV files")
    ap.add_argument("--config", help="config file (default: advice/config.json)")
    ap.add_argument("--launch", help="launch date, overrides launch_date in the config")
    ap.add_argument("--json", help="also write a JSON summary to this file")
    args = ap.parse_args(argv)
    cfg = cfgmod.load(args.config)
    if hasattr(sys.stdout, "reconfigure"):
        # UTF-8 when piped or redirected (on Windows the default would be the ANSI code page, which breaks the pound sign).
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    summary = build_summary(History(load_pack(args.folder)), cfg, args.folder, args.launch)
    print(render(summary, cfg))
    if args.json:
        Path(args.json).write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
