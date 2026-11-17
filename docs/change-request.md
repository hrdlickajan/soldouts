# Change request: hide auto top-up sold-out tasks (routing 2.15.0 to 2.16.0)

For: Greg Lindqvist, Merchant Ops. **Status: proposal. Nobody has agreed to it.** It has not been sent. The sender sends it.

## What changes

- `routing/plan.py` reads `input/suppressions.csv` when `suppress_soldout_tasks` is `true`. It creates no task for the deals in that file. Nothing else changes: list order, priors, input columns and `suppressed_deal_ids` (disputes) stay as they are.
- **The switch ships off.** With it off, output is identical to 2.15.0 (tested with a golden file and a byte comparison).
- A script writes the file. It lists only deals where all of this holds: the merchant is in test group B (50% of merchant-weeks, by hash), an auto top-up schedule is active, and the best case (the most a call could win back) is under **£6**. £6 is a dial in config (`dial_gbp`). It is yours to raise or lower.
- Never dropped: promised callbacks. Do-not-contact stays dropped. A row with only a merchant id is ignored.
- Not in this change: automated cap raises, new priors, new list order.

## Why

19% of sold-outs sit on a deal with an auto top-up. Reps log a call on 21% of the tasks we would hide. Hiding them for all reps would remove about 39 tasks a week (6.7% of tasks). In the test, only group B loses them: about 20 a week.

## Risk

1. **A hidden task was worth a call.** In the history, 8.0% of hidden tasks still had £6 or more to win back. Each is a small sum. The rep tool still shows these tasks, with the reason.
2. **The schedule join is unchecked.** I join schedules to sold-outs by deal id and dates. Please have Merchant Ops check a sample of deals.
3. **A bad file stops the run** when the switch is on. The loader raises on a row with no id. The writer replaces the whole file on each run. Switching off restores the run.
4. **Group A must stay clean.** A deal row drops every task on that deal. The writer lists a deal only when all its affected tasks are group B.
5. **The test is weak on this change.** It can show only that hiding these tasks does little harm. It cannot show a gain.

## Rollback

Set `suppress_soldout_tasks` to `false`, or empty the file. Output returns to the 2.15.0 output. One action. No data to undo.

## When to stop (my proposal, for you to set)

Switch off if any of these happens:
- a rep reports that a hidden deal needed a call;
- at any read, 30-day GP per touched task is lower in group B and the 95% interval excludes zero;
- the refund share rises and the 95% interval excludes zero;
- you decide to.

The result reader prints these reads from CSV files. The first 30-day GP read comes about a month after launch. The real number comes 8 weeks of tasks plus 30 days of GP after launch. Launch on 8 January 2027 gives 4 April 2027.

## Process and what I ask

1. Diff to Hana first. In the repo: `git diff 5149ce5 HEAD -- routing-service/routing` (5149ce5 is the 2.15.0 baseline commit). Against the Desk download: `diff -ru <2.15.0 folder>/routing routing-service/routing`.
2. Wednesday 15:00 change review. Then Merchant Ops deploys.
3. **Ask:** deploy 2.16.0 with the switch **off** before the freeze. Switch on after 7 January, only with your written OK in chat. Nobody flips it before that.

Questions for you: Is deploying with the switch off before the freeze acceptable? Is £6 the dial you want? Who changes it? What else do you need to say yes?
