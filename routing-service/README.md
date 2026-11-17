# routing

Builds each rep's morning task list from yesterday's sold-outs. Owned by Merchant Ops (Hana day to day). Runs overnight; lists are ready by about 07:00.

```
python3 -m routing.plan input/todays_soldouts.csv
python3 -m unittest discover -s tests     # or: python3 -m pytest
```

## What it does

1. Takes the sold-outs for one rep (`input/todays_soldouts.csv` is yesterday's file for one rep).
2. Creates one restock task per sold-out. It works from that file only. It has no view of anything else that may be happening to the deal.
3. Drops do-not-contact merchants and anything in `suppressed_deal_ids`. Pauses merchants after too many failed attempts.
4. Promised callbacks go first, whatever they are worth. Someone told the merchant we would ring.
5. The rest are ranked by expected GP: `(called - left_alone) x value_30d_gbp`, using the restock priors.
6. Fills the rep's day. Whatever doesn't fit carries over to tomorrow and shows as overdue.

## Config

| File | What's in it |
|---|---|
| `config/routing.json` | Minutes per day, minutes per task, pause threshold, `suppressed_deal_ids`, `suppress_soldout_tasks`, `suppression_file` |
| `priors.json` | Restock priors used for ranking; also the priors for other task types |
| `config/env_overrides.json` | Environment values. Loaded last, on top of the above, and takes precedence (`priors` over `priors.json`, `routing` over `config/routing.json`) |
| `input/suppressions.csv` | Sold-out suppression list: `deal_id`, `merchant_id`, `reason`, `source`, `added_on`. Ships empty |

Notes for anyone changing things:

- All values are read at start of run. There is no hot reload.
- `suppressed_deal_ids` is a plain list of deal ids. A suppressed deal gets no task. Ops use it for deals in dispute or under a manual arrangement.
- Value per task comes from the input file; routing does not compute it.
- The input file's column order matters to the importer, so add columns at the end.

## Sold-out suppression (wired in 2.16.0, off by default)

Agreed in October so reps stop getting tasks that don't need them.

- `suppress_soldout_tasks` in `config/routing.json`. Default `false`. This is the one switch. Only JSON `true` turns it on. `env_overrides.json` wins over `routing.json`.
- `input/suppressions.csv`, read by `routing/suppressions.py`. Ships empty.
- **Switch off:** the file is not read. Output is identical to 2.15.0 (tests: `tests/test_parity.py`, golden file made by the 2.15.0 code).
- **Switch on:** `plan.py` drops every task whose `deal_id` is in the file.
  - Only deal rows count. A row with only a `merchant_id` is ignored, because it would drop every deal of that merchant.
  - A promised callback is never dropped. Do-not-contact is still dropped.
  - `suppressed_deal_ids` (disputes) is separate and unchanged.
  - A missing file suppresses nothing. A malformed row stops the run. Rolling back means switching it off, or emptying the file.
- The advice engine in `../advice` writes the file (`python -m advice.suppress`). Only auto-top-up tasks of test group B are listed.

Nobody switches it on before Greg's written OK in chat. Release 1 changes task creation only. List order, priors and input columns stay as today.

## Tests

```
python -m unittest discover -s tests                            # this copy: 11 original tests + parity + wiring
ROUTING_UNDER_TEST=<path to 2.15.0> python -m unittest tests.test_parity   # the same parity suite on the original
```

## Ops

- Changes go to Wednesday change review, then Merchant Ops deploys. Config changes count as changes.
- Peak change freeze: nothing touches routing or its config until 7 January.
- Version: 2.16.0. 2.15.0 added the suppression switch and file, unused. 2.16.0 wires them into `plan.py`, behind the switch (off).
