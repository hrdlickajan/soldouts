# Handoff: finish the hand-in (Tue 17 Nov 2026; Desk clock about Wed 11 Nov 02:00)

For the agent that finishes the job. Read `README.md` (short, written for the hand-in) and this file. Older context: `docs/HANDOFF-build.md`, `docs/tasks.md`, `docs/spec.md`.

## Where things stand

- **Code:** done and tested offline. Root suite 174 pass, routing suite 29 pass. One earlier run showed a single unexplained failure and many later runs were clean. Suspect the real-time limiter test in `tests/test_10_live.py`.
- **Pushed:** `main` is on GitHub at `hrdlickajan/soldouts`, latest commit `31c3cb4` (check `git log` for newer). The repo is **private**. The hand-in says "public, or invite the address in your invitation email". The user must do that.
- **Deployed:** Vercel project `soldout-desk` (id `prj_vN5Aun95mDkdNghsC1VuiLZ9iXF8`, the user's personal Hobby team `team_BSOuElD34yZVKexTNDvrsUlX`). It is connected to the GitHub repo, so **every push to `main` deploys to production by itself** (about 10 s build).
- **Public link:** `https://soldout-desk-eight.vercel.app`. This address is NOT behind Vercel's login. The other two aliases (`soldout-desk-hrdlickajans-projects.vercel.app` and the per-deployment URLs) ARE behind Vercel Authentication, so reviewers cannot open them. Never give those out.
- **Configured and live.** All four settings are set for Production. `GROUPON_API_BASE` was set by the previous agent in the browser (plain config). The user typed `TOOL_PASSWORD`, `SESSION_SECRET` and `GROUPON_API_KEY` (Secret type). Never read or enter those values. The user signed in and gave Go 2, and the live app loaded. Details below.
- **Login:** one login, name `admin`, password from `TOOL_PASSWORD`. After login the admin picks any rep, or Everyone, in a dropdown. Marks are saved under the chosen rep.

## What only the user can do (do not do these for them)

1. The four settings are done. Do not enter, read or change the secret values.
2. Say "go" for the next live step (Go 3 below), make the repo public or invite the facilitator, take phone screenshots, export the AI sessions, press Submit before **Thursday 09:00 Desk time**. Put `admin` and the password in the Submit "notes" field.
3. The user decided: **no messages to any person** (Greg, Dan, Hana, Priya, Renee, Marcus). Do not draft or send any.

## Tools and traps

- **Git push:** the user's global git config uses a company proxy that does not resolve off the network. The user approved one direct push. Use `git -c http.proxy= push origin main` (one command, no config change) and tell the user you did. Ask again if the context changes.
- **Vercel:** the `vercel` CLI in the shell cannot log in. Use the Vercel connector tools: `list_deployments`, `get_deployment`, `list_deployment_events` (build log), `get_runtime_logs` (Hobby keeps 1 hour), `create_deployment` (redeploy), `get_project`, `web_fetch_vercel_url` (reaches protected URLs, but it creates a share link, so ask first).
- **Waiting:** a foreground `sleep` is blocked. Poll with a background bash loop, or call `list_deployments` again.
- **Learned the hard way:** Vercel finds the Python handler by reading `api/index.py`, so `class handler(BaseHTTPRequestHandler)` must be written out literally (it is). The home page `/` needs its own rewrite in `vercel.json` (it has one). `.vercelignore` works (it removed 29 files, kept `routing-service/input/todays_soldouts.csv`, which the example tasks need).
- **Do not touch:** the routing switch (Greg's written OK first). No `PUT /routing/switch`, ever.

## Verified on the live link (deployment of `f887b9c`, user signed in, Go 2 given)

- `/login` 200 with the form. `/` redirects to `/login`. `/api/state` without a login gives 401. `/theme.css` 200. A wrong password gives 401 and "Wrong name or password".
- The first `/api/state` after sign-in took about **8.3 s** (a cold start that loads the history from the API). Later calls took under 1 s. Function: Python 3.12, region fra1. `maxDuration: 60` was accepted at build.
- The rep dropdown listed all 24 real reps (R01 to R24), so the history tables loaded from the API. Example tasks load and are read only.
- The feed was **empty**: "0 tasks, team time 03:46". The page shows the empty state and the "Show example tasks" button, as designed.
- **Go 3 done** (team time 03:48): `PUT /api/mark` with merchant `M10001`, code `test`, as `R10` gave 200 and the sandbox's own `marked_at`. The mark showed in `/api/state`. `DELETE` gave `removed: true` and the list was empty again. No mark was left behind. The test ran from the signed-in page with `fetch`, because an empty feed has no cards to mark.
- Vercel adds `path=...` to the query on every rewrite. The handler ignores it. `get_runtime_logs` shows each request with path and status (Hobby keeps 1 hour). Use it for timing.

## Still unverified

1. A real live row through the page. Check again later: the team clock advances and the feed fills during the day.
2. Dark mode, and real phone screenshots.

## Facts about the sandbox (from Go 1, 2026-11-11 01:36 team time)

- About 130 ms a call. Team clock Wed 11 Nov 2026 (world day d2). The pack ends 27 Oct, so call history for the failed-attempts estimate is partly empty. The reason text then says "failed attempts" (unknown).
- Live row fields: sold_out_id, restock_task_id, deal_id, deal_name, merchant_id, merchant_name, category, region, city, size_band, rep_id, rep_name, do_not_contact, cap, sold_out_at, team_time, world_day, posted_in_channel. Not in the row: callback flag, failed attempts, value.
- `GET /marks` gives data[{merchant_id, mark, reason, marked_by, marked_at, set_with}]. `PUT` returns the mark. `DELETE` returns {removed, previous} (404 if none).

## Left to do, in order

1. Look at the feed again for real rows (the team clock advances and the list fills). If rows appear, check the cards and the £ range once.
2. The README and `docs/three-lines.md` already name the link `https://soldout-desk-eight.vercel.app`. Re-read both once after the checks and keep them true.
3. Any change: tests first, `git -c http.proxy= push origin main`, wait for READY, re-check the link. A push gives the next visitor a cold start of about 8 s.
4. Remind the user: repo public or invite, screenshots, AI session export, Submit before Thursday 09:00 Desk time.
5. Optional, if asked: a rep mark `call_first` (new status, and the suppression writer would have to read marks). Not decided, not built.

## Rules that still hold

- No API call without the user's go for that step. Never write, print or store the key. Never put the Desk URL (it has a secret token) or the user's name from `/me` in any file.
- Plain, short sentences (ASD-STE100, about 80%). No invented numbers.
- Commit messages end with the attribution line from the system reminder. Do not commit unless asked.
