# Sold-out advice

One engine decides, for each sold-out restock task, a status (Call first, Call later, Skip, Other), a plain reason and a rough £ range. Three things use it: a phone **rep tool** (`advice/`), a **routing change** with the switch off (`routing-service/`), and an offline **result reader** (`advice/result_reader.py`). I spent most of my time on the logic, not on the screens.

## Run and test

```bash
python -m advice.tool --demo          # made-up data, open http://127.0.0.1:8080
python -m unittest discover -s tests -t .
cd routing-service && python -m unittest discover -s tests
```

Python 3.10 or newer, no packages. Tests run offline. Tests that need the data pack skip when it is missing. The result reader runs on a folder of CSV files: `python -m advice.result_reader <folder>`.

## The hand-in, item by item

- **Three lines for Dan:** `docs/three-lines.md`. What I did, what it is worth (a scenario range of £0 to about £62.9k a year, real number on 4 April 2027 if we launch on 8 January), and what I cut.
- **Tool link:** https://soldout-desk-eight.vercel.app (Vercel free tier). One `admin` login, the password is in the Submit notes field. After signing in you pick any rep in a dropdown. The first visit after a quiet period takes about 8 seconds. The one command above also works.
- **Repo link:** this repo, history kept, no key in it.
- **Zip:** not needed, the repo is enough.
- **AI sessions:** exported in the Submit panel. Claude Code wrote the code. I checked it with tests that were written first, and with numbers rebuilt from the data pack.
- **Screenshots:** of the tool at phone width, in the Submit panel.
- **Change request for Greg:** `docs/change-request.md`. It was not sent. Nobody has agreed to it.

## What I decided

- **Best case ranks tasks.** Profit per on-sale day, times the expected wait without a call, times one minus the refund share. It is the most a call can win back, not a forecast.
- **Hide only auto top-up tasks under £6.** The £6 is a dial in `advice/config.json`. It is not the cost of a call. Greg owns it.
- **50:50 test.** A hash of the merchant and the week sets the group. The result reader compares group B with group A, and passes an A/A check on history.
- **Code does the sums.** Every £ figure is tagged computed, assumed or missing. The switch stays off until Greg says yes in writing.

## What it cannot do yet

- Today's sandbox feed was still empty when I checked (team time 03:46), so no real live row has gone through the page yet. The history and the rep list do load from the sandbox. Live rows have no callback flag and no failed-attempts count, so the tool says "unknown".
- The data pack ends on 27 October. History loaded from the API is the same data.
- The test can show only that hiding these tasks does little harm.

## What I cut, and why

- **The live AI note reader.** It runs on a stub. No rep checked its findings, and I would not show unchecked findings as advice.
- **Reviews and refund texts as sources.** Cut first, they add the least.
- **List order and priors in routing.** A smaller change is easier for Greg to say yes to.
- **Automated cap raises.** Greg said not before January.
- **Per-rep logins.** One admin login is enough for now.

## People

I chatted with the people very little: one question to Dan about the cost of a call, one message to Priya. I did not talk to Greg, Hana, Renee or Marcus. So nothing here is agreed with anyone. The £11 a call and the cost of a call are not validated, Merchant Ops has not checked the schedule join, and the change request is only a proposal.
