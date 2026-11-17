# Handoff: build session (Tuesday 17 Nov 2026, Desk time Wed 00:17 when last seen)

For the next agent or the author. Read `README.md` first, then `docs/spec.md`. The older handoff is `inputs/HANDOFF.md` (discuss-first phase).

## State

All ten build steps in `docs/spec.md` are done, with tests first. Two parts are partly done by design: the note reader runs on a stub, and the rep tool is not hosted.

| Suite | How to run | Result |
|---|---|---|
| Root tests (adapters, fit, engine, groups, writer, reader, tool, note reader) | `python -m unittest discover -s tests -t .` | 106 pass with the data pack. 96 pass and 10 skip without it. |
| Routing copy (2.16.0) | `cd routing-service && python -m unittest discover -s tests` | 29 pass (11 original, 10 parity, 8 wiring). |
| Original routing (2.15.0) | `cd inputs/routing-original && python -m unittest discover -s tests` | 11 pass. |
| Parity suite on the original | `cd routing-service && ROUTING_UNDER_TEST=<original folder> python -m unittest tests.test_parity` | 10 pass, 8 wiring tests skip. |

The existing solution was tested first (11 pass), before any change.

Also checked by hand: the rep tool in the built-in browser at 375 px wide (no horizontal scroll, marks round trip, name remembered). That check found and fixed one bug (the `hidden` attribute lost to `display: grid`).

## Against `docs/tasks.md`

| Task | State |
|---|---|
| M1 to M8 (adapters/fit, engine, groups, routing copy, writer, reader, tool, README) | Done. Core tasks M4, M5, M6 are done. |
| M11 change request for Greg, M12 three lines for Dan | Drafted: `docs/change-request.md`, `docs/three-lines.md`. The user sends and submits. |
| M9 (check Desk for replies), M10 (message to Hana), M13 (git identity, first commit, push), M14 (export AI sessions, screenshots, Submit) | Not mine. M10 is not drafted. M13: the user asked for the commit in this session. |
| O3 note reader, O8 test mode, O9 name picker | Built. O3 on a stub only. |
| O1 live feed, O2 marks in the API | Code exists in `advice/api.py` and `advice/tool.py`. Never run: no "go". |
| O4, O5, O6, O7 (hosting), O10, O11 | Not done. O5 and O7 are on the cut list. |

## Not done, and why

- **No API call was made.** The user has not said "go". Waiting on "go": (1) a read-only shape check of `/soldouts/today` (I assumed the row has the history-table fields), (2) a small live run of the note reader (`python -m advice.notes <folder> --merchants M1,M2 --live`), (3) marks through the API (`--api-marks`).
- **Findings are not checked against Renee.** That needs the live run first. The user sends that message.
- **No message was sent to anyone.** Open questions from the earlier session (Priya: connected-call definition and the steps behind £11; Hana: `value_30d_gbp`; Greg: change request, deploy timing, the £6 dial; Renee) have no answers in this repo.
- **Nothing was submitted.** The user presses Submit in the Desk: three lines (`docs/three-lines.md`), repo link, optional zip, AI session exports, screenshots, `docs/change-request.md`.
- **The routing switch was never touched**, in any environment.

## Differences from the spec (data wins)

1. Calls come up to 9 days after a sold-out in the pack, so the connected-call share is 28.2% at any time and 27.3% within 7 days. The reader prints both.
2. Top-fifth cut is £87.62 (fit), not £87.60.
3. "6,145 a year" needs inclusive date counting (361 days). The reader uses it. Tasks a week: 589 (spec 591).

## Git

The repo has no commits. Git author name and email were not set. They must be set before the first commit, and the email shows in a public repo. Rule from the user: commit only new code, specs and handoffs. Do not commit what comes from the Desk: `inputs/` (except `inputs/HANDOFF.md`), the data pack, the original routing service, and Desk documents. `.claude/` (a local preview config) is ignored.

## Where to look

- Engine: `advice/engine.py`. Status table and reason texts at the top.
- Config: `advice/config.json`. Dial £6, share 0.5, fitted numbers. Greg owns the dial.
- Groups: `advice/groups.py`. One function, used by the tool, the writer and the reader.
- Routing change: `routing-service/routing/plan.py` (`suppressed_deals`, `is_active`). Diff against `inputs/routing-original`.
- Result reader: `advice/result_reader.py`. Intervals use merchant-week clusters.
