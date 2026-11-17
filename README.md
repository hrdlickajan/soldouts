# Sold-outs: advice, a routing change and a result reader

Reps get one restock task per sold-out (about 600 a week). Reps call on 39% of them. This repo has:

| What | Where | One line |
|---|---|---|
| Advice engine | `advice/engine.py` | For each task: a status (10, in 3 groups), a plain reason, a rough £ range, a test group. |
| Rep tool | `advice/tool.py`, `advice/static/index.html` | A phone page. Lists today's sold-outs. Reps can mark a merchant. |
| Routing change | `routing-service/` | The routing service 2.15.0 plus one change: the existing suppression switch now works. **Off by default.** |
| Suppression writer | `advice/suppress.py` | Writes the suppression file: only group B, only `auto_top_up_soon`, only deal rows. |
| Result reader | `advice/result_reader.py` | Reads CSV files offline. Compares group B with group A. Prints a range now and the date of the real number. |
| Note reader (optional) | `advice/notes.py` | AI reads notes and replies. **Runs on a stub. The real gateway was not called.** |
| Fit step | `advice/fit.py` | Writes the fitted numbers (waits, profit per day, refund shares, cut points) to `advice/config.json`. |

Nothing is switched on. The routing switch stays off until Greg gives written OK in chat.

## How to run it

Python 3.10 or newer. No packages to install. Use `python3` if `python` is not your command.

```bash
python -m advice.tool --demo
```

Open http://127.0.0.1:8080 (add `--host 0.0.0.0` to open it on a phone on the same Wi-Fi). `--demo` uses made-up data, so nothing else is needed. The tool is not hosted. This one command is the hosting plan.

With real files (the data pack is not in this repo, see "What is not in the repo"):

```bash
python -m advice.tool --data <data pack folder> --tasks routing-service/input/todays_soldouts.csv
python -m advice.tool --data <data pack folder> --live     # today's sold-outs from the API. Needs GROUPON_API_KEY and GROUPON_API_BASE. Only after "go".
```

Tool modes (`tool_mode` in `advice/config.json`, or `--mode`):
- `demo` (default): advice on every task, with the test group badge.
- `test`: advice only on group B tasks. Group A tasks show as plain tasks with hard facts only (do-not-contact, promised callback, rep marks). The group is hidden from reps.

The result reader (runs offline, on a folder of CSV files with the data-pack names):

```bash
python -m advice.result_reader <data pack folder> --json result.json
python -m advice.result_reader <data pack folder> --launch 2027-01-08     # counts tasks from the launch date on
```

The suppression file (only has an effect when the routing switch is on):

```bash
python -m advice.suppress --routing-input routing-service/input/todays_soldouts.csv --data <data pack folder> --out suppressions.csv
```

Refresh the fitted numbers from another data folder: `python -m advice.fit <folder> --write`.

## How to run the tests

```bash
python -m unittest discover -s tests -t .                      # advice engine, writer, reader, tool, note reader
cd routing-service && python -m unittest discover -s tests     # routing: the 11 original tests, parity and wiring
```

All tests run offline. No test uses the network or the sandbox key. Tests that need the real data pack read the folder in `SOLDOUTS_DATA_PACK` (default `inputs/data-pack`) and skip when it is missing. Without the pack: 97 tests run and 10 skip. With the pack: 107 run. The routing service has 29 tests.

**Both solutions.** The routing parity suite (`routing-service/tests/test_parity.py`) runs the service as a subprocess, so it can test the original and the new copy:

```bash
cd routing-service
ROUTING_UNDER_TEST=<path to the original 2.15.0 folder> python -m unittest tests.test_parity
```

The original passes its own 11 tests and the parity suite (10 pass; the 8 wiring tests skip, because 2.15.0 never reads the file). The new copy passes all 29. With the switch off, the output is identical to 2.15.0: a golden file made by the 2.15.0 code, and (when the original is present) a byte comparison on the original's own input.

## What I decided, and why

- **One engine, three users.** The tool, the suppression writer and the result reader all call the same engine and the same `group_of()` function. They cannot disagree about a status or a group.
- **Ten statuses, first match wins** (`advice/engine.py`): do-not-contact, promised callback, rep marked no-call, other mark, paused after failed attempts, two note findings, high value, auto top-up soon, worth a call. Each status has one fixed reason text. Tests check the exact text.
- **Best case ranks tasks.** Best case = merchant profit per on-sale day (leave one out, band mean if none) x expected wait without a call (by schedule cadence) x (1 - refund share). It is an upper bound on what a call can win back. In the data it is 23% to 51% above the realised value, so the rule errs toward calling.
- **The £6 dial is a policy dial, not a cost of a call.** Nobody has a cost per call. Greg owns the dial (`dial_gbp`). A scheduled task is hidden only if best case < £6.
- **Test design: 50:50.** Group = SHA-256 of the merchant id, a bar and the ISO week (`2026-W43`). Every deal of one merchant in one week is in one group. We read results only on touched tasks (would-be status `high_value` or `auto_top_up_soon`).
- **Intervals use clusters.** Tasks of one merchant-week share a group, so the result reader's 95% intervals treat the merchant-week as one draw. A plain interval would be too narrow.
- **The suppression writer protects group A.** A deal row drops every task on that deal, but groups are set per merchant and week. The writer lists a deal only if every affected task on it is group B and `auto_top_up_soon`. Otherwise a group A task would vanish too.
- **Routing change is small.** 18 lines added and 2 replaced in `plan.py`. Only JSON `true` turns the switch on. Deal rows only (a merchant-only row would drop every deal of that merchant, so it is ignored). Promised callbacks survive. Do-not-contact stays dropped. The disputed-deal list is separate and unchanged. A missing file suppresses nothing. A malformed row stops the run: that is the loader's existing behaviour, and switching off restores it. Diff: `diff -u inputs/routing-original/routing/plan.py routing-service/routing/plan.py`.
- **`value_30d_gbp` is not used.** In the routing input it is 1.2 to 9 times a merchant's real mean 30-day GP, with no fixed ratio.
- **Money is computed in code, never by AI.** Every figure carries a tag: computed, assumed or missing. The rep sees a range that reads "up to £X", because a call may change nothing.
- **Pay rate is an assumption.** £17 to £32 an hour (`33,000 / 1,950` to `45,000 / 1,700 x 1.2`). The salary range comes from public salary guides, as listed in `docs/spec.md`. The hours and the on-costs are assumptions. It changes only the £ display, never a status.
- **"Called" is configurable.** Logged call: a call activity with the task's sold-out id, after removing exact repeats (526 rows). Connected call: a logged call of 120 seconds or more. The primary metric is a connected call within 7 days. Both are config values.
- **API access is one module** (`advice/api.py`). The key is read only from the environment, never from a file, and never printed. Only rep marks are written (PUT and DELETE on a mark). The routing switch is never touched. No API call has been made.

## Results on the data pack (computed, offline)

`python -m advice.result_reader inputs/data-pack` (period 1 Nov 2025 to 27 Oct 2026, 30,369 tasks):

- **A/A check passes.** Nothing was applied, and all four measured differences sit inside their 95% intervals (for example, share of `high_value` tasks with a connected call: B minus A = -0.2 points, interval -2.8 to +2.4).
- **Range now (a scenario, not an estimate).** If the connected-call share of top-fifth tasks rises by 10 points: about 614 extra connected calls a year. Value of one call: £0 (no effect), £11 (the memo's figure, not validated), £102 (ceiling: a call wins back the whole wait). That gives £0, about £6.8k, and about £62.9k a year. The ceiling is not a forecast.
- **Skip rule at the £6 dial.** About 39 tasks a week are hidden (6.7% of all tasks). Reps log a call on 21% of them. That saves about 4 connected calls a week (8 logged, 51 minutes), worth about £14 to £27 a week of rep time at the assumed pay rates. 8.0% of hidden tasks still had a realised best case of £6 or more (false skips). The test can only show that the skip does little harm.
- **Date for the real number** = launch date + 8 weeks of tasks + 30 days of GP follow-up. Launch on 8 January 2027 gives 4 April 2027. The first 30-day GP read comes about a month after launch.
- On the top fifth, the smallest difference the test can see after 13 weeks at 50:50 is about 7 points of call share and about £9 of 30-day GP (spec, computed earlier).

## What it cannot do yet

- **Live feed gaps.** The live feed of today's sold-outs has no promised-callback flag and no failed-attempts count. The tool shows "Unknown: callback promised" in the reason. It estimates failed attempts from the call log (No answer calls in 30 days, reset by a connected call). That proxy is unvalidated and the reason says so. I assumed the live-feed row has the same fields as the history table. I did not call the API to check.
- **Schedule join.** A schedule is active if start date <= sold-out date <= end date (blank end = running). Merchant Ops has not checked this.
- **Marks** use the sandbox API shape from the docs (`GET /marks` rows with `merchant_id`, `mark`, `reason`, `marked_by`). That shape is assumed. Tests use a fake. Offline, marks go to a local file.
- **Pay rate and the value of a call** are assumptions. The memo's £11 is not validated. Nobody has a cost per call.
- **The result reader's guards.** "Promised callbacks kept" is missing: the files have no callback flag. "Connected calls per rep per week" is measured per touched task instead. "Refund share" uses only the refunds that have a typed reason (about a third).
- **Skip saves little rep time.** No rep-day had more than 17 tasks, so time is not the limit. The `high_value` label is the bigger lever.
- **Note findings are not real yet.** The statuses `fix_problem_first` and `check_capacity_first` work in the engine and tool, but only a stub (keyword rules) feeds them.
- **The result reader trusts `advice/config.json`.** The fitted numbers and cut points come from this data pack. For a different data folder, run `python -m advice.fit <folder> --write` first.

## What I cut

- Hosting beyond a one-command run.
- The real AI gateway run (the note reader is built and tested on a stub; I did not say "go").
- Reviews and refund reasons as note sources.
- List ordering inside routing (release 1 changes task creation only).
- A rep login. A "flag a finding as wrong" button. A check against Marcus.
- Automated cap raises (out of scope).
- Any change to routing priors, list order or input columns.
- Flipping the routing switch, anywhere.

## Where AI is used, and how I checked it

- **Claude Code wrote this code.** I checked it with tests that I read and ran: unit tests on hand-made data, plus tests that reproduce known numbers from the data pack (waits, profit per day, refund shares, cut points, logged and connected call shares, the range now). When a test failed against real data I found the cause before changing anything.
- **In the product.** Only the note reader would use AI. It was **not run** against the real gateway. With `--live` it would send each text to a model and get back a finding type, a quote and a confidence. Code then checks that the quote is in the source text (only extra spaces and line breaks are ignored). If it is not, the finding is dropped. The module also retries once on a bad response, never trusts an answer that stopped for `max_tokens`, stays under 5 requests a second, and stops at a spend limit (USD 5, set in the config). These checks are tested with scripted fake responses.
- **Not yet done:** checking the findings against a rep who knows the merchants (Renee). That needs the live run first.
- AI never does a sum. All £ figures come from code.

## Where the spec and the data differ

Where they differ, the data wins. Three small points:

1. The spec says every logged call falls within 7 days of its sold-out. In the pack, 268 calls come 8 or 9 days after. So the connected-call share is 28.2% at any time (the spec's figure) and 27.3% within 7 days (the primary metric). The reader prints both.
2. The top-fifth cut point from the fit is £87.62, not £87.60. The bottom-fifth cut is £13.64.
3. The "6,145 a year" figure needs inclusive date counting (361 days, both end dates). The reader uses that. Tasks a week then show as 589, not 591. The hidden-tasks figure (39.4 a week) is a little below the spec's 40.4, because do-not-contact and paused tasks keep their own status.

## Agreements

Nobody has agreed to any change. The routing switch needs Greg's written OK in chat. Changes go to the Wednesday change review, then Merchant Ops deploy. The peak change freeze runs until 7 January. See `docs/change-request.md`.

## What is not in the repo

The data pack, the original routing service and the Desk documents are material from the Desk. They are not committed. `inputs/` is read-only and stays local. The routing copy in `routing-service/` uses a hand-made input file, not the Desk's. `advice/demo.py` makes up data for the demo and for tests. No key is stored anywhere: `.gitignore` blocks `.env`, `*.key` and `marks.json`.

## Layout

```
advice/      engine, fit, groups, adapters, history, suppression writer, result reader, tool, api, note reader, config.json
routing-service/   routing 2.15.0 + the switch wired in (2.16.0), its README and tests
tests/       tests by build step (1 adapters, 2 fit, 3 engine, 4 groups, 6 writer, 7 reader, 8 tool, 9 note reader)
docs/        spec.md, change-request.md, three-lines.md, handoff notes
```
