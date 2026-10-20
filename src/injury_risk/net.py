"""HTTP GET that trusts the operating system's certificate store.

On this machine Norton Web/Mail Shield re-signs HTTPS traffic with its own root certificate. That root is in
the Windows store but not in the bundle ``requests`` ships with, so ``requests`` fails verification. Python's
default SSL context reads the Windows store, so plain urllib with that context verifies normally.
"""
from __future__ import annotations

import ssl
import urllib.error
import urllib.request

_CONTEXT = ssl.create_default_context()
USER_AGENT = "Mozilla/5.0 (injury-risk research)"


def get(url: str, timeout: float = 60, headers: dict | None = None) -> tuple[int, bytes]:
    """Return (status, body); an HTTP error status comes back with an empty body instead of raising."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(request, context=_CONTEXT, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, b""
