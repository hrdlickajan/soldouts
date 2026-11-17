"""Fit step: compute the fitted parameters from the history files and write them to config.json.

    python -m advice.fit <data folder>            # print
    python -m advice.fit <data folder> --write    # also update advice/config.json
"""
import argparse
import json
import statistics
from collections import defaultdict
from datetime import timedelta

from . import config as cfgmod
from .history import History, load_pack


def quantile(xs, q):
    """Linear interpolation between order statistics (the 'inclusive' method)."""
    xs = sorted(xs)
    pos = q * (len(xs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def fit(h, cfg):
    """Return the fitted parameters. Anything the data cannot give keeps the value already in cfg."""
    # Wait without a call: mean days from sold-out to restock, capped at 30, never restocked = 30.
    # Only sold-outs whose 30 days are fully observed.
    cutoff = h.max_date - timedelta(days=30)
    waits = defaultdict(list)
    for so in h.sold_outs:
        if so.date <= cutoff:
            lag = min((so.restocked - so.date).days, 30) if so.restocked else 30
            waits[h.cadence_on(so.deal, so.date) or "none"].append(lag)

    by_band = defaultdict(list)
    for (merchant, _, _), v in h.pd_own.items():
        by_band[h.band(merchant)].append(v)

    # Refund share of GP (upper bound): refunds / (gp + refunds) over the last 12 months of merchant_months.
    months = [r["month"] for r in h.merchant_months]
    refunds = defaultdict(lambda: [0.0, 0.0])
    if months:
        last = max(months)
        first = f"{int(last[:4]) - (1 if int(last[5:7]) < 12 else 0)}-{(int(last[5:7]) % 12) + 1:02d}"
        for r in h.merchant_months:
            if r["month"] >= first:
                b = h.band(r["merchant_id"])
                refunds[b][0] += float(r["refunds_gbp"] or 0)
                refunds[b][1] += float(r["gp_gbp"] or 0)

    out = {
        "wait_days": {k: statistics.mean(v) for k, v in waits.items()},
        "profit_per_day": {b: statistics.mean(v) for b, v in by_band.items() if b},
        "refund_share": {b: r / (r + g) for b, (r, g) in refunds.items() if b and (r + g) > 0},
    }
    minutes = [dur / 60 for calls in h.task_calls.values() for _, dur in calls if dur is not None]
    out["mean_logged_minutes"] = statistics.mean(minutes) if minutes else cfg["mean_logged_minutes"]

    # Cut points: 80th and 20th percentile of best case over the last 12 months of tasks.
    params = {k: {**cfg["fitted"][k], **out[k]} for k in ("wait_days", "profit_per_day", "refund_share")}
    start, end = h.window()
    cases = [c for so in h.sold_outs if start <= so.date <= end
             for c, _ in [h.best_case(h.task_of(so), params)] if c is not None]
    if cases:
        out["top_fifth_cut_gbp"] = quantile(cases, 0.8)
        out["bottom_fifth_cut_gbp"] = quantile(cases, 0.2)
    return out


def write_config(out, path=None):
    path = path or cfgmod.DEFAULT_PATH
    cfg = json.loads(path.read_text(encoding="utf-8"))
    digits = {"wait_days": 2, "profit_per_day": 2, "refund_share": 3}
    for k, nd in digits.items():
        cfg["fitted"][k].update({b: round(v, nd) for b, v in out[k].items()})
    for k in ("top_fifth_cut_gbp", "bottom_fifth_cut_gbp"):
        if k in out:
            cfg[k] = round(out[k], 2)
    cfg["mean_logged_minutes"] = round(out["mean_logged_minutes"], 1)
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data", help="folder with the data-pack CSV files")
    ap.add_argument("--config", help="config file to read (default: advice/config.json)")
    ap.add_argument("--write", action="store_true", help="write the fitted values into advice/config.json")
    args = ap.parse_args(argv)
    out = fit(History(load_pack(args.data)), cfgmod.load(args.config))
    print(json.dumps(out, indent=2))
    if args.write:
        write_config(out)
        print("written to", cfgmod.DEFAULT_PATH)


if __name__ == "__main__":
    main()
