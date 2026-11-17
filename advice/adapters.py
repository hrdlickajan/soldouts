"""One adapter layer. CSV history rows, API rows and the routing input file become one Task.

A Task is identified by (merchant, deal, sold-out date). Facts that only some sources carry
(task id, callback flag, failed attempts, routing value) do not take part in equality.
"""
import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


def s(v):
    """Normalise one cell. CSV blank and API null both become ''. Booleans become '1' or '0'."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    return str(v).strip()


def flag(v):
    """True/False from '1', 'true', 1, True. None when blank (unknown)."""
    v = s(v).lower()
    if v == "":
        return None
    return v in ("1", "true", "yes")


def norm_rows(rows):
    """API or CSV rows with every cell as a string, so the rest of the code sees one shape."""
    return [{k: s(v) for k, v in r.items()} for r in rows]


@dataclass(frozen=True)
class Task:
    merchant_id: str
    deal_id: str
    sold_out_date: date
    size_band: str = ""
    do_not_contact: bool = False
    merchant_name: str = ""
    task_id: str = field(default="", compare=False)
    callback_promised: bool = field(default=None, compare=False)
    failed_attempts: int = field(default=None, compare=False)
    value_30d_gbp: float = field(default=None, compare=False)
    # What the live feed adds for the card. None of it takes part in equality.
    deal_name: str = field(default="", compare=False)
    city: str = field(default="", compare=False)
    rep_id: str = field(default="", compare=False)
    team_time: str = field(default="", compare=False)  # the team clock at the sold-out, for example "09:14"

    @property
    def key(self):
        return (self.merchant_id, self.deal_id, self.sold_out_date)


def to_task(row, merchants=None):
    """Build a Task from a history row, an API row or a routing input row.

    `merchants` is an optional {merchant_id: merchants.csv row} lookup. It fills the name, band
    and do-not-contact flag when the row does not carry them. A value on the row wins.
    """
    r = {k: s(v) for k, v in row.items()}
    m = (merchants or {}).get(r["merchant_id"], {})
    pick = lambda name: r.get(name) or s(m.get(name))
    failed = r.get("failed_attempts", "")
    value = r.get("value_30d_gbp", "")
    return Task(
        merchant_id=r["merchant_id"],
        deal_id=r["deal_id"],
        # History and routing rows carry sold_out_date. The live feed carries only sold_out_at (a timestamp).
        sold_out_date=date.fromisoformat((r.get("sold_out_date") or r["sold_out_at"])[:10]),
        size_band=pick("size_band"),
        do_not_contact=bool(flag(pick("do_not_contact"))),
        merchant_name=pick("merchant_name"),
        task_id=r.get("task_id") or r.get("restock_task_id") or r.get("sold_out_id", ""),
        callback_promised=flag(r.get("callback_promised", "")),
        failed_attempts=int(failed) if failed else None,
        value_30d_gbp=float(value) if value else None,
        deal_name=r.get("deal_name", ""),
        city=pick("city"),
        rep_id=pick("rep_id"),
        team_time=r.get("team_time", ""),
    )


def read_csv(path):
    """Rows of one CSV file. A missing file gives no rows."""
    p = Path(path)
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_routing_tasks(path, merchants=None):
    """Tasks from the routing service's input file (yesterday's sold-outs)."""
    return [to_task(r, merchants) for r in read_csv(path)]
