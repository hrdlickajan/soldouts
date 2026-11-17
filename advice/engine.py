"""The advice engine. For one sold-out task: a status, a plain reason, a rough GBP range and a test group.

The AI never does sums. Every figure carries a tag: computed, assumed or missing.
"""
from dataclasses import dataclass

from .adapters import Task
from .config import pay_rates
from .groups import group_of

# status -> (group, label, plain reason). Rule order is the order of this table. First match wins.
STATUSES = {
    "do_not_contact": ("skip", "Skip", "Do not contact this merchant."),
    "callback_promised": ("call", "Call first", "A callback was promised. Call first."),
    "rep_marked_no_call": ("skip", "Skip", "A rep marked this merchant: no call."),
    "rep_marked_other": ("other", "Other", "A rep marked this merchant. Read the mark before you call."),
    "paused_failed_attempts": ("skip", "Skip", "Paused: too many failed call attempts."),
    "fix_problem_first": ("other", "Other", "Notes show a problem to fix first."),
    "check_capacity_first": ("other", "Other", "Notes say to check capacity first."),
    "high_value": ("call", "Call first", "High value: the best case is in the top fifth."),
    "auto_top_up_soon": ("skip", "Skip", "An automatic top-up is active and the best case is small. The deal should restock soon."),
    "worth_a_call": ("call", "Call later", "Worth a call."),
}
REASONS = {k: v[2] for k, v in STATUSES.items()}
TOUCHED = ("high_value", "auto_top_up_soon")  # the new routing changes how these are handled


@dataclass(frozen=True)
class Advice:
    task: Task
    status: str
    kind: str            # call, skip or other
    label: str           # Call first, Call later, Skip or Other
    reason: str
    best_case: float     # GBP, None when missing
    best_case_source: str
    gbp_low: float       # rough range for the rep, None when best case is missing
    gbp_high: float
    tags: dict           # computed, assumed or missing, for every figure
    group: str           # test group: A keeps today's routing, B gets the new routing
    quote: str = ""      # supporting quote from the note reader, if any
    mark: dict = None    # the rep's mark on the merchant, if any

    @property
    def would_be_status(self):
        """For group A: the status the new routing would give. None for group B (the status is applied)."""
        return self.status if self.group == "A" else None

    @property
    def touched(self):
        return self.status in TOUCHED


class Engine:
    def __init__(self, cfg, history):
        self.cfg, self.h = cfg, history

    def money(self, best):
        """(low, high) GBP. High: best case minus the low rep-time cost. Low: best case x low realization minus the high cost."""
        if best is None:
            return None, None
        low_rate, high_rate = pay_rates(self.cfg)
        hours = self.cfg["mean_logged_minutes"] / 60
        return (max(0.0, best * self.cfg["realization_low"] - hours * high_rate),
                max(0.0, best - hours * low_rate))

    def advise(self, task, marks=None, findings=None):
        """marks: {merchant_id: {"mark", "reason", "marked_by"}}. findings: {merchant_id: {"type", "quote", ...}}."""
        cfg, h = self.cfg, self.h
        mark = (marks or {}).get(task.merchant_id)
        finding = (findings or {}).get(task.merchant_id) or {}
        ftype = finding.get("type", "none")
        best, source = h.best_case(task, cfg["fitted"])
        cadence = h.cadence_on(task.deal_id, task.sold_out_date)
        unknown = []

        if task.do_not_contact:
            status = "do_not_contact"
        else:
            callback = task.callback_promised
            if callback is None:
                callback = ftype == "callback_promised"
                if not callback:
                    unknown.append("callback promised")
            fails = task.failed_attempts
            if fails is None and not callback and not mark:
                if h.has_calls:
                    fails = h.failed_attempts_proxy(task.merchant_id, task.sold_out_date,
                                                    cfg["failed_attempts_proxy_window_days"], cfg["connected_seconds"],
                                                    cfg["no_answer_subject"])
                    unknown.append("failed attempts estimated")
                else:  # no call log loaded: do not pretend to estimate
                    fails = 0
                    unknown.append("failed attempts")
            if callback:
                status = "callback_promised"
            elif mark:
                status = "rep_marked_no_call" if mark.get("mark") == "no_call" else "rep_marked_other"
            elif fails >= cfg["failed_attempts_limit"]:
                status = "paused_failed_attempts"
            elif ftype in ("fix_problem_first", "check_capacity_first"):
                status = ftype
            elif best is not None and best >= cfg["top_fifth_cut_gbp"]:
                status = "high_value"
            elif best is not None and cadence and best < cfg["dial_gbp"]:
                status = "auto_top_up_soon"
            else:
                status = "worth_a_call"
                if best is None:
                    unknown.append("best case missing")

        kind, label, reason = STATUSES[status]
        if unknown:
            reason += " Unknown: " + "; ".join(unknown) + "."
        low, high = self.money(best)
        return Advice(
            task=task, status=status, kind=kind, label=label, reason=reason,
            best_case=best, best_case_source=source, gbp_low=low, gbp_high=high,
            tags={"best_case": "computed" if best is not None else "missing",
                  "pay_rate": "assumed", "realization": "assumed"},
            group=group_of(task.merchant_id, task.sold_out_date, cfg["share_new_routing"]),
            quote=finding.get("quote", "") if ftype != "none" else "", mark=mark,
        )
