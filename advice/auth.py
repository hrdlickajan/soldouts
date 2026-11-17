"""Basic login for the hosted tool. One admin login (name "admin" and a shared password), a signed cookie, nothing stored.

This is a gate for a demo, not a user system. The limits:
- one login only: "admin" with TOOL_PASSWORD. After login the admin picks any rep in a dropdown and acts as that rep.
- the cookie is signed with SESSION_SECRET (HMAC-SHA256) and ends after 12 hours. Nothing is kept on the server.
- a wrong password waits 0.7 seconds. There is no lock-out, because a hosted function keeps no state.
The settings come from the environment and are never written to a file. A missing or weak setting is a ConfigError,
and the hosted tool then refuses every request (it fails closed).
"""
import hashlib
import hmac
import re
import time

COOKIE = "session"
REP = re.compile(r"[A-Za-z0-9_-]{1,32}")
MIN_SECRET, MIN_PASSWORD = 16, 8


class ConfigError(Exception):
    """A setting is missing or too weak. The message names the setting, never a value."""


ADMIN = "admin"


class Auth:
    def __init__(self, password, secret, ttl=12 * 3600, clock=time.time, fail_delay=0.7):
        self._password, self._secret = password.encode("utf-8"), secret.encode("utf-8")
        self.ttl, self._clock, self.fail_delay = ttl, clock, fail_delay

    @classmethod
    def from_env(cls, env):
        problems = []
        password, secret = env.get("TOOL_PASSWORD", ""), env.get("SESSION_SECRET", "")
        if len(password) < MIN_PASSWORD:
            problems.append(f"TOOL_PASSWORD must be set and at least {MIN_PASSWORD} characters")
        if len(secret) < MIN_SECRET:
            problems.append(f"SESSION_SECRET must be set and at least {MIN_SECRET} characters")
        if problems:
            raise ConfigError("; ".join(problems))
        return cls(password, secret)

    # ---- login ----
    def check_login(self, user, password):
        """"admin" when the name and the password are right, else None. The password check takes the same time either way."""
        ok = hmac.compare_digest(hashlib.sha256((password or "").encode("utf-8")).digest(), hashlib.sha256(self._password).digest())
        return ADMIN if ok and (user or "").strip().lower() == ADMIN else None

    # ---- cookie ----
    def _sign(self, rep, exp):
        return hmac.new(self._secret, f"{rep}.{exp}".encode("utf-8"), hashlib.sha256).hexdigest()

    def make_cookie(self, rep):
        exp = int(self._clock()) + self.ttl
        return f"{rep}.{exp}.{self._sign(rep, exp)}"

    def read_cookie(self, header):
        """The rep id from a Cookie header, or None if there is no valid session."""
        for part in (header or "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == COOKIE:
                bits = value.split(".")
                if len(bits) == 3 and REP.fullmatch(bits[0]) and bits[1].isdigit():
                    rep, exp, sig = bits
                    if hmac.compare_digest(sig, self._sign(rep, exp)) and int(exp) > self._clock():
                        return rep
        return None

    def set_cookie_header(self, rep, secure):
        return f"{COOKIE}={self.make_cookie(rep)}; HttpOnly; SameSite=Lax; Path=/; Max-Age={self.ttl}" + ("; Secure" if secure else "")

    def clear_cookie_header(self, secure):
        return f"{COOKIE}=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0" + ("; Secure" if secure else "")
