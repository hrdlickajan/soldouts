# Handoff: Groupon UK "Sold-outs" builder exercise

Written 2026-11-16 (Desk clock was Tuesday 10:07 at last look). For the next agent. Read this first, then `C:\Projects\soldouts\inputs\README.md`.

## 1. What the user wants from you

The user is a candidate in a simulated work week (Desk app). Dan Okafor (VP Sales) asked for, by **Thursday 09:00 Desk time**: a phone-usable rep tool, a routing change that Greg will switch on, and a number Dan can defend. The user is in a **discuss-first phase**. They want to understand the problem fully before anything is built.

How to work with them (they asked for all of this):
- Run the `grilling:grilling` interview. Ask a numbered round of questions. Give a recommended answer for each, so "yes" accepts it. Wait for answers. Do not ask a question whose answer depends on an open one.
- After every round, give a **short summary of the problem** and collect all facts, so you reach a shared understanding.
- Talk to the user in **ASD-STE100 non-strict (80%) English**: short sentences, active voice, no jargon, no semicolons. For the hardest topics they asked for "very simple terms". They also used `/bro` once to get a plain re-explanation.
- The user sometimes answers with a question ("explain this") or defers ("keep discussing"). Treat that as "not decided". Do not assume yes.

## 2. Hard rules the user set (do not break)

- **Build nothing yet.** "Do not build yet, keep discussing." Python is the agreed language "for now". Technical details come later.
- **No sandbox API calls** until the user says "go". Do not read or use the sandbox key. Never commit it.
- **Messages to characters** (Dan, Greg, Hana, Priya, Renee, Marcus): the user sends them, unless they clearly tell you to send. They did tell you to send the Priya message (done). For the others, draft only. They said: "wait until I understand the issue properly". Every agreement you mention must be one the user really made in the Desk.
- **Never flip the routing switch**, even in the sandbox. Greg's written OK in chat comes first (Hana's rule). The hiring team reads the logs.
- Git: repo exists, **no commits, no git author name or email set**. Ask the user before the first commit. The email would show in a public repo. Call `propose_branch` right before the first file edit in the repo. Do not commit unless asked. Commit messages need the attribution line from the system reminder.
- No employer material in the repo (rules of the exercise). The Desk URL has a secret token in its path, and the user's key is under "Your API key" in the Desk. Neither is written here. The Desk is open in the built-in browser pane (tab id `seed`). If the pane is closed, ask the user for the link.
- Do not quote the old scratch-folder path to the user. Call it "a folder the app made for this session".
- **Never invent numbers.** The user corrected this once. Every number must come from the attached data, with source and method. Label each as computed, assumed, or missing. If a number is not in the data, say so in the handoff and ask the owner. I made up a £6 call cost and a 30-day wait. Both are withdrawn (section 6).

## 3. State of the work

Done:
- Read all 8 Desk docs, 3 channels and relevant threads. Downloaded both zips. Created `C:\Projects\soldouts` (git init, branch `main`, no commit).
- Repo layout (see `inputs/README.md` for sources, owners and known data issues):
  - `inputs/archives/` original zips
  - `inputs/data-pack/` 11 CSV files, unchanged
  - `inputs/routing-original/` routing service v2.15.0, unchanged. Its `README.md` and code are the reference. Our diff must show against it.
  - `.gitignore` (keys, caches)
- **Message sent to Priya** in the Desk at 10:07 (6 questions: cost of a call, selection by merchant size, schedules ignored in the memo, later refunds, marginal calls, CRM duplicates). **Check for her reply first.** Her welcome message at 09:40 offered a walkthrough at **11:30 or 15:00** today. The user has not chosen. Ask them.
- Exploration scripts (read-only, local files, throwaway): `<scratch folder>\exploration\`. Run with `python -I <script> <data-pack dir>`. `logic.py` takes a second arg: `inputs\routing-original\input`. They call `sys.stdout.reconfigure(encoding="utf-8")` because the Windows console is cp1252.

Not done: any code, tests, tool, README, change request, three lines, holdout script, AI note reader, hosting, commit.

## 4. Brief digest (the Desk docs are not saved as files)

Ask the user if they want them saved as Markdown under `docs/` in the repo.

- **Deliverables** (Dan's ask): rep tool behind a link (phone, today's sold-outs: call / don't bother / something else, why, rough £, reps can mark a merchant with a reason); AI over free text (rep notes, merchant replies, reviews, refund reasons) with the supporting quote, checked against a rep who knows the merchants; money in code, not AI (GP from a cap raise minus rep time minus refund risk); routing change in `routing.zip` (off by default, one switch, rollback, tests); holdout plus a script that reads out the real number, with a range now and a date for the real one; repo with history, tests, README (how to run, decisions, limits, cut list); exported AI sessions; three lines for Dan and a one-page change request for Greg (risk, rollback, when to stop). Dan prefers deliberate cuts over eight things done badly. Put the cut list in the README and in the three lines.
- **Hand-in:** the Desk Submit button. Only the three lines are compulsory. Tool link, repo link (keep history, no squash), zip up to 50 MB, AI session exports, screenshots, change request text (it is not sent to Greg unless the user sends it). The facilitator may run tests and the detector **offline** on unseen data. Keep the detector runnable from a file. Do not rely on the sandbox key for tests.
- **Time:** about 3 hours of work in total, 48 hours elapsed from first opening the Desk. Change review is **Wednesday 15:00**. Peak freeze runs **from next Monday to 7 January**. A last check on Friday covers changes already discussed with Greg.
- **People** (all AI characters): Dan (VP Sales, owns the brief, takes the three lines); Greg Lindqvist (Head of Merchant Ops: caps, automations, routing, sandbox, written OK, "likes things with an off switch"; said no automated cap raises before January); Hana Kowalczyk (engineer, Merchant Ops: routing service day to day, sandbox API, notes export, reviews the diff first, flips the switch only after Greg's written OK); Priya Nair (sales analyst: memo, data pack); Renee Walsh (senior AM, H&B North, rep R10: can say what notes mean and check AI output); Marcus Bell (AM, F&D London, R12).
- **Sandbox API** (not used): base path `/api/sandbox/v1`, read endpoints for each CSV plus `/soldouts/today`, marks (PUT/DELETE `/merchants/{id}/mark`), routing switch (GET/PUT `/routing/switch`), LLM gateway (Anthropic Messages passthrough, USD 20 budget, models claude-haiku-5-5 / sonnet-5-5 / opus-5-5). Gotchas: 5.5 models think by default, so use `max_tokens` 2000 or more, or `thinking: {"type":"disabled"}`; forced `tool_choice` returns 400; check `stop_reason`; 10 requests a second.
- **Routing today:** one task per sold-out. It ignores schedules and Deal Alert state. A task closes when the rep logs an outcome. The day holds 210 minutes at 12 minutes per task (17 tasks).

## 5. Findings so far (all from the local data pack; caveats matter)

Priya's memo ("£11 GP per call", `Restock calls` doc in the Desk):
- Arithmetic is right: weighted gap £11.08; £11 × 600 × 52 ≈ £343k. The logic is weak: observational, only band-adjusted, ignores schedules, 30-day GP excludes later refunds.
- Her own table shows reps already call big merchants more: called share among called and left-alone is A 51%, B 40%, C 23%, D 12%.
- The £340k is an upper limit: a fifth of tasks need no call, and marginal calls earn less than the average.

Schedules and sizing:
- Window 2025-11-01 to 2026-10-27: 30,369 sold-outs (591 a week). **19.1% sit on a deal with an active schedule** (about 113 a week). Whole file: 17.6%. The join is by dates only, unchecked with Merchant Ops.
- Covered sold-outs restock in the export 96.2% of the time, against 56.4% for the others.
- 25.4% of sold-outs share a merchant and an ISO week with another sold-out.
- A **top-up** is the cap increase a schedule adds each run: new cap minus old cap equals `top_up_qty` in 99% to 100% of covered restocks.
- Wait from sold-out to restock for covered deals: weekly median 4 days (90% within 7), fortnightly 8 (13), monthly 16 (27). The averages the rule uses are in the section 6 table (recomputed). My computed "next top-up date" matched the real restock date within a day only 10% to 37% of the time. **Do not use computed dates. Use cadence.**

Other numbers:
- Profit per on-sale day (proxy: `gp_30d_after_gbp / (30 - days sold out)`, restocked rows), mean by band: A £5.10, B £2.38, C £1.26, D £0.65. Averaging over all sold-outs is wrong, because deals that never restocked earn £0.
- Refunds: raw `refunds_gbp / gp_gbp` by band, months from 2025-11: A 0.111, B 0.075, C 0.066, D 0.065. The rule uses a different, corrected share (section 6 table).
- **Trap:** `value_30d_gbp` in the routing input does not match the data pack. It is 1.2 to 9 times the merchant's mean `gp_30d_after_gbp`, with no constant ratio. Do not use it as profit. **Ask Hana what it is.**

Routing service traps (my reading of `inputs/routing-original/`):
- `plan.py` never reads `suppress_soldout_tasks` or the suppression file. With the switch off, output must stay byte-identical. Add a regression test.
- Config order: defaults, then `routing.json`, then `env_overrides.json` (wins). The shipped override sets only priors (0.46 / 0.43, "temporary" since 2026-03, against 0.62 / 0.41 in `priors.json`). The real production override file may differ. Test precedence.
- Rank is `(called - left_alone) x value_30d_gbp`, so the order depends only on `value_30d_gbp`.
- `suppressed_deal_ids` (3 ids) is a separate, existing list for disputes. Keep it separate.
- Promised callbacks must survive suppression (my inference). Do-not-contact stays dropped. A merchant-only suppression row would drop every deal of that merchant, so use deal-level rows.
- New input columns go at the end only. Code and tests use `unittest`. The permission classifier blocked running the downloaded routing tests once. The code only reads CSV and JSON. Ask the user before you try again.

## 6. The deterministic call/skip logic (proposal, not yet accepted by the user)

The user asked for a deterministic rule tied to the cost of a call. The rule has one input that the data cannot give: the **cost of a call in £, `c`**. The pack has no salary, rep cost or cost per minute (checked). An earlier version of this handoff used £6 ("£30 an hour for 12 minutes"). **That number was invented. It is withdrawn.** The user said: do not invent numbers, compute them from the attached data, and say in the handoff what is missing. Priya was asked for `c` (message point 1). Until Priya or Dan answers, show results as a function of `c`. Never show a £ net value as fact.

First match wins:
1. `do_not_contact = 1` → SKIP, "Do not contact".
2. `callback_promised = 1` → CALL first, "Callback promised".
3. `failed_attempts >= 3` → SKIP, "Paused".
4. (Later, from notes or AI: merchant said no / fix a problem first / check capacity / already restocked.)
5. Wait without a call `W`, in days: weekly 4.94, fortnightly 8.38, monthly 16.12, no active schedule 22.33 (recomputed, see the table below).
6. `best_case = pd x W x (1 - r_band)`. Here `pd` is the merchant's mean profit per on-sale day (leave-one-out, fallback to the band mean), and `r_band` is the refund share in the table below. This is the most a call could win back. It is a rough upper bound. It ignores call success odds and any cap raise beyond the refill.
7. `best_case < c` → SKIP. Label it "Auto top-up soon" if a schedule is active. Otherwise "Not worth it".
8. Else CALL, "Worth a call". Show "up to £(best_case - c)". Rank by that. The coin-flip holdout will later measure the real gain.

### Where every number comes from

Scripts: `<scratch folder>\exploration\logic.py` and `calltime.py`. Run `python -I <script> C:\Projects\soldouts\inputs\data-pack` (`logic.py` also takes `C:\Projects\soldouts\inputs\routing-original\input` as a second argument).

| Parameter | Value | Source and method | Status |
|---|---|---|---|
| Wait `W` by schedule type | weekly 4.94 (n=2,498), fortnightly 8.38 (n=2,075), monthly 16.12 (n=2,952), none 22.33 (n=35,554, median 29) | `sold_out_deals.csv` + `auto_replenish_schedules.csv`. Sold-outs 2025-05-04 to 2026-09-27, so all 30 days are observed. Mean of min(days from sold-out to `restocked_date`, 30). A blank `restocked_date` counts as 30. A schedule is active when `start_date <= sold_out_date <= end_date` (blank end = running). | Computed. The date join is not checked with Merchant Ops. An earlier draft used 4.0 / 7.6 / 15.0 (restocked rows only) and 30 for "no schedule" (an assumption). Both withdrawn. |
| Profit per on-sale day `pd` | A £5.10, B £2.38, C £1.26, D £0.65 (band means) | `gp_30d_after_gbp / (30 - days sold out)` over restocked sold-outs with GP known and under 30 days sold out. | Computed, with an assumption: 30-day GP is spread evenly over the on-sale days. GP excludes refunds after 30 days. |
| Refund share `r_band` | A 0.100, B 0.070, C 0.062, D 0.061 | `merchant_months.csv`, months 2025-11 to 2026-10: `refunds_gbp / (gp_gbp + refunds_gbp)`. | Computed upper bound. Using it as a haircut is my modelling choice, not checked with Priya (message point 4). An earlier draft quoted the raw ratio refunds/GP (0.111 / 0.075 / 0.066 / 0.065) as a haircut, and its backtest left the haircut out. Both wrong. |
| Call length | 6.1 min mean, 5.2 median (20,721 calls logged against a restock task). Connected calls (2 min or more): 9.3 mean. 36.5% are under 2 minutes. | `activities.csv`, `type = call`, `sold_out_id` filled, after removing 526 exact repeats (same merchant, task, date, type, owner, duration, subject). | Computed. Routing plans 12 minutes per task, which is higher. Not used in the rule yet. |
| Rep load | 24.5 tasks per rep a week (min 11.3, max 41.9). At most 17 tasks in one rep-day (0 of 6,728 rep-days above 17). 108 call minutes logged per rep a week. | `sold_out_deals.csv` + `merchants.csv` (rep) + `activities.csv`, 2025-11-01 to 2026-10-27. | Computed. The 210-minute day rarely binds. Freed rep time may be small: 10 tasks a week at 6.1 minutes is about 1 rep-hour. An earlier claim of "about 24 rep-hours a week" used 12 minutes for every covered task. Withdrawn. |
| Cost of a call in £ (`c`) | not available | No source in the pack. | **Missing.** Ask Priya or Dan. |

### Backtest: a what-if grid, not an estimate

`c` takes the value shown. Window 2025-11-01 to 2026-10-27, 5,799 covered sold-outs (about 113 a week). The realized best case is profit per on-sale day times the actual days sold out (restocked rows only).

| `c` | Skipped a week | Share of covered | False-skip rate |
|---|---|---|---|
| £3 | 15.7 | 13.9% | 11.6% |
| £6 | 40.4 | 35.8% | 7.9% |
| £9 | 59.4 | 52.6% | 6.6% |
| £12 | 70.9 | 62.9% | 5.4% |
| £15 | 79.8 | 70.8% | 4.1% |

False-skip means the rule skipped, but the realized best case was at least `c`. The predicted best case is 23% to 51% above the realized value in all 12 schedule-by-band cells, so the rule errs toward calling. At `c` = £6 (a grid point only), the skip share is: weekly A 0%, B 32%, C 80%, D 98%; fortnightly A 0%, B 1%, C 43%, D 90%; monthly A 0%, B 0%, C 5%, D 44%. Deals with no schedule are skipped about once a week at £6.

Routing change idea: suppress only **scheduled** deals that fail step 7. Use deal-level rows with source `auto_replenish`. Never touch promised callbacks. One switch; rollback means switch off or empty the file. Holdout: skip for about half, chosen by a hash of the `deal_id`. Keep the task for the other half. Compare 30-day GP between the groups.

## 7. Decisions

Settled: skip automated cap raises (Greg: not before January). Python for now. Project lives in `C:\Projects\soldouts`. The coin flip (holdout) replaces "GP per call" as the proof method, and the cost of a call must enter the rule (the user's own point). Recommendation 1 ("more calls to A and B"): adapt to a net-value rank, but only after Priya answers.

Parked: data source and API ("keep discussing"), contact order, stack details, whether to commit the raw data (I suggest not: 3.6 MB zip, hiring-team data, the facilitator uses unseen data).

## 8. Next steps for you

1. Read Priya's DM in the Desk. If she answered, summarise it simply for the user. Ask which walkthrough slot (11:30 or 15:00) they want, and do not choose for them.
2. Present section 6 to the user in very simple words. Get a yes or no, with c still open.
3. Draft (do not send) a short message for Hana: what `value_30d_gbp` means, what she expects us to trip over, and the path for the Wednesday 15:00 review. Draft one for Greg after 10:30: what he needs to say yes. Also one for Renee, who checks note meaning.
4. Keep grilling: holdout design and the date for "the real number" (30-day GP window plus the freeze), money formula inputs (cost, refund risk), AI note reader scope and Renee's check, status list (10 statuses in three groups: call, skip, other), cut list, hosting and the tool link, change request for Greg, git identity, when to say "go" for the API.
5. Build only after the user says so. Then follow the deliverables in section 4.

## 9. Suggested skills

- `grilling:grilling`: keep the round-based interview.
- `asd-ste100:asd-ste100`: the user's required language style.
- `anthropic-skills:built-in-browser`: reading and writing in the Desk (pane tab `seed`). Quirks: the left drawer toggles with the Menu button, and the chat input accepts text with `form_input`, then the Send button. Coordinates change with the viewport, so take a screenshot first.
- `claude-api`: when the user says "go" for the AI note reader (gateway base URL, thinking and `max_tokens` gotchas).
- `artifact-design` (and the Artifact tool): only if the user wants the rep tool published as a page. Ask before publishing anything.
- `simplify` and `code-review`: after building, before the change request.
