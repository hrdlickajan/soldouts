"""Today's sold-outs from the API, kept for a short time so a phone gets a fast answer.

- A fresh copy is used for `ttl` seconds.
- If the API fails, the last copy is shown as stale, with the reason. The API is not asked again for `retry_after` seconds.
- With no copy yet, a failure is a FeedError. The page shows a clear message and a Retry button.
- `force` (the Refresh button) asks again at once.
The copy lives in the memory of one process. On a hosted function that is best effort: a new instance starts empty.
"""
import threading
import time
from datetime import datetime, timezone

from .api import ApiError


class FeedError(Exception):
    pass


class LiveFeed:
    def __init__(self, client, ttl=30, retry_after=10, clock=time.monotonic):
        self.client, self.ttl, self.retry_after, self._clock = client, ttl, retry_after, clock
        self._rows = self._meta = None
        self._at = self._block_until = 0.0
        self._updated = ""
        self.error = None
        self._lock = threading.Lock()

    def get(self, force=False):
        """(rows, meta). meta: source, date, team_time, total, updated_at, stale, error."""
        with self._lock:
            now = self._clock()
            if not force and self._rows is not None:
                if now - self._at < self.ttl:
                    return self._result(False)
                if now < self._block_until:  # the API failed a moment ago: do not ask again yet
                    return self._result(True)
            try:
                rows, meta = self.client.soldouts_today_page()
            except ApiError as e:
                self._block_until = now + self.retry_after
                if self._rows is None:
                    raise FeedError(str(e)) from e
                self.error = str(e)
                return self._result(True)
            self._rows, self._meta, self._at, self.error = rows, meta, now, None
            self._updated = datetime.now(timezone.utc).isoformat(timespec="seconds")
            return self._result(False)

    def _result(self, stale):
        meta = dict(self._meta, source="live", updated_at=self._updated, stale=stale, error=self.error if stale else None)
        return list(self._rows), meta
