"""Suppression writer. Reads the routing input file plus history files and writes the suppression file.

    python -m advice.suppress --routing-input routing-service/input/todays_soldouts.csv \
        --data <data folder> --out routing-service/input/suppressions.csv

It lists only deals whose tasks are all group B and `auto_top_up_soon`. Rows are deal-level (a merchant-only row
would drop every deal of that merchant). It never touches the routing switch. The file does nothing until the
switch is on, and nobody switches it on before Greg's written OK.
"""
import argparse
import csv
from collections import defaultdict
from datetime import date

from . import config as cfgmod
from .adapters import load_routing_tasks
from .engine import Engine
from .history import History, load_pack

COLUMNS = ["deal_id", "merchant_id", "reason", "source", "added_on"]
UNAFFECTED = ("callback_promised", "do_not_contact")  # suppression never removes these tasks


def suppression_rows(tasks, engine, added_on):
    advised = defaultdict(list)
    for t in tasks:
        advised[t.deal_id].append(engine.advise(t))
    rows = []
    for deal, items in advised.items():
        affected = [a for a in items if a.status not in UNAFFECTED]
        # A deal-level row drops every task of that deal. Group is set per merchant and week, so list a deal
        # only when every affected task is group B and auto_top_up_soon. Otherwise a group A task would vanish too.
        if affected and all(a.group == "B" and a.status == "auto_top_up_soon" for a in affected):
            rows.append({"deal_id": deal, "merchant_id": "", "reason": "auto_top_up_soon",
                         "source": "auto_replenish", "added_on": added_on})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--routing-input", required=True, help="the routing service's input file (yesterday's sold-outs)")
    ap.add_argument("--data", required=True, help="folder with the data-pack CSV files (schedules, history)")
    ap.add_argument("--out", required=True, help="suppression file to write (it is replaced)")
    ap.add_argument("--config", help="config file (default: advice/config.json)")
    ap.add_argument("--share", type=float, help="override the share on new routing")
    ap.add_argument("--added-on", default=date.today().isoformat(), help="date for the added_on column")
    args = ap.parse_args(argv)

    cfg = cfgmod.load(args.config)
    if args.share is not None:
        cfg["share_new_routing"] = args.share
    history = History(load_pack(args.data))
    tasks = load_routing_tasks(args.routing_input, history.merchants)
    rows = suppression_rows(tasks, Engine(cfg, history), args.added_on)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"{len(tasks)} tasks read, {len(rows)} deal rows written to {args.out}")


if __name__ == "__main__":
    main()
