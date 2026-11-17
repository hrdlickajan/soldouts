# Handoff: finish the hand-in (written Tue 17 Nov 2026, Desk time Wed 11 Nov about 01:40)

For the agent that finishes the task. Read `README.md`, `docs/HANDOFF-build.md` (earlier state) and `docs/tasks.md` first. This file says what changed since then, what is NOT verified, and what is left.
Written by hand, not with the `handoff:handoff` skill. Nothing is committed.

**Update, later the same day (the user's decisions):**
- Login is **one "admin" login only** (name `admin`, password `TOOL_PASSWORD`). After login the admin picks any rep, or Everyone, in a dropdown. Marks are saved under the chosen rep (a name that is not a real rep becomes `admin`). `TOOL_USERS` is gone.
- **All messages to people are dropped** (Greg, Dan, Hana, Priya, Renee, Marcus). The people are online in about 5 hours. Do not draft or send any. The change request and three lines stay as files for the Submit panel.
- The README was rewritten small (49 lines) and `docs/three-lines.md` was updated to match. The page was checked at a true 375 px (iframe) against a fake sandbox API: login, rep dropdown, chips, mark save and remove, empty feed, example tasks. No sideways scroll, no tap target under 44 px. Root tests: 171 pass. One run showed a single unexplained failure and three later runs were clean, so one test may be timing-sensitive (suspect the real-time limiter test in `tests/test_10_live.py`).

## Rules that still hold (the user set them)

- No API call without the user's "go" for that step. Never write, print or store the sandbox key. Never touch the routing switch (Greg's written OK first).
- Messages to Greg, Dan, Hana, Priya, Renee: the user sends them. The user said "write to greg and dan". That is ambiguous. Draft them and get a clear "send" in chat before posting anything.
- Do not commit until asked. Git name and email must be set first (the email shows in a public repo). Commit message ends with the attribution line from the system reminder.
- Do not put the Desk URL (it has a secret token), the key, or the user's name from `/me` in any file.
- Talk to the user in short, plain sentences (ASD-STE100, about 80%). No invented numbers: tag every figure computed, assumed or missing.

## What was done this session

- Label "Normal" is now **Call later** (engine, spec table, page, test). Call first = callback promised or high value. Call later = worth a call.
- The rep tool page uses the user's style sheet (`advice/static/theme.css`, copied unchanged from `C:\veci\stylesheet\groupon-style\`).
- **Go 1 done** (3 read-only GETs: `/me`, `/openapi.json`, `/soldouts/today?limit=5`). Findings: about 130 ms a call. Team clock was Wed 11 Nov 2026 01:36 (world day d2). The feed had 0 rows, so the live row shape comes from OpenAPI only. Live rows carry: sold_out_id, restock_task_id, deal_id, deal_name, merchant_id, merchant_name, category, region, city, size_band, rep_id, rep_name, do_not_contact, cap, sold_out_at, team_time, world_day. They do NOT carry the callback flag, failed attempts or value. `GET /marks` returns data[{merchant_id, mark, reason, marked_by, marked_at, set_with}]. `PUT` returns the mark. `DELETE` returns {removed, previous}. The data pack ends 27 Oct, the team clock is 11 Nov, so the call-log window is partly empty.
- Bug fixed: live rows have `sold_out_at`, not `sold_out_date`. `adapters.to_task` now reads both. Tests added first.
- Built (all tested offline with fake transports, **172 root tests pass**):
  - `advice/api.py`: 10 s timeout, one retry on reads, lock on the rate limiter, URL-encoded cursors, `soldouts_today_page()` (rows + team clock), `load_tables()` (merchants, reps, schedules, sold_outs, about 55 requests), `CachedMarks`, `ApiMarks` keeps `marked_at`. An empty key or base no longer falls back to the environment.
  - `advice/feed.py`: `LiveFeed` with a 30 s cache (`live_cache_seconds` in config), stale copy on failure, 10 s wait before asking again, `FeedError` when there is no copy.
  - `advice/auth.py`: one `admin` login with a shared password, HMAC-signed cookie (12 h), fails closed on weak settings. Demo-grade, no lock-out.
  - `advice/web.py` and `api/index.py`, `vercel.json`, `.vercelignore`: the Vercel entry. History loads from the API on the first request, in memory. Login does not wait for it. A rewrite sends every path to the function with the real path in `__p`.
  - `advice/tool.py`: `LiveSource` (bad rows skipped and counted), example tasks (read only, made-up), error JSON (503/502 instead of a dropped connection), login, logout, Origin and JSON checks on writes, `marked_by` forced to the logged-in rep. Local flags: `--history-api`, `--auth`, `--live`.
  - `advice/static/index.html` rewritten (loading and error states, stale banner, Refresh, filter chips, deal name and city, login bar, Mine/Everyone, example button) and `login.html`.
  - Engine: with no call log loaded, the reason says "failed attempts" (unknown), not "estimated".

## NOT verified (do these first)

1. **Page: checked** at 375 px in light mode against a fake API (see the update above). Dark mode was not checked. A real screenshot was not possible (the pane window was hidden), so take phone screenshots for the Submit panel.
2. **Nothing was deployed to Vercel.** Unverified there: the `__p` rewrite (`/:path*` to `/api/index?__p=:path*`), that `advice/static/*` and `routing-service/input/todays_soldouts.csv` are bundled, `maxDuration: 60` on the Hobby plan (the docs I could search did not state the Hobby limit; check with `vercel inspect <url> --json`), and the cold-start time of the history load.
3. **History from the API was never run live.** The row shapes of `/merchants`, `/reps`, `/automation/schedules`, `/soldouts` are assumed to match the CSV files (an earlier shape check said so). Needs Go 2.
4. The routing-service suite (29 tests) was not re-run this session. Run it: `cd routing-service && python -m unittest discover -s tests`.

## Gates the user must give

- **Go 2:** read-only. History tables (about 55 GETs) and `/soldouts/today` again once the feed has rows.
- **Go 3:** marks write test: one `PUT` and one `DELETE` on one merchant, code `test`, removed at once.
- **Deploy:** the user says go and sets these in the Vercel dashboard themselves: `TOOL_PASSWORD`, `SESSION_SECRET`, `GROUPON_API_KEY`, `GROUPON_API_BASE`. Ask which Vercel team and project name. Turn Deployment Protection off for the project so reviewers can open the link. Hobby is for non-commercial use. Put the login (`admin` and the password) in the Submit "notes" field.
- To run the probe or any live step, the user must set the variables in their own Terminal tab. My terminal calls open new tabs without them. Do not read their tab: the key may be on screen. Write results to a file and read the file.

## Left to do

1. Run both test suites (root 171, routing 29) and fix what breaks. Re-run the root suite a few times to see if the flaky test shows again.
2. Optional, with the user's go: Go 2 (read-only history tables, about 55 GETs), Go 3 (one mark `PUT` and `DELETE`, code `test`), and the Vercel deploy (steps above). The README says the tool is not deployed. If it gets deployed, change the "Tool link" line.
3. Open decision: a rep mark `call_first` (new status, and the suppression writer would have to read marks). Not decided, not built. Mark code suggestions in the page: `no_call`, `wrong_number`, `call_back_later`.
4. Commit and push (M13) after the user sets git identity. No key, no `inputs/` content in history. The user then exports AI sessions, takes phone screenshots and presses Submit before **Thursday 09:00 Desk time**.
5. Optional: `/code-review` on `advice/api.py`, `feed.py`, `auth.py`, `tool.py`, `web.py` (cookie flags, Origin check, fail-closed config).
