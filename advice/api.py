"""All API access lives in this module. Every test uses a fake transport. Nothing here runs until the user says "go".

The key comes from the environment (GROUPON_API_KEY). It is never read from a file, printed or stored.
The base URL comes from GROUPON_API_BASE (for example https://<host>/api/sandbox/v1).
Writes: only rep marks (PUT and DELETE /merchants/{id}/mark). The routing switch is never touched here.

Made for a phone and a hosted function: short timeouts, one retry on reads, a lock on the rate limiter,
a short cache for the marks, and a loader that builds the history tables from the API.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

MAX_MARK_CODE = 64
RETRY_STATUS = (500, 502, 503, 504)
# The four tables the advice engine needs for a live sold-out. Same field names as the data-pack CSV files.
HISTORY_TABLES = {"merchants": "/merchants", "reps": "/reps", "schedules": "/automation/schedules", "sold_outs": "/soldouts"}


class ApiError(Exception):
    def __init__(self, status, message=""):
        super().__init__(f"API error {status}: {message}")
        self.status = status


class Client:
    def __init__(self, base=None, key=None, transport=None, sleep=time.sleep, clock=time.monotonic, per_second=10, timeout=10):
        # None means "read the environment". An empty string means "not set": no fallback to the environment.
        self.base = (os.environ.get("GROUPON_API_BASE", "") if base is None else base).rstrip("/")
        self._key = os.environ.get("GROUPON_API_KEY", "") if key is None else key
        self._transport = transport or self._urllib
        self._sleep, self._clock, self._gap, self._last = sleep, clock, 1.0 / per_second, 0.0
        self._lock = threading.Lock()  # two phones at once must still stay under the rate limit
        self.timeout = timeout

    def __repr__(self):
        return f"Client(base={self.base!r})"  # never shows the key

    def _urllib(self, method, url, headers, body):
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None), dict(r.headers)
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, (json.loads(raw) if raw else None), dict(e.headers)
            except ValueError:
                return e.code, {"error": "not JSON"}, dict(e.headers)
        except ValueError:
            raise ApiError(502, "the API answered with something that is not JSON") from None
        except (urllib.error.URLError, OSError) as e:  # timeouts, DNS, refused connections
            raise ApiError(0, "network: " + str(getattr(e, "reason", e))) from None

    def _pace(self):
        with self._lock:
            wait = self._gap - (self._clock() - self._last)  # stay under 10 requests a second
            if wait > 0:
                self._sleep(wait)
            self._last = self._clock()

    def request(self, method, path, params=None, body=None):
        if not self._key or not self.base:
            raise ApiError(0, "set GROUPON_API_KEY and GROUPON_API_BASE in the environment")
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        data = json.dumps(body).encode() if body is not None else None
        for attempt in range(2):
            self._pace()
            try:
                status, payload, resp_headers = self._transport(method, url, headers, data)
            except ApiError as e:
                if attempt == 0 and method == "GET" and e.status == 0:  # a read may be tried once more
                    self._sleep(0.5)
                    continue
                raise
            if status == 429 and attempt == 0:
                self._sleep(float((resp_headers or {}).get("Retry-After", 1)))
                continue
            if status in RETRY_STATUS and attempt == 0 and method == "GET":
                self._sleep(0.5)
                continue
            if status >= 400:
                raise ApiError(status, str((payload or {}).get("error", payload)) if isinstance(payload, dict) else str(payload))
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

    def me(self):
        return self.request("GET", "/me")

    def soldouts_today_page(self):
        """(rows, meta). meta carries the team clock the API puts around the list: date, team_time, world_day, total."""
        rows, meta, cursor = [], {}, None
        while True:
            page = self.request("GET", "/soldouts/today", dict({"limit": 1000}, **({"cursor": cursor} if cursor else {})))
            if not meta:
                meta = {k: page[k] for k in ("date", "team_time", "world_day", "total") if k in page}
            rows.extend(page["data"])
            cursor = page.get("next_cursor")
            if not cursor:
                return rows, meta

    def soldouts_today(self):
        return self.soldouts_today_page()[0]

    def reps(self):
        return list(self.pages("/reps", limit=1000))

    def load_tables(self, tables=None):
        """The history tables, one thread per table. Each table pages one request after the other."""
        tables = tables or HISTORY_TABLES
        with ThreadPoolExecutor(max_workers=len(tables)) as pool:
            futures = {name: pool.submit(lambda p=path: list(self.pages(p, limit=1000))) for name, path in tables.items()}
            return {name: f.result() for name, f in futures.items()}

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
        return {m["merchant_id"]: {"mark": m["mark"], "reason": m.get("reason", ""), "marked_by": m.get("marked_by", ""),
                                   "marked_at": m.get("marked_at", "")}
                for m in self.client.marks()}

    def put(self, merchant_id, mark, reason, marked_by):
        check_mark(mark, reason)
        reply = self.client.put_mark(merchant_id, mark, reason, marked_by)
        saved = {"mark": mark, "reason": reason, "marked_by": marked_by}
        if isinstance(reply, dict) and reply.get("marked_at"):
            saved["marked_at"] = reply["marked_at"]
        return saved

    def delete(self, merchant_id):
        try:
            self.client.delete_mark(merchant_id)
            return True
        except ApiError as e:
            if e.status == 404:
                return False
            raise


class CachedMarks:
    """Keeps the marks for a short time, so a page load does not call the API every time.

    Our own save and remove change the copy at once. If the API fails, the last copy stays and `error` says why.
    """

    def __init__(self, inner, ttl=30, clock=time.monotonic):
        self.inner, self.ttl, self._clock = inner, ttl, clock
        self._data, self._at, self.error = None, 0.0, None
        self._lock = threading.Lock()

    def all(self):
        with self._lock:
            if self._data is not None and self._clock() - self._at < self.ttl:
                return dict(self._data)
            try:
                self._data, self._at, self.error = self.inner.all(), self._clock(), None
            except ApiError as e:
                if self._data is None:
                    raise
                self.error = str(e)
                self._at = self._clock() - self.ttl + min(10, self.ttl)  # try again in a few seconds
            return dict(self._data)

    def put(self, merchant_id, mark, reason, marked_by):
        saved = self.inner.put(merchant_id, mark, reason, marked_by)
        with self._lock:
            if self._data is not None:
                self._data[merchant_id] = saved if isinstance(saved, dict) else {"mark": mark, "reason": reason, "marked_by": marked_by}
        return saved

    def delete(self, merchant_id):
        found = self.inner.delete(merchant_id)
        with self._lock:
            if self._data is not None:
                self._data.pop(merchant_id, None)
        return found
