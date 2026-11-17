"""Vercel entry point. Vercel looks for a class named `handler` in each file under api/.

Every setting comes from environment variables set in the Vercel dashboard (see advice/web.py).
Nothing is read from a file. A missing or weak TOOL_PASSWORD or SESSION_SECRET makes every route answer 503.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from advice.web import build_handler  # noqa: E402

handler = build_handler(os.environ)
