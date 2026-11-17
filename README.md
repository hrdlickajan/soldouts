# Sold-out advice

For each sold-out restock task, one engine gives a status (Call first, Call later, Skip, Other), a plain reason and a rough £ range. Three parts use it: a phone rep tool (`advice/`), a routing change with the switch off (`routing-service/`), and an offline result reader (`advice/result_reader.py`).

- **Tool:** https://soldout-desk-eight.vercel.app. Login `admin`, the password is in the Submit form. The first visit after a quiet period takes about 8 seconds.
- **Run:** `python -m advice.tool --demo` (made-up data, http://127.0.0.1:8080). Python 3.12 or newer, no packages.
- **Test (offline):** `python -m unittest discover -s tests -t .` and, in `routing-service/`, `python -m unittest discover -s tests`. Tests that need the data pack skip when it is missing.
- **Result reader:** `python -m advice.result_reader <folder of CSV files>`.

## Decisions

- **Best case ranks tasks.** Profit per on-sale day, times the expected wait without a call, times one minus the refund share. It is the most a call can win back, not a forecast.
- **Hide only auto top-up tasks under £6.** The £6 is made up. We have not found the real value. It is a dial in `advice/config.json`.
- **50:50 test.** A hash of the merchant and the week sets the group.
- **Code does the sums.** Every £ figure is tagged computed, assumed or missing. The switch stays off until Greg says yes in writing.

## Not done

- No real live row has gone through the page yet. The sandbox feed was empty when I checked (team time 04:03). While it is empty, the page shows the last day in the API history, read only.
- Cut: the live AI note reader (a stub), reviews and refund texts, list order in routing, automated cap raises, per-rep logins.
- I started in the evening. The team is offline now, but this is the only time I have to do it. So nothing is agreed with anyone.
