# Handoff: finish the hand-in (Tue 17 Nov 2026; Desk clock about Wed 11 Nov 02:00)

For the agent that finishes the job. Read `README.md` (short, written for the hand-in) and this file. Older context: `docs/HANDOFF-build.md`, `docs/tasks.md`, `docs/spec.md`.

## Where things stand

- **Code:** done and tested offline. Root suite 174 pass, routing suite 29 pass. One earlier run showed a single unexplained failure and many later runs were clean. Suspect the real-time limiter test in `tests/test_10_live.py`.
- **Pushed:** `main` is on GitHub at `hrdlickajan/soldouts`, latest commit `31c3cb4` (check `git log` for newer). The repo is **private**. The hand-in says "public, or invite the address in your invitation email". The user must do that.
- **Deployed:** Vercel project `soldout-desk` (id `prj_vN5Aun95mDkdNghsC1VuiLZ9iXF8`, the user's personal Hobby team `team_BSOuElD34yZVKexTNDvrsUlX`). It is connected to the GitHub repo, so **every push to `main` deploys to production by itself** (about 10 s build).
- **Public link:** `https://soldout-desk-eight.vercel.app`. This address is NOT behind Vercel's login. The other two aliases (`soldout-desk-hrdlickajans-projects.vercel.app` and the per-deployment URLs) ARE behind Vercel Authentication, so reviewers cannot open them. Never give those out.
- **The app is not usable yet.** The four settings are not set on Vercel, so it fails closed: every page answers 503 "This tool is not set up yet" and names the missing settings (never values). Checked on the deployment of `31c3cb4`: `/`, `/login`, `/api/state`, `/theme.css` and `/api/index` all answer 503 that way, so the rewrite and the handler work on Vercel. The configured path (login, rewrite with real settings, history load) has NOT been run yet. See "What only the user can do".
- **Login:** one login, name `admin`, password from `TOOL_PASSWORD`. After login the admin picks any rep, or Everyone, in a dropdown. Marks are saved under the chosen rep.

## What only the user can do (do not do these for them)

1. In Vercel, project `soldout-desk`, Settings, Environment Variables, Production, set:
   - `TOOL_PASSWORD`: the admin password, 8 characters or more. The user chooses it and puts it in the Submit "notes" field.
   - `SESSION_SECRET`: a long random string, 16 characters or more.
   - `GROUPON_API_KEY`: the sandbox key from the Desk ("Your API key"). Never read it, never write it to a file, never print it.
   - `GROUPON_API_BASE`: `https://desk-production-6adc.up.railway.app/api/sandbox/v1`
2. Say "redeploy" (env changes only apply to new deployments). Then you can redeploy with the connector (`create_deployment` with `deploymentId` of the latest deployment) or push any commit.
3. Say "go" for the first live calls (see below), make the repo public or invite the facilitator, take phone screenshots, export the AI sessions, press Submit before **Thursday 09:00 Desk time**.
4. The user decided: **no messages to any person** (Greg, Dan, Hana, Priya, Renee, Marcus). The people come online in about 5 hours. Do not draft or send any.

## Tools and traps

- **Git push:** the user's global git config uses a company proxy that does not resolve off the network. The user approved one direct push. Use `git -c http.proxy= push origin main` (one command, no config change) and tell the user you did. Ask again if the context changes.
- **Vercel:** the `vercel` CLI in the shell cannot log in. Use the Vercel connector tools: `list_deployments`, `get_deployment`, `list_deployment_events` (build log), `get_runtime_logs` (Hobby keeps 1 hour), `create_deployment` (redeploy), `get_project`, `web_fetch_vercel_url` (reaches protected URLs, but it creates a share link, so ask first).
- **Waiting:** a foreground `sleep` is blocked. Poll with a background bash loop, or call `list_deployments` again.
- **Learned the hard way:** Vercel finds the Python handler by reading `api/index.py`, so `class handler(BaseHTTPRequestHandler)` must be written out literally (it is). The home page `/` needs its own rewrite in `vercel.json` (it has one). `.vercelignore` works (it removed 29 files, kept `routing-service/input/todays_soldouts.csv`, which the example tasks need).
- **Do not touch:** the routing switch (Greg's written OK first). No `PUT /routing/switch`, ever.

## Verify after the user has set the four settings and redeployed

Run these, and report what you see. Each real API call needs the user's go. The first login and first page load already make the hosted function call the API, so ask first.

1. `curl https://soldout-desk-eight.vercel.app/login` gives 200 with a form. `/` gives a redirect to `/login`. `/api/state` without a cookie gives 401.
2. Log in as `admin` in the Browser pane. The first `/api/state` loads the history from the API: about 55 read-only GETs, expect several seconds. Check the function time in `get_runtime_logs`. `vercel.json` asks for `maxDuration: 60`, and whether the Hobby plan accepts it is unconfirmed (no deploy error so far, so it was accepted at build time).
3. Today's feed was **empty** at team time 01:36. If it is still empty, the page shows "No sold-outs yet today" and a "Show example tasks" button. That is expected. If it has rows, check them: this is the first time real live rows go through `to_task`. Compare with the OpenAPI shape in `docs/` notes below.
4. Marks (Go 3): pick a rep, save one mark with code `test` on one merchant, check it shows, remove it. That is one `PUT` and one `DELETE`. Never leave the test mark behind.
5. Open the page at 375 px (iframe trick if the pane window is hidden) and check no sideways scroll. Dark mode was not checked.

## Facts about the sandbox (from Go 1, 2026-11-11 01:36 team time)

- About 130 ms a call. Team clock Wed 11 Nov 2026 (world day d2). The pack ends 27 Oct, so call history for the failed-attempts estimate is partly empty. The reason text then says "failed attempts" (unknown).
- Live row fields: sold_out_id, restock_task_id, deal_id, deal_name, merchant_id, merchant_name, category, region, city, size_band, rep_id, rep_name, do_not_contact, cap, sold_out_at, team_time, world_day, posted_in_channel. Not in the row: callback flag, failed attempts, value.
- `GET /marks` gives data[{merchant_id, mark, reason, marked_by, marked_at, set_with}]. `PUT` returns the mark. `DELETE` returns {removed, previous} (404 if none).

## Left to do, in order

1. Wait for the user's "settings are set". Redeploy. Run the verification above. Fix what breaks (tests first, then push, then re-check).
2. When the link works, edit `README.md` ("Tool link": give `https://soldout-desk-eight.vercel.app`, login `admin`, password goes in the Submit notes) and `docs/three-lines.md` (the Tool link note). If it does not work, leave "none yet, one command" as it is.
3. Commit, push direct, check the new deployment is READY.
4. Remind the user of their steps: repo public or invite, screenshots, AI session export, Submit before Thursday 09:00 Desk time.
5. Optional, if the user asks: a rep mark `call_first` (new status, and the suppression writer would have to read marks). Not decided, not built.

## Rules that still hold

- No API call without the user's go for that step. Never write, print or store the key. Never put the Desk URL (it has a secret token) or the user's name from `/me` in any file.
- Plain, short sentences (ASD-STE100, about 80%). No invented numbers.
- Commit messages end with the attribution line from the system reminder. Do not commit unless asked.
