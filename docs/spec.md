# Spec: Sold-out advice, routing change and result reader

**Status: ready to implement.** Version 2. Written from the conversation (no interview).
**Implementer:** the `ponytail` agent. Make the smallest complete change. Do not wait for anyone. Every open question has a default below.
**Tracker:** none is configured, so this spec is a local file. The `ready-for-agent` label is not applied. The user confirmed the test seams ("ok, good").
**Marks:** **[Decided]** the user said so in chat. **[Default]** I chose it so work can start. Change it only if the user says so. **[Assumed]** a labelled assumption, never a fact.

What changed since version 1: test group is 50:50 (decided); every open item now has a default; added data contracts, configuration, build order and acceptance checks; added the A/A check; fixed the "called" definitions.

## Problem Statement

About 600 sold-outs a week create one restock task each on a rep's morning list. Reps dislike them. The routing service creates a task for every sold-out. It does not look at auto-replenish schedules or Deal Alert state. So a deal that an automation will refill in a few days still gets a task.

Reps do not call every task. Over 1 Nov 2025 to 27 Oct 2026, reps logged a call on 39.0% of tasks and a connected call (2 minutes or more) on 28.2%. On deals with an active schedule they logged a call on only 20.5%. On the tasks with the highest expected gain they logged a call on only 52.1%. Time is not the limit: no rep-day had more than 17 tasks, and 17 tasks fit the 210-minute day. So the lever is which tasks get attention, not how many calls fit.

The only evidence that "calls pay" is a memo that claims £11 GP per call. The memo compares merchants that reps chose to call. It controls for size band only. It did not join the schedules. It ignores refunds after 30 days. Nobody has a cost per call: Dan points to Priya, Priya points to Dan or Greg, and Greg points to Sales.

Dan Okafor (VP Sales) wants three things by Thursday 09:00 on the Desk clock: a rep tool that works on a phone, a routing change that Greg will switch on, and a number he can defend, with a range now and a date for the real one. Greg Lindqvist (Head of Merchant Ops) likes things with an off switch. A change freeze runs from Monday to 7 January. Greg's written OK must come before anyone flips the switch.

## Solution

One advice engine decides, for each sold-out task, a status, a plain reason and a rough £ range. Statuses sit in three groups: call, skip, other. Three things use the engine:

1. **Rep tool.** A phone page that lists today's sold-outs with the status, the reason, the £ range, and a supporting quote when the note reader found one. Reps can mark a merchant with a short code and a reason.
2. **Routing change.** The existing sold-out suppression switch is wired into the routing service. It is off by default. When it is on, the routing service drops the tasks listed in the suppression file. The engine writes that file. It lists only auto-top-up tasks of merchants in test group B.
3. **Result reader.** A script that rebuilds the groups and statuses from data files and compares group B with group A on the tasks where the two differ. It prints a range now and the date the real number arrives. It runs offline.

**Test design [Decided]:** group A keeps today's routing. Group B gets the new routing. The split is **50:50**. A hash of the merchant and the ISO week of the sold-out date decides the group. We read the result only on touched tasks.

## User Stories

Reps
1. As a rep, I want to open today's sold-outs on my phone, so that I can plan my morning in one look.
2. As a rep, I want each sold-out to show one status in the call, skip or other group, so that I know what to do without reading anything long.
3. As a rep, I want a plain reason next to each status, so that I can trust it or overrule it.
4. As a rep, I want a rough £ range on tasks worth a call, so that I can compare tasks quickly.
5. As a rep, I want to see the quote behind a note-based status, so that I can check it myself.
6. As a rep, I want promised callbacks to appear first, so that I keep my word to the merchant.
7. As a rep, I want do-not-contact merchants to show as skip, so that I never call someone I must not call.
8. As a rep, I want to mark a merchant with a short code and a reason, so that the team knows why I left it alone.
9. As a rep, I want to see and remove my own marks, so that I can fix a wrong mark.
10. As a rep, I want the page to load fast on a mobile connection, so that I can use it between meetings.
11. As a rep, I want a skip task to stay visible with its reason, so that I can still call if I know something the tool does not.
12. As a rep, I want the tool to tell me when a deal has an auto top-up, so that I do not ask the merchant for a cap raise that is already coming.
13. As a rep, I want to pick my name once and have the page remember it, so that I do not log in.

Senior account managers
14. As a senior account manager (Renee), I want to check the AI findings against merchants I know, so that wrong findings get caught.
15. As a senior account manager, I want to see the quote and the source note for each finding, so that I can judge it in seconds.
16. As a senior account manager, I want to flag a finding as wrong, so that the error rate is on record.

Dan
17. As Dan, I want a tool I can open on my phone, so that I can see what reps see.
18. As Dan, I want one number with a range, so that I can defend it on Friday.
19. As Dan, I want the date when the real number arrives, so that I can plan the follow-up.
20. As Dan, I want a cut list with reasons, so that I know what was left out on purpose.
21. As Dan, I want the money sums done in code, so that nobody argues with an AI guess.
22. As Dan, I want every £ tagged computed, assumed or missing, so that I know how far to trust it.

Greg and Merchant Ops
23. As Greg, I want one switch that is off by default, so that nothing changes without my decision.
24. As Greg, I want rollback to be "switch it off", so that a bad day costs me one action.
25. As Greg, I want to own the £ dial that hides tasks, so that I can raise or lower it at any time.
26. As Greg, I want a one-page change request with risk, rollback and when to stop, so that I can decide at the Wednesday review.
27. As Greg, I want no automated cap raises in this change, so that my January rule holds.
28. As Greg, I want the switch to stay off until I give written OK in chat, so that the log shows a clean sequence.
29. As Hana, I want output identical to version 2.15.0 when the switch is off, so that deploying is safe.
30. As Hana, I want the diff against the original service to be small and readable, so that I can review it first.
31. As Hana, I want config precedence tested (defaults, routing config, environment override), so that the override cannot surprise us.
32. As Hana, I want the existing disputed-deal list to stay separate from the new suppression file, so that ops keep their tool.
33. As Hana, I want each suppression row to name a deal, a reason and a source, so that I can audit it.

Analysts and assessors
34. As Priya, I want the called definition to be explicit and configurable, so that results compare with her memo.
35. As Priya, I want the schedule join method written down, so that Merchant Ops can check it.
36. As the facilitator, I want to run the tests and the result reader offline on unseen data, so that I need no network or key.
37. As the facilitator, I want the README to say how to run, what was decided, what it cannot do and what was cut, so that I can judge the choices.
38. As the facilitator, I want the commit history kept, so that I can see how the work grew.
39. As an assessor, I want every agreement named in the README to be one made in the Desk, so that the record is honest.

Maintainers
40. As a maintainer, I want one adapter layer that turns CSV history, API rows and the routing input file into one internal record, so that the rules never care where data came from.
41. As a maintainer, I want API access in one small module, so that all other code and all tests run offline.
42. As a maintainer, I want the fitted parameters (waits, profit per day, refund shares, cut points) written to config by a "fit" step, so that I can refresh them without editing code.
43. As a maintainer, I want the group assignment to be a pure function, so that the tool, the suppression writer and the result reader agree on every merchant-week.
44. As a maintainer, I want the result reader to work from CSV files alone, so that it runs on unseen data.
45. As a maintainer, I want an A/A check on historical data, so that I know the pipeline shows no effect where none exists.
46. As a maintainer, I want the sandbox key never written to disk or the repo, so that I do not leak it.

## Implementation Decisions

### Data and adapters
- **[Decided]** The CSV data pack is the only source for every number, backtest and test. The API is used only for today's sold-outs, rep marks and the AI gateway, and only after the user says "go" for each. The read-only shape check is done. Result: for all 11 history tables the API has the same field names, row counts and sampled values as the CSV files. Differences: blank cells are null, numbers are numbers, do-not-contact is true or false, the merchant list adds the rep name and team, and lists come as a data array with a cursor and a total.
- Three input shapes feed one internal task record: (a) data-pack history rows, (b) API rows, (c) the routing service's input file (yesterday's sold-outs).
- The live feed of today's sold-outs lacks the value, the promised-callback flag and the failed-attempts count. The routing input file has all three.
- **[Default]** Failed attempts in the tool (no routing file): count "No answer" calls on the merchant's tasks in the last 30 days, reset by any connected call. Unvalidated proxy: show "unknown" in the reason text when the proxy is the only source.
- **[Default]** Promised callback in the tool: from the note reader if it ships, else unknown (treated as not promised, with "unknown" in the reason).
- API access sits in one module. All tests run offline.

### Called definitions
- **Logged call:** at least one call activity with the task's sold-out id, after removing exact repeats (same merchant, task, date, type, owner, duration and subject).
- **Connected call:** a logged call of at least 120 seconds.
- **[Default]** The primary metric uses connected calls within 7 days of the sold-out. Both numbers are reported. Priya's answer may change the minutes or the window. Both are config values. In the pack, every logged call falls within 7 days of its sold-out.

### Best case, statuses and labels
- **[Decided]** Rank by best case. The order does not depend on the cost of a call.
- Best case = the merchant's profit per on-sale day (leave one out; fall back to the band mean) × the expected wait without a call (by schedule type: weekly, fortnightly, monthly, none) × (1 − refund share of the band). It is an upper bound on what a call can win back. In the pack the predicted value runs 23% to 51% above the realized value, so the rule errs toward calling.
- A schedule is active on a sold-out date when start date ≤ sold-out date ≤ end date. A blank end date means it still runs. The join is by deal id and dates. Use cadence, never computed top-up dates.
- **[Decided]** The dial is £6, in config, owned by Greg. It is a policy dial, not a claim about the cost of a call.
- **[Default]** "High value" means best case at or above the top-fifth cut point. Fitted value from the pack: £87.60. The bottom-fifth cut point is £13.64 (for information only).
- **[Decided]** Statuses (ten). Rule order, first match wins:

| # | Status | Group | Label | Rule |
|---|---|---|---|---|
| 1 | `do_not_contact` | skip | Skip | do-not-contact is true |
| 2 | `callback_promised` | call | Call first | callback is promised |
| 3 | `rep_marked_no_call` | skip | Skip | the merchant has a mark `no_call` |
| 4 | `rep_marked_other` | other | Other | the merchant has any other mark |
| 5 | `paused_failed_attempts` | skip | Skip | failed attempts is 3 or more |
| 6 | `fix_problem_first` | other | Other | note finding of that type (optional module) |
| 7 | `check_capacity_first` | other | Other | note finding of that type (optional module) |
| 8 | `high_value` | call | Call first | best case ≥ top-fifth cut point |
| 9 | `auto_top_up_soon` | skip | Skip | schedule active and best case < dial |
| 10 | `worth_a_call` | call | Call later | everything else |

- Every status has one fixed plain-language reason template. Tests check the exact text.
- Tasks with no active schedule are never `auto_top_up_soon`.

### Test groups [Decided: 50:50]
- Group = a deterministic hash of the merchant id and the ISO year-week of the sold-out date. Take SHA-256 of the merchant id, a vertical bar and the year-week string. Read the first 8 hex digits as an integer. Divide by 2^32. Group B if the result is below the share. The share is a config value, default **0.5**. Zero means everyone is group A.
- Every deal of one merchant in one week lands in one group.
- Group A tasks also get the status the new routing would give ("would-be status"). The result reader compares touched tasks: tasks whose would-be status is `high_value` or `auto_top_up_soon`.
- **[Default]** Tool modes. `demo` (default for the hand-in link): the tool shows advice for all tasks and shows the group badge. `test`: the tool shows advice only for group B tasks and shows group A tasks as plain tasks with only hard facts (do-not-contact, promised callback, marks). The mode is config.
- Metrics. Fast: share of `high_value` tasks with a connected call within 7 days. Slow: 30-day GP per touched task. Guards: refund share, connected calls per rep per week, promised callbacks kept. The result reader reports each as the difference B minus A with a 95% interval.
- Honest limits: Skip saves little rep time and the test can show only that it does little harm. The `high_value` label is the bigger lever. After 13 weeks at 50:50 the smallest visible difference on the top fifth is 7.1 points of call share and £9.12 of 30-day GP.

### Money in code
- Code does all sums. The AI never does sums. Every figure carries a tag: computed, assumed or missing.
- **[Assumed]** Rep pay rate range: £17 to £32 an hour. Method: salary £33,000 to £45,000 (sources below) divided by 1,950 to 1,700 working hours, with 0% to 20% employer on-costs added at the high end. Low = 33,000 / 1,950. High = 45,000 / 1,700 × 1.2. Rep-time cost per call = logged call length × rate. At the mean logged length of 6.1 minutes this is £1.72 to £3.23. At the 12 minutes routing plans it is £3.38 to £6.35. The rate is config. It affects only the £ display. It never changes a status.
- The £ shown to a rep is a range. High = best case minus the low end of the rep-time cost. Low = best case × low realization minus the high end of the rep-time cost. Floor both at zero. The default low realization is 0 (a call may have no effect), so the low end is £0 and the page reads "up to £X". Refund risk is already inside best case through the refund share. Tag the rate and the realization "assumed".

### Routing change
- Wire the existing suppression switch (`suppress_soldout_tasks`, default off) and the suppression file into task creation. One switch. Rollback = switch off or empty the file.
- With the switch off, output is byte-identical to version 2.15.0.
- Config order: defaults, then routing config, then environment override. The override wins. The shipped override sets only the restock priors.
- Suppression rows are deal-level, with source `auto_replenish`, reason `auto_top_up_soon`. Never write merchant-only rows (one would drop every deal of that merchant). The disputed-deal list stays separate and unchanged.
- Promised callbacks survive suppression. Do-not-contact stays dropped.
- **[Default]** Release 1 changes task creation only. The list order, the priors and the input columns stay as today. Labels and best-case rank live in the rep tool.
- The engine reads the routing input file plus the history files and writes the suppression file. It writes rows only for group B tasks with status `auto_top_up_soon`.
- Process (README and change request): diff to Hana first, then the Wednesday 15:00 review, then Merchant Ops deploy. **[Default]** Ask to deploy with the switch off before the freeze, and to switch on after 7 January with Greg's written OK. Nobody flips the switch, not even in the sandbox, before that OK.

### Rep tool
- **[Default]** One page plus a small JSON endpoint, served by a one-command Python standard-library server. The README gives the command. Hosting is on the cut list. If time remains, host it only after asking the user.
- Reads today's sold-outs from the API feed (in `demo` mode with the key from an environment variable, never from a file), or from a local file for offline use. Shows status, reason, £ range and quote. Marks use the API (short code, reason, who marked), sandbox only.
- **[Default]** The rep picks a name from the reps list. The page remembers it in the browser. No login.
- Mobile first: one column, large tap targets, no horizontal scroll.

### AI note reader (optional module)
- Reads rep notes, alert replies, reviews and refund reasons through the Messages passthrough on the sandbox key (USD 20 budget). **Start only after the user says "go" for the gateway.** Until then the module runs against a stub.
- Output per text: a finding type (one of `fix_problem_first`, `check_capacity_first`, `merchant_said_no`, `callback_promised`, `none`), the supporting quote and a confidence. Code checks that the quote appears in the source text. If it does not, the finding is dropped. One retry on a bad response.
- Gateway rules: use a high `max_tokens` (2000 or more) or disable thinking; never force a tool choice; read the stop reason; stay under 10 requests a second; keep a running spend guard well under USD 20.
- **[Default]** Sources, in order: rep notes, alert replies. Reviews and refund reasons are cut unless time remains.
- Findings are checked against Renee. The implementer does not message anyone. The user does.

### Result reader
- Input: a folder of CSV files with the data-pack names, plus config. Output: plain text and a JSON summary.
- It rebuilds statuses and groups from the files for every sold-out in a date range. It joins outcomes (logged and connected calls, first-call day, 30-day GP). It compares B and A on touched tasks.
- Before launch (no launch date in config) it prints an **A/A check** on history: nothing was applied, so every difference must sit inside its interval. After launch it counts tasks from the launch date on.
- "Range now" (scenario, not an estimate). For a lift of L points in the connected-call share of `high_value` tasks: extra calls a year = about 6,145 × L. Value per extra call: low £0 (no effect); mid £11 (the memo's figure, unvalidated); ceiling £102 (mean realized best case, assumes a call wins back the whole wait). Worked example, L = 10 points: about 615 calls a year, £0 low, about £6.8k at the memo figure, about £62.9k ceiling. Skip rule: about 4 connected calls a week (8.4 logged, 51 minutes) saved, worth about £14 to £27 a week of rep time at the assumed rates.
- "Date for the real number" = launch date + accrual weeks (config, default 8) + 30 days of GP follow-up. Example: launch 8 January 2027 gives 4 April 2027.

### Configuration (all in one config; defaults shown)
Share on new routing 0.5; dial £6; top-fifth cut £87.60; connected seconds 120; window days 7; failed-attempts limit 3; failed-attempts proxy window 30 days; pay-rate range £17 to £32; planned minutes per task 12; mean logged minutes 6.1; fitted parameters (waits by cadence, profit per on-sale day by band, refund share by band); tool mode `demo`; launch date empty; accrual weeks 8.

### Build order and acceptance checks
Each step starts with failing tests. Each step must pass before the next starts.
1. **Adapters.** Given the same sold-out in CSV, API and routing-file shapes, the adapters return equal records. Blank and null are equal. Do-not-contact 0 and false are equal.
2. **Fit.** Running the fit on the pack reproduces the Key facts below within rounding: waits, profit per day, refund shares, cut points.
3. **Engine rules.** Each of the ten statuses has a test. Order tests: a do-not-contact task with a callback is `do_not_contact`. Boundary tests at the dial and the cut point. Schedule edge cases: blank end date, sold-out on the start date, sold-out on the end date.
4. **Groups.** The hash is deterministic. Same merchant and week give the same group. Over the pack, the share of group B is 0.5 within 1 point. Share 0 gives all A.
5. **Routing copy.** Original tests still pass. Switch off gives byte-identical output on the shipped input. Switch on drops listed deals. Callbacks survive. Do-not-contact stays dropped. A merchant-only row is ignored. Override beats routing config. Disputed-deal list unchanged.
6. **Suppression writer.** From the shipped routing input plus history, it writes only group B `auto_top_up_soon` rows. A callback task is never written.
7. **Result reader.** The A/A check on the pack passes. The "range now" and the date print as specified. It runs with the network off.
8. **Rep tool.** Opens on a 375-pixel-wide screen with no horizontal scroll. Shows the ten statuses with their reasons. `test` mode hides advice for group A. Marks round-trip against a stub of the API.
9. **Note reader (after "go").** The quote check drops a made-up quote. The stub test passes. Spend guard stops at the limit.
10. **README and cut list.** How to run, how to test, what was decided, what it cannot do, what was cut, where AI is used and how it was checked.

## Testing Decisions

- A good test checks external behaviour only: data in, statuses, rows, files or text out. It does not check how the code gets there.
- Tests come first. Use `unittest`, as the routing service does.
- All tests run offline on small hand-made fixtures plus a few real rows from the pack. No test uses the network or the sandbox key.
- **Seams [Decided]:**
  1. **Advice engine** (new, highest seam): task records and history in; status, reason, £ range, group and would-be status out. Most tests live here.
  2. **Routing plan builder** (existing seam, with the original unit tests as prior art): rows, priors and config in; today's list and carried-over list out.
  3. **Result reader** (thin, new): a folder of files in; text and JSON out.
  The ideal is one seam. We use three because the routing service is a separate package and the reader must run from files.
- Prior art: the original routing tests for plan and config.

## Out of Scope

- Automated cap raises (Greg: not before January).
- Flipping the routing switch in any environment.
- Any API write other than rep marks, and those only after "go".
- Merchant-only suppression rows.
- Deal Alert opens and clicks, merchant booking data, and the reasons reps skip a task (not in the pack).
- A real cost per call. Only a labelled assumption for the £ display.
- Live reload of routing config.
- Any change to routing priors, list order or input columns in release 1.
- Accounts, logins and roles in the rep tool.
- Sending messages to anyone. The user does that.

## Further Notes

**Rules for the implementer**
- Make the smallest complete change that meets the acceptance checks. Do not add features that are not here.
- Do not commit. Ask the user first. Git name and email are not set.
- The `inputs/` folder is read-only. Build the routing change as a copy and show the diff against the original.
- Never write, print or store the sandbox key. Never call POST, PUT or DELETE on the API. Never touch the routing switch. Make no API call at all until the user says "go".
- Use no employer material.
- Where this spec and the Desk differ, the Desk wins. Tell the user.

**Terms.** *Sold-out*: a deal reached its cap. *Restock task*: the task routing creates for one sold-out. *Auto top-up / schedule*: Merchant Ops adds cap on a cadence. *Best case*: the most a call could win back before the next top-up. *Dial*: the £ level below which a scheduled task is hidden. *Touched task*: a task where new and current routing differ. *Group A / B*: current / new routing. *Called*: see the definitions above.

**Key facts** (computed from the data pack by throwaway scripts; window 1 Nov 2025 to 27 Oct 2026 unless noted; step 2 of the build order must reproduce them):
- 30,369 sold-outs, 591 a week. 19.1% (5,799) sit on a deal with an active schedule (date join, unchecked by Merchant Ops).
- Logged-call share: 39.0% of tasks; band A 51.7%, B 42.6%, C 30.4%, D 21.7%; scheduled deals 20.5%; others 43.4%. Connected-call share: 28.2% of tasks.
- Top fifth by best case (6,077 tasks, about 6,145 a year, 294 merchants, 86% band A, only 8 on scheduled deals): logged 52.1%, connected 42.0%. Bottom fifth: logged 22.2%. Cut points £13.64 and £87.60. Mean realized best case of the top fifth £102.37 (median £92.95; 3,176 restocked rows with GP known).
- At a £6 dial: 40.4 tasks a week hidden (6.8% of all tasks, 35.8% of scheduled tasks). Reps log a call on 20.7% of them and a connected call on 9.0%. False-skip rate (realized best case still at least £6): 7.9%.
- Wait without a call (days): weekly 4.94, fortnightly 8.38, monthly 16.12, none 22.33. Profit per on-sale day: A £5.10, B £2.38, C £1.26, D £0.65. Refund share of GP: A 0.100, B 0.070, C 0.062, D 0.061 (upper bound).
- Logged call length: mean 6.1 minutes, median 5.2, after removing 526 exact repeats; 36.5% are under 2 minutes. Routing plans 12 minutes a task.
- First call after a sold-out: median 3 days, 90% within 6 days. No call is logged before its sold-out date.
- Noise (80% power, 5% false alarm, 50:50): over all tasks, mean 30-day GP is £24.22 (spread £40.02) and the smallest visible difference after 13 weeks is £2.55. On the top fifth: 9.1 points of call share after 8 weeks and 7.1 after 13; £11.63 of 30-day GP after 8 weeks and £9.12 after 13.
- Task-linked activity subjects (raw counts, repeats not removed): "Restock call - no change" 7,706; "No answer" 6,277; "Restock call - cap raised" 5,742; "Deal Alert sent" (type call) 1,430; email "Your deal sold out" 2,620; note "Left voicemail" 1,073.
- Trap: `value_30d_gbp` in the routing input is 1.2 to 9 times a merchant's mean 30-day GP in the pack, with no constant ratio. The engine does not use it.

**Sources for the pay-rate assumption** (web search, Nov 2026): Coburg Banks sales recruiter, typical account manager £28k to £48k, median about £38k; Payscale, Account Manager Sales £32,914, Senior Account Manager £41,348; ITJobsWatch, median £45,000 (IT sector). The hours and on-costs are my assumptions.

**People and agreements.** Nobody has agreed to any change. Facts from the Desk: Greg said the skip advice in the tool is between the user and Sales, and a change to what routing creates is his. Priya never joined the schedules, did not check within band, did not check refunds after 30 days, and did not clean the CRM repeats. Messages sent, answers not yet in: Priya (connected-call definition, steps behind the £11), Hana (`value_30d_gbp`, review timing), Greg (change-request needs, deploy timing, the £6 dial), Renee (why reps leave tasks alone, behaviour near auto top-ups). None of these blocks the build.

**Timeline.** Freeze runs from Monday to 7 January. If Greg agrees to switch on after the freeze, the first 30-day GP read comes about 6 February and an 8-week read about 4 April.

**Candidate cut list** (for the README and the three lines): hosting beyond a one-command run; reviews and refund-reason sources for the note reader; list ordering inside routing; a rep login; checking against Marcus; the two note-finding statuses if the note reader does not ship.

**Time.** The exercise asks for about 3 hours of work. Build in the order above and stop when time runs out. Anything not built goes on the cut list.
