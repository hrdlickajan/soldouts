# Tasks: minimal working solution (MWS)

Companion to `docs/spec.md`. The implementer works in another session. This file only lists and orders the work.

**Owners:** IMPL = implementer session. USER = you. CLAUDE = this session (drafts, checks).
**Gate "go":** the task touches the sandbox API. It starts only after the user says "go" for that task.
**Rules that hold for every task:** no API call without "go". No PUT, POST or DELETE except where a task says so. Never flip the routing switch. Never write the sandbox key anywhere. Messages to characters are sent by the user.

## What "minimal working solution" means

The MWS runs fully offline from the CSV data pack and the routing input file. It has no API calls and no AI calls. It gives eight active statuses. The two note-based statuses stay dormant. Tests pass with the network off. The hand-in is submitted. Everything else is optional.

## Must: the MWS

| # | Owner | Task | Done when | Blocked by |
|---|---|---|---|---|
| M1 | IMPL | Adapters and fit (spec steps 1 and 2) | CSV, API-shaped and routing-file rows give equal records. The fit reproduces the Key facts. | none |
| M2 | IMPL | Engine: best case, eight active statuses, £ range with tags (step 3) | One test per status. Order, boundary and schedule edge tests pass. | M1 |
| M3 | IMPL | Test groups at 50:50 (step 4) | Hash is deterministic. Group B share is 0.5 within 1 point on the pack. | M1 |
| M4 | IMPL | Routing copy with suppression wired behind the switch (step 5) | Switch off gives byte-identical output. Switch on drops listed deals. Callbacks survive. Override tests pass. Diff against the original is small. | M2, M3 |
| M5 | IMPL | Suppression writer (step 6) | It writes only group B `auto_top_up_soon` rows from the shipped routing input. | M2, M3 |
| M6 | IMPL | Result reader (step 7) | A/A check passes. "Range now" and the date for the real number print. Runs with the network off. | M2, M3 |
| M7 | IMPL | Rep tool, offline (step 8). Reads the routing input file and the CSV history. Shows status, reason and £ range. Rep marks stay in the browser. | 375-pixel screen, no sideways scroll. All active statuses show with their reasons. | M2 |
| M8 | IMPL | README and cut list (step 10) | It covers how to run, how to test, decisions, limits, cuts, and where AI is used and how it was checked. | M4, M5, M6, M7 |
| M9 | CLAUDE | Check the Desk for replies from Priya, Hana, Greg and Renee. Apply default changes to the spec. Tell the user what changed. | Spec and Desk agree. | none |
| M10 | CLAUDE draft, USER send | Short message to Hana with the diff or repo link, for her review | Sent before the Wednesday 15:00 review. | M4 |
| M11 | CLAUDE draft, USER send | One-page change request for Greg: what changes, risk, rollback, stop rule, the £6 dial, the 50:50 share, the timeline | Sent in chat to Greg before the review. | M4, M5, M10 |
| M12 | CLAUDE draft | Three lines for Dan: what you did, what it is worth (range and date), what you cut | Plain text, readable on a phone. | M6, M8 |
| M13 | USER | Set the git name and email. Make the first commit. Keep the history. Push to a repo and get the link. | Repo link works. No key in history. | M8 |
| M14 | USER | Export AI sessions. Take phone screenshots. Press Submit. | Submitted before Thursday 09:00 on the Desk clock. The latest submission counts. | M8, M11, M12, M13 |

Order: M1 first. Then M2 and M3. Then M4, M5, M6 and M7 in any order. M9 runs at any time, and best at the start and again before M11.

## Optional

| # | Owner | Task | Gate | Fallback if cut | Blocked by |
|---|---|---|---|---|---|
| O1 | IMPL | **Live feed.** The tool reads today's sold-outs from the API (GET). | go | The tool reads the routing input file. | M7 |
| O2 | IMPL | **Marks in the API.** Rep marks go to the sandbox (PUT, DELETE, GET). | go | Marks stay in the browser. | M7 |
| O3 | IMPL | **AI note reader.** It reads rep notes and alert replies through the LLM gateway (POST). It returns a finding and a supporting quote. Code checks that the quote is in the source text. A spend guard keeps spend under the USD 20 budget. Start with a stub. | go | The two note statuses stay dormant. Say so in the README. | M2 |
| O4 | USER send | Ask Renee, and Marcus if time allows, to check a sample of the findings. | none | Say "unchecked" in the README. | O3 |
| O5 | IMPL | Add reviews and refund reasons as sources for the note reader. | go | Cut first. | O3 |
| O6 | IMPL | Turn on `fix_problem_first`, `check_capacity_first` and the promised-callback finding from the note reader. | go | Statuses stay dormant. | O3, O4 |
| O7 | USER decide, IMPL build | Host the tool at a public link. | ask the user which host | One-command run in the README. | M7 |
| O8 | IMPL | Tool `test` mode: hide advice for group A. Needed before real reps use it, not for the demo. | none | Demo mode only. Say so in the README. | M7 |
| O9 | IMPL | Rep picks a name and the page remembers it. | none | One shared view. | M7 |
| O10 | USER send | Ask Merchant Ops (Hana) to check the schedule join by date. | none | The README says the join is unchecked. | none |
| O11 | USER send | Reply to Dan's open "anything you need?" with a short status. | none | none | none |

## If time runs out: cut in this order

1. O5 reviews and refund reasons.
2. O3, O4 and O6 together (the whole AI reader).
3. O7 hosting.
4. O9 and O8.
5. O1 and O2 last. They are cheap, but they need your "go" and add risk.

Never cut M4, M5 or M6. The routing change and the result reader are the core of the hand-in. Put every cut in the README and in the three lines.

## Gates to remember

- **No API call at all** until you say "go". The read-only shape check was the only exception.
- **Greg's written OK** comes before anyone flips the switch. The freeze blocks it until 7 January.
- **Sandbox writes** (marks, switch) land in the sandbox only, but the switch stays off regardless.
