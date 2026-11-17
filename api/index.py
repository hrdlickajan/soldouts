"""Vercel entry point. Vercel looks for a class named `handler` in each file under api/.

Every setting comes from environment variables set in the Vercel dashboard (see advice/web.py).
Nothing is read from a file. A missing or weak TOOL_PASSWORD or SESSION_SECRET makes every route answer 503.
"""
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from advice.web import build_handler  # noqa: E402

_impl = build_handler(os.environ)


class handler(BaseHTTPRequestHandler):
    """Vercel finds this class by reading this file, so it is written out here.
    It takes every method from the real handler that advice/web.py builds for this environment."""


for _name, _value in vars(_impl).items():
    if not _name.startswith("__"):
        setattr(handler, _name, _value)
