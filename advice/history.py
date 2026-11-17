"""History tables and the lookups the engine needs. Reads the data-pack CSV shapes."""
from bisect import bisect_left
from collections import defaultdict, namedtuple
from datetime import date, timedelta
from pathlib import Path

from .adapters import Task, flag, norm_rows, read_csv

PACK_FILES = {
    "merchants": "merchants.csv",
    "schedules": "auto_replenish_schedules.csv",
    "sold_outs": "sold_out_deals.csv",
    "activities": "activities.csv",
    "refunds": "refunds.csv",
    "merchant_months": "merchant_months.csv",
    "reps": "reps.csv",
}
SoldOut = namedtuple("SoldOut", "id merchant deal date restocked gp")


def load_pack(folder):
    """Every pack table as a list of rows. A missing optional file gives an empty table."""
    return {name: read_csv(Path(folder) / fn) for name, fn in PACK_FILES.items()}


def _d(v):
    return date.fromisoformat(v[:10]) if v else None


class History:
    def __init__(self, tables):
        t = {k: norm_rows(tables.get(k, [])) for k in PACK_FILES}
        self.merchants = {r["merchant_id"]: r for r in t["merchants"]}
        self.reps = t["reps"]
        self.merchant_months = t["merchant_months"]

        self._sched = defaultdict(list)  # deal -> [(start, end, cadence)]
        for r in t["schedules"]:
            self._sched[r["deal_id"]].append((_d(r["start_date"]), _d(r["end_date"]) or date.max, r["cadence"]))

        self.sold_outs = [
            SoldOut(r["sold_out_id"], r["merchant_id"], r["deal_id"], _d(r["sold_out_date"]),
                    _d(r["restocked_date"]), float(r["gp_30d_after_gbp"]) if r["gp_30d_after_gbp"] else None)
            for r in t["sold_outs"]
        ]
        self.max_date = max((so.date for so in self.sold_outs), default=None)

        # Profit per on-sale day: 30-day GP spread over the days the deal was on sale (restocked rows only).
        self.pd_own, self.realized = {}, {}
        self._pd_sum, self._pd_n = defaultdict(float), defaultdict(int)
        for so in self.sold_outs:
            if so.restocked and so.gp is not None:
                lag = (so.restocked - so.date).days
                if 0 <= lag < 30:
                    v = so.gp / (30 - lag)
                    key = (so.merchant, so.deal, so.date)
                    self.pd_own[key] = v
                    self.realized[key] = v * lag  # what a call could really have won back
                    self._pd_sum[so.merchant] += v
                    self._pd_n[so.merchant] += 1

        # Calls linked to a task, after removing exact repeats that came back with a new id.
        seen = set()
        self.task_calls = defaultdict(list)  # sold_out_id -> [(date, seconds or None)]
        self._calls = defaultdict(list)      # merchant -> sorted [(date, activity_id, subject, seconds)]
        for r in t["activities"]:
            k = tuple(r.get(c, "") for c in
                      ("merchant_id", "sold_out_id", "activity_date", "type", "owner_id", "duration_s", "subject"))
            if k in seen:
                continue
            seen.add(k)
            if r["type"] == "call" and r["sold_out_id"]:
                dur = int(r["duration_s"]) if r["duration_s"] else None
                d = _d(r["activity_date"])
                self.task_calls[r["sold_out_id"]].append((d, dur))
                self._calls[r["merchant_id"]].append((d, r["activity_id"], r["subject"], dur))
        for v in self._calls.values():
            v.sort()
        self._call_dates = {m: [c[0] for c in v] for m, v in self._calls.items()}
        self.has_calls = bool(self._calls)  # False when the call log was not loaded: failed attempts are then unknown

        self.refunds = defaultdict(list)  # (merchant, deal) -> [(date, amount)]
        for r in t["refunds"]:
            self.refunds[(r["merchant_id"], r["deal_id"])].append((_d(r["created_at"]), float(r["amount_gbp"] or 0)))

    # ---- lookups ----
    def band(self, merchant_id):
        return self.merchants.get(merchant_id, {}).get("size_band", "")

    def task_of(self, so):
        m = self.merchants.get(so.merchant, {})
        return Task(so.merchant, so.deal, so.date, m.get("size_band", ""),
                    bool(flag(m.get("do_not_contact", ""))), m.get("merchant_name", ""), task_id=so.id)

    def window(self):
        """Last 12 calendar months, ending on the latest sold-out date."""
        end = self.max_date
        y, m = end.year, end.month - 11
        if m < 1:
            y, m = y - 1, m + 12
        return date(y, m, 1), end

    def cadence_on(self, deal_id, d):
        """Cadence of the schedule active on date d, else None. Start and end dates are inclusive; no end = running."""
        for start, end, cadence in self._sched.get(deal_id, ()):
            if start <= d <= end:
                return cadence
        return None

    def merchant_pd(self, merchant_id, key=None):
        """The merchant's mean profit per on-sale day, leaving out the task itself (key). None if no other rows."""
        s, n = self._pd_sum.get(merchant_id, 0.0), self._pd_n.get(merchant_id, 0)
        own = self.pd_own.get(key)
        if own is not None:
            s, n = s - own, n - 1
        return s / n if n > 0 else None

    def best_case(self, task, fitted):
        """(best case in GBP, source). The most a call could win back before the next top-up."""
        band = task.size_band or self.band(task.merchant_id)
        cadence = self.cadence_on(task.deal_id, task.sold_out_date) or "none"
        pd, source = self.merchant_pd(task.merchant_id, task.key), "merchant"
        if pd is None:
            pd, source = fitted["profit_per_day"].get(band), "band"
        refund = fitted["refund_share"].get(band)
        if pd is None or refund is None:
            return None, "missing"
        return pd * fitted["wait_days"][cadence] * (1 - refund), source

    def failed_attempts_proxy(self, merchant_id, asof, window_days, connected_seconds, no_answer_subject):
        """'No answer' task calls in the window before asof, reset by any connected call. Unvalidated proxy."""
        calls = self._calls.get(merchant_id)
        if not calls:
            return 0
        dates = self._call_dates[merchant_id]
        lo, hi = bisect_left(dates, asof - timedelta(days=window_days)), bisect_left(dates, asof)
        n = 0
        for _, _, subject, seconds in calls[lo:hi]:
            if subject == no_answer_subject:
                n += 1
            elif seconds is not None and seconds >= connected_seconds:
                n = 0
        return n
