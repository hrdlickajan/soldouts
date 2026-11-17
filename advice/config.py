"""The one config file. Every number the engine uses lives in config.json."""
import json
from pathlib import Path

DEFAULT_PATH = Path(__file__).with_name("config.json")


def load(path=None, **overrides):
    cfg = json.loads(Path(path or DEFAULT_PATH).read_text(encoding="utf-8"))
    cfg.update(overrides)
    return cfg


def pay_rates(cfg):
    """(low, high) pay in GBP per hour. Assumed, see README. Never changes a status."""
    p = cfg["pay"]
    low = p["salary_gbp"][0] / p["hours_a_year"][0]
    high = p["salary_gbp"][1] / p["hours_a_year"][1] * (1 + p["on_cost_high"])
    return low, high
