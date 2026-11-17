"""The hosted rep tool: what api/index.py serves on Vercel. Settings come from the environment, never from a file.

    TOOL_PASSWORD     the password of the one login, "admin" (8 characters or more)
    SESSION_SECRET    a long random string that signs the login cookie (16 characters or more)
    GROUPON_API_KEY   the sandbox key (kept in the host's secret store, never in the repo)
    GROUPON_API_BASE  for example https://<host>/api/sandbox/v1

It fails closed: a missing or weak TOOL_PASSWORD or SESSION_SECRET gives a 503 on every route.
The history (4 tables) loads from the API on the first request after a cold start, about 55 requests,
and stays in the memory of that instance. The login page does not wait for it.
"""
import threading
import time
from http.server import BaseHTTPRequestHandler

from . import config as cfgmod
from . import demo
from .api import ApiMarks, CachedMarks, Client, MemoryMarks
from .auth import Auth, ConfigError
from .feed import LiveFeed
from .history import History
from .tool import PAGE, LiveSource, Tool, make_handler, past_day_tool


class Runtime:
    """Builds the tool on the first request that needs it, once, even when two phones ask together."""

    def __init__(self, cfg, client):
        self.cfg, self.client = cfg, client
        self._tool, self._lock = None, threading.Lock()

    def tool(self):
        with self._lock:
            if self._tool is None:
                ttl = self.cfg["live_cache_seconds"]
                history = History(self.client.load_tables())
                example = past_day_tool(self.cfg, history)  # the last real day, else the made-up examples
                if example is None:
                    h2, t2, f2, s2 = demo.tool_demo()
                    example = Tool(self.cfg, h2, t2, MemoryMarks(s2), f2)
                self._tool = Tool(self.cfg, history, LiveSource(LiveFeed(self.client, ttl=ttl)),
                                  CachedMarks(ApiMarks(self.client), ttl=ttl), example=example)
            return self._tool


def not_configured(message):
    class Closed(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _refuse(self):
            body = ("This tool is not set up yet. " + message + "\n").encode("utf-8")
            self.send_response(503)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        do_GET = do_POST = do_PUT = do_DELETE = _refuse

    return Closed


def build_handler(env, transport=None, sleep=time.sleep):
    """The handler class for this environment. transport and sleep are for tests."""
    try:
        auth = Auth.from_env(env)
    except ConfigError as e:
        return not_configured(str(e))
    client = Client(base=env.get("GROUPON_API_BASE", ""), key=env.get("GROUPON_API_KEY", ""), transport=transport, sleep=sleep)
    return make_handler(Runtime(cfgmod.load(), client).tool, PAGE.read_text(encoding="utf-8"), auth=auth)
