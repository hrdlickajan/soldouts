# Sold-out advice, routing change and result reader

Reps get one restock task for each sold-out. This repo helps reps choose which tasks to call.

| Part | Where | What it does |
|---|---|---|
| Engine | `advice/engine.py` | One set of rules. It gives each task a status, a reason, a £ range and a test group. |
| Rep tool | `advice/tool.py` | A phone page. It shows today's sold-outs. Reps can mark a merchant. |
| Routing change | `routing-service/` | Routing 2.15.0 with the suppression switch wired in. The switch is **off**. |
| Result reader | `advice/result_reader.py` | It reads CSV files offline. It compares group B with group A. |

Nothing is switched on. Greg must give written OK in chat before anyone changes the switch.

## Run it

You need Python 3.10 or newer. You do not need to install packages.

```bash
python -m advice.tool --demo
```

Open http://127.0.0.1:8080. The demo uses made-up data. The tool is not hosted.

Run the result reader on a folder with the data-pack CSV files:

```bash
python -m advice.result_reader <folder> --json result.json
```

## Test it

```bash
python -m unittest discover -s tests -t .
cd routing-service && python -m unittest discover -s tests
```

All tests run offline. The data pack is not in this repo. Tests that need it skip when it is missing.

The routing parity tests also run on the original service:

```bash
cd routing-service
ROUTING_UNDER_TEST=<folder of routing 2.15.0> python -m unittest tests.test_parity
```

The same tests pass on both services. With the switch off, the output is the same as 2.15.0.

## What I decided, and why

- **One engine.** The tool, the suppression writer and the result reader use the same rules. They cannot disagree.
- **Best case ranks tasks.** Best case is profit per on-sale day, times the expected wait without a call, times one minus the refund share. It is the most a call can win back. It is not a forecast.
- **Hide only scheduled tasks.** A task is hidden if its deal has an active auto top-up and its best case is under £6. The £6 is a policy dial in the config. It is not the cost of a call. Greg owns it.
- **Test design.** A hash of the merchant and the ISO week sets the group. 50% of merchant-weeks are group B. The reader compares only the tasks where the two routings differ.
- **Small routing change.** The change is 18 lines in `plan.py`. The switch is off. When it is on, the service drops the deals in the suppression file. It keeps promised callbacks. It keeps dropping do-not-contact merchants. It ignores rows that have only a merchant id.
- **Code does all sums.** Each £ figure has a tag: computed, assumed or missing. The pay rate of £17 to £32 an hour is an assumption. It changes the £ display only.
- **`value_30d_gbp` is not used.** In the routing input it is 1.2 to 19.7 times the merchant's mean 30-day GP in the data pack. The median is 3.7.

## What the data shows

I ran the reader on the data pack (1 Nov 2025 to 27 Oct 2026, 30,369 tasks).

- Reps log a call on 39.0% of tasks. They log a connected call (120 seconds or more) on 28.2%.
- Some calls come 8 or 9 days after the sold-out. A 7-day window gives 27.3%.
- The A/A check passes. Nothing was applied, and all differences sit inside their 95% intervals.
- The skip rule hides about 39 tasks a week (6.7% of tasks). Reps log a call on 21% of them. 8.0% of them still had £6 or more to win back.
- Range now: a 10-point rise in the connected-call share of top-fifth tasks gives about 614 extra calls a year. The value is £0, about £6.8k at the memo's £11 a call, or about £62.9k at the ceiling of £102 a call. This is a scenario, not a forecast.
- The real number arrives 8 weeks plus 30 days after launch. Launch on 8 January 2027 gives 4 April 2027.

## What it cannot do yet

- The live feed has no callback flag and no failed-attempts count. The tool estimates failed attempts from the call log and says "Unknown".
- I did not call the API. The shape of a live row is an assumption.
- Merchant Ops has not checked the schedule join. I join by deal id and dates.
- The data has no cost per call. The £11 in the memo is not validated.
- The reader cannot measure "promised callbacks kept". The data has no callback flag.
- The test can show only that the skip does little harm.

## What I cut

- Hosting. One command runs the tool.
- The live AI run. The note reader runs on a stub only.
- Reviews and refund reasons as note sources.
- List order in routing, a rep login, a "flag a finding" button, and a check with Marcus.
- Automated cap raises.

## Where AI is used, and how I checked it

Claude Code wrote the code. I checked it with tests. Some tests reproduce numbers from the data pack. When a test failed, I found the cause before I changed the code.

The product has one AI part: the note reader. It reads rep notes and alert replies. It returns a finding, a quote and a confidence. I did not run it on the real gateway. It runs on a stub.

Code checks every AI answer:
- The quote must appear in the source text. If not, the code drops the finding.
- The code retries once on a bad answer.
- A spend limit stops the run.

Nobody has checked the findings against a rep who knows the merchants.
