# Sold-out advice

For each sold-out restock task, one engine gives a status (Call first, Call later, Skip, Other), a plain reason and a rough £ range. Three parts use it: a phone rep tool (`advice/`), a routing change with the switch off (`routing-service/`), and an offline result reader (`advice/result_reader.py`).

- **Tool:** https://soldout-desk-eight.vercel.app. Login `admin`, the password is in the Submit form. The first visit after a quiet period takes about 8 seconds.
- **Run:** `python -m advice.tool --demo` (made-up data, http://127.0.0.1:8080). Python 3.12 or newer, no packages.
- **Test (offline):** `python -m unittest discover -s tests -t .` and, in `routing-service/`, `python -m unittest discover -s tests`. No network and no key.
- **Tests that skip without the data pack:** 10 in the root suite (the fit, the 50:50 split, the A/A check, the range now). These are the tests that tie the numbers to the data, so run them if you have the pack: `SOLDOUTS_DATA_PACK=<pack folder> python -m unittest discover -s tests -t .` (the default is `inputs/data-pack`). In `routing-service/`, one test checks the 2.15.0 comparison on the Desk's own input file, and skips unless `inputs/routing-original` exists. The other routing comparison tests use a 28-row hand-made input.
- **Result reader:** `python -m advice.result_reader <folder of CSV files>`.

## Decisions

- **Best case ranks tasks.** Profit per on-sale day, times the expected wait without a call, times one minus the refund share. It is the most a call can win back, not a forecast.
- **Hide only auto top-up tasks under £6.** The £6 is made up. We have not found the real value. It is a dial in `advice/config.json`.
- **50:50 test.** A hash of the merchant and the week sets the group.
- **Code does the sums.** Every £ figure is tagged computed, assumed or missing. The switch stays off until Greg says yes in writing.

## Where AI is used, and how I checked it

- **Claude Code wrote the code and the docs.** The checks are tests: unit tests on hand-made data, tests that reproduce known numbers from the data pack, and the result reader's A/A check on history, where every difference must sit inside its interval.
- **In the product, AI never does a sum.** Every £ figure comes from code and is tagged computed, assumed or missing.
- **The AI note reader is built but was never run on the real gateway** (see "Not done"). With `--live` it would ask a model for a finding type and a quote. Code drops any finding whose quote is not in the source text. It retries once on a bad answer, ignores an answer that stopped for `max_tokens`, stays at 5 requests a second and stops at a spend limit of USD 5. These checks are tested with scripted fake replies only.
- **Not checked:** the findings against a person who knows the merchants. That needs the live run first.

## Not done

- No real live row has gone through the page yet. The sandbox feed was empty when I checked (team time 04:03). While it is empty, the page shows the last day in the API history, read only.
- Cut: the live AI note reader (a stub), reviews and refund texts, list order in routing, automated cap raises, per-rep logins.
- I started in the evening. The team is offline now, but this is the only time I have to do it. So nothing is agreed with anyone.
