"""Rep tool. One page plus a small JSON endpoint, served by the Python standard library. No login, no install.

    python -m advice.tool --demo                                       # made-up data, nothing else needed
    python -m advice.tool --data <data folder> --tasks <routing input csv>
    python -m advice.tool --data <data folder> --live                  # today's sold-outs from the API
                                                                       # (needs GROUPON_API_KEY and GROUPON_API_BASE)
Then open http://127.0.0.1:8080 . To open it on a phone on the same Wi-Fi add --host 0.0.0.0.

Modes (config tool_mode, or --mode):
  demo  advice for every task, with the test group badge
  test  advice only for group B tasks. Group A tasks show as plain tasks with only hard facts
        (do-not-contact, promised callback, rep marks).
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import config as cfgmod
from . import demo
from .adapters import load_routing_tasks, to_task
from .api import ApiError, ApiMarks, Client, FileMarks, MemoryMarks
from .engine import Engine
from .history import History, load_pack

HARD = ("do_not_contact", "callback_promised", "rep_marked_no_call", "rep_marked_other")
PAGE = Path(__file__).with_name("static") / "index.html"


def _r2(x):
    return None if x is None else round(x, 2)


def _order(r):
    s = r["status"]
    first = 0 if s == "callback_promised" else 1 if s == "high_value" else 2 if s in ("worth_a_call", "task") else 3 if r["kind"] == "other" else 4
    return first, -(r["gbp_high"] or 0)


class Tool:
    def __init__(self, cfg, history, tasks, marks, findings=None):
        self.cfg, self.h, self._tasks, self.marks, self.findings = cfg, history, tasks, marks, findings or {}
        self.engine, self.mode = Engine(cfg, history), cfg["tool_mode"]

    def _row(self, a):
        t = a.task
        row = {"task_id": t.task_id, "merchant_id": t.merchant_id, "merchant_name": t.merchant_name, "deal_id": t.deal_id,
               "sold_out_date": t.sold_out_date.isoformat(), "mark": a.mark}
        if self.mode != "test":
            row["group"] = a.group
        full = self.mode != "test" or a.group == "B"
        if full or a.status in HARD:
            row.update(status=a.status, kind=a.kind, label=a.label, reason=a.reason,
                       gbp_low=_r2(a.gbp_low) if full else None, gbp_high=_r2(a.gbp_high) if full else None,
                       quote=a.quote if full else "", tags=a.tags if full else {})
        else:  # test mode, group A: a plain task
            row.update(status="task", kind="other", label="Task", reason="Restock task.", gbp_low=None, gbp_high=None, quote="", tags={})
        return row

    def state(self, rep_id=None):
        marks = self.marks.all()
        tasks = self._tasks() if callable(self._tasks) else self._tasks
        rows, names = [], {}
        for t in tasks:
            names[t.merchant_id] = t.merchant_name
            rep = self.h.merchants.get(t.merchant_id, {}).get("rep_id")
            if rep_id and rep and rep != rep_id:  # a merchant with no known rep is shown to everyone
                continue
            rows.append(self._row(self.engine.advise(t, marks, self.findings)))
        rows.sort(key=_order)
        mine = [{"merchant_id": m, "merchant_name": names.get(m, m), **v} for m, v in marks.items()
                if not rep_id or v.get("marked_by") == rep_id]
        reps = [{"rep_id": r["rep_id"], "rep_name": r.get("rep_name") or r["rep_id"]} for r in self.h.reps]
        return {"mode": self.mode, "reps": reps, "rows": rows, "marks": mine}

    def put_mark(self, merchant_id, mark, reason, marked_by):
        self.marks.put(merchant_id, mark, reason, marked_by)

    def delete_mark(self, merchant_id):
        return self.marks.delete(merchant_id)


def make_handler(tool, page):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj))

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/":
                self._send(200, page, "text/html")
            elif u.path == "/api/state":
                self._json(200, tool.state(parse_qs(u.query).get("rep", [None])[0]))
            else:
                self._json(404, {"error": "not found"})

        def do_PUT(self):
            if urlparse(self.path).path != "/api/mark":
                return self._json(404, {"error": "not found"})
            try:
                b = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                tool.put_mark(b.get("merchant_id", ""), b.get("mark", ""), b.get("reason", ""), b.get("marked_by", ""))
                self._json(200, {"ok": True})
            except (ValueError, KeyError) as e:
                self._json(400, {"error": str(e)})
            except ApiError as e:
                self._json(502, {"error": str(e)})

        def do_DELETE(self):
            u = urlparse(self.path)
            if u.path != "/api/mark":
                return self._json(404, {"error": "not found"})
            try:
                self._json(200, {"removed": tool.delete_mark(parse_qs(u.query).get("merchant_id", [""])[0])})
            except ApiError as e:
                self._json(502, {"error": str(e)})

    return Handler


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true", help="made-up data, nothing else needed")
    ap.add_argument("--data", help="folder with the data-pack CSV files (history)")
    ap.add_argument("--tasks", help="routing input file with today's sold-outs (offline)")
    ap.add_argument("--live", action="store_true", help="read today's sold-outs from the API")
    ap.add_argument("--api-marks", action="store_true", help="keep marks in the sandbox through the API")
    ap.add_argument("--marks", default="marks.json", help="local marks file (default marks.json)")
    ap.add_argument("--findings", help="JSON file from the note reader: {merchant_id: {type, quote, ...}}")
    ap.add_argument("--mode", choices=["demo", "test"])
    ap.add_argument("--config")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args(argv)

    cfg = cfgmod.load(args.config, **({"tool_mode": args.mode} if args.mode else {}))
    findings = json.loads(Path(args.findings).read_text(encoding="utf-8")) if args.findings else {}
    if args.demo:
        history, tasks, demo_findings, seed = demo.tool_demo()
        marks, findings = MemoryMarks(seed), findings or demo_findings
    else:
        if not args.data or not (args.tasks or args.live):
            ap.error("use --demo, or --data with --tasks or --live")
        history = History(load_pack(args.data))
        client = Client() if (args.live or args.api_marks) else None
        tasks = (lambda: [to_task(r, history.merchants) for r in client.soldouts_today()]) if args.live \
            else load_routing_tasks(args.tasks, history.merchants)
        marks = ApiMarks(client) if args.api_marks else FileMarks(args.marks)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(Tool(cfg, history, tasks, marks, findings), PAGE.read_text(encoding="utf-8")))
    print(f"Rep tool ({cfg['tool_mode']} mode) on http://{args.host}:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
