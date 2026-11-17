"""All API access lives in this module. Every test uses a fake transport. Nothing here runs until the user says "go".

The key comes from the environment (GROUPON_API_KEY). It is never read from a file, printed or stored.
The base URL comes from GROUPON_API_BASE (for example https://<host>/api/sandbox/v1).
Writes: only rep marks (PUT and DELETE /merchants/{id}/mark). The routing switch is never touched here.
"""
import json
import os
import time
import urllib.error
import urllib.request

MAX_MARK_CODE = 64


class ApiError(Exception):
    def __init__(self, status, message=""):
        super().__init__(f"API error {status}: {message}")
        self.status = status


class Client:
    def __init__(self, base=None, key=None, transport=None, sleep=time.sleep, clock=time.monotonic, per_second=10):
        self.base = (base or os.environ.get("GROUPON_API_BASE", "")).rstrip("/")
        self._key = key or os.environ.get("GROUPON_API_KEY", "")
        self._transport = transport or self._urllib
        self._sleep, self._clock, self._gap, self._last = sleep, clock, 1.0 / per_second, 0.0

    def __repr__(self):
        return f"Client(base={self.base!r})"  # never shows the key

    def _urllib(self, method, url, headers, body):
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None), dict(r.headers)
        except urllib.error.HTTPError as e:
            raw = e.read()
            return e.code, (json.loads(raw) if raw else None), dict(e.headers)

    def request(self, method, path, params=None, body=None):
        if not self._key or not self.base:
            raise ApiError(0, "set GROUPON_API_KEY and GROUPON_API_BASE in the environment")
        url = self.base + path
        if params:
            url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        data = json.dumps(body).encode() if body is not None else None
        for attempt in range(2):
            wait = self._gap - (self._clock() - self._last)  # stay under 10 requests a second
            if wait > 0:
                self._sleep(wait)
            self._last = self._clock()
            status, payload, resp_headers = self._transport(method, url, headers, data)
            if status == 429 and attempt == 0:
                self._sleep(float((resp_headers or {}).get("Retry-After", 1)))
                continue
            if status >= 400:
                raise ApiError(status, str((payload or {}).get("error", payload)))
            return payload

    def pages(self, path, **params):
        """Every row of a paged list: {data, next_cursor, total}."""
        cursor = None
        while True:
            q = dict(params, **({"cursor": cursor} if cursor else {}))
            page = self.request("GET", path, q)
            yield from page["data"]
            cursor = page.get("next_cursor")
            if not cursor:
                return

    def soldouts_today(self):
        return list(self.pages("/soldouts/today", limit=1000))

    def reps(self):
        return list(self.pages("/reps", limit=1000))

    def marks(self):
        page = self.request("GET", "/marks")
        return page["data"] if isinstance(page, dict) else (page or [])

    def put_mark(self, merchant_id, mark, reason, marked_by):
        return self.request("PUT", f"/merchants/{merchant_id}/mark", body={"mark": mark, "reason": reason, "marked_by": marked_by})

    def delete_mark(self, merchant_id):
        return self.request("DELETE", f"/merchants/{merchant_id}/mark")

    def messages(self, payload):
        return self.request("POST", "/llm/v1/messages", body=payload)


# ---------- mark stores: the tool uses one of these ----------
def check_mark(mark, reason):
    if not mark or len(mark) > MAX_MARK_CODE:
        raise ValueError(f"the mark code must be 1 to {MAX_MARK_CODE} characters")
    if not reason or not reason.strip():
        raise ValueError("say why in a sentence")


class MemoryMarks:
    def __init__(self, seed=None):
        self._m = dict(seed or {})

    def all(self):
        return dict(self._m)

    def put(self, merchant_id, mark, reason, marked_by):
        check_mark(mark, reason)
        self._m[merchant_id] = {"mark": mark, "reason": reason, "marked_by": marked_by}

    def delete(self, merchant_id):
        return self._m.pop(merchant_id, None) is not None


class FileMarks(MemoryMarks):
    """Marks kept in a local JSON file. For offline use."""

    def __init__(self, path):
        self.path = path
        super().__init__()

    def all(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                self._m = json.load(f)
        except FileNotFoundError:
            self._m = {}
        return dict(self._m)

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._m, f, indent=2)

    def put(self, merchant_id, mark, reason, marked_by):
        self.all()
        super().put(merchant_id, mark, reason, marked_by)
        self._save()

    def delete(self, merchant_id):
        self.all()
        found = super().delete(merchant_id)
        self._save()
        return found


class ApiMarks:
    """Marks kept in the sandbox through the API (needs the key, after 'go')."""

    def __init__(self, client):
        self.client = client

    def all(self):
        return {m["merchant_id"]: {"mark": m["mark"], "reason": m.get("reason", ""), "marked_by": m.get("marked_by", "")}
                for m in self.client.marks()}

    def put(self, merchant_id, mark, reason, marked_by):
        check_mark(mark, reason)
        self.client.put_mark(merchant_id, mark, reason, marked_by)

    def delete(self, merchant_id):
        try:
            self.client.delete_mark(merchant_id)
            return True
        except ApiError as e:
            if e.status == 404:
                return False
            raise
