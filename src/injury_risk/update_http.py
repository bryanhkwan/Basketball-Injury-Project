"""Small, bounded web reader for scheduled updates. Raw responses stay under data/."""
from __future__ import annotations

import hashlib
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlsplit

USER_AGENT = "BasketballInjuryProject/1.0 (+https://github.com/bryanhkwan/Basketball-Injury-Project)"
AGENTS = ("BasketballInjuryProject", "ChatGPT-User", "Claude-User", "Perplexity-User", "*")
MAX_BYTES = 20 * 1024 * 1024


class SourceError(RuntimeError):
    pass


class Robots:
    """Use the longest matching rule, including robots wildcards and Allow exceptions."""

    def __init__(self, text):
        if re.search(r"<!doctype|<html", text, re.I):
            raise SourceError("robots.txt returned HTML; access policy could not be checked")
        self.groups = []
        agents, rules, delay = [], [], 0
        started = False
        for line in text.splitlines() + ["User-agent: end-of-file"]:
            key, _, value = line.split("#", 1)[0].partition(":")
            key, value = key.strip().lower(), value.strip()
            if key == "user-agent":
                if started:
                    self.groups.append((agents, rules, delay))
                    agents, rules, delay, started = [], [], 0, False
                agents.append(value.lower())
            elif agents and key in ("allow", "disallow", "crawl-delay"):
                started = True
                if key == "crawl-delay":
                    try:
                        delay = max(delay, float(value))
                    except ValueError:
                        raise SourceError("unreadable Crawl-delay")
                elif value:
                    rules.append((key == "allow", value))

    def policy(self, agent, path):
        matches = [(max([len(a) for a in aa if a != "*" and a in agent.lower()] or [0]), rr, dd)
                   for aa, rr, dd in self.groups if any(a == "*" or a in agent.lower() for a in aa)]
        best = max((m[0] for m in matches), default=0)
        rules, delay = [], 0
        for score, rr, dd in matches:
            if score == best:
                rules.extend(rr)
                delay = max(delay, dd)
        hits = []
        for allow, pattern in rules:
            regex = re.escape(pattern).replace(r"\*", ".*")
            if pattern.endswith("$"):
                regex = regex[:-2] + "$"
            if re.match(regex, path):
                hits.append((len(pattern.replace("*", "").rstrip("$")), allow))
        return (max(hits)[1] if hits else True), delay


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, hosts, raw: Path, *, budget=100, sleep=time.sleep, clock=time.monotonic):
        self.hosts, self.raw, self.budget = set(hosts), raw, budget
        self.sleep, self.clock = sleep, clock
        self.policies, self.last = {}, {}
        self.opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))

    def _address(self, url):
        u = urlsplit(url)
        if u.scheme != "https" or u.hostname not in self.hosts or u.username or u.password or u.port not in (None, 443):
            raise SourceError("source URL is outside its allowed HTTPS hosts")
        return u

    def _request(self, url, delay=2.5):
        u = self._address(url)
        if self.budget <= 0:
            raise SourceError("request budget exhausted")
        if delay > 30:
            raise SourceError("source requests a longer crawl delay than this job supports")
        self.sleep(max(0, self.last.get(u.hostname, -1000) + max(2.5, delay) - self.clock()))
        self.budget -= 1
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            try:
                response = self.opener.open(request, timeout=25)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise SourceError("response exceeds the size limit")
                return response.code, dict(response.headers.items()), body
        except (OSError, TimeoutError) as error:
            raise SourceError(f"network request failed ({type(error).__name__})") from error
        finally:
            self.last[u.hostname] = self.clock()

    def _policy(self, url):
        u = self._address(url)
        if u.hostname not in self.policies:
            status, _, body = self._request(f"https://{u.hostname}/robots.txt")
            if status in (404, 410):
                body = b""
            elif status != 200:
                raise SourceError(f"{u.hostname}: robots.txt unavailable (HTTP {status})")
            self.policies[u.hostname] = Robots(body.decode("utf-8", "replace"))
        path = u.path or "/"
        if u.query:
            path += "?" + u.query
        decisions = [self.policies[u.hostname].policy(a, path) for a in AGENTS]
        if not all(allowed for allowed, _ in decisions):
            raise SourceError("robots.txt does not allow this request")
        return max(delay for _, delay in decisions)

    def get(self, url):
        for _ in range(4):
            delay = self._policy(url)
            for attempt in range(2):
                status, headers, body = self._request(url, delay)
                if status not in (429, 500, 502, 503, 504) or attempt:
                    break
                retry = next((v for k, v in headers.items() if k.lower() == "retry-after"), "5")
                if not retry.isdigit() or int(retry) > 15:
                    raise SourceError(f"source asks to retry later (HTTP {status})")
                self.sleep(max(5, int(retry)))
            if status in (301, 302, 303, 307, 308):
                location = next((v for k, v in headers.items() if k.lower() == "location"), None)
                if not location:
                    raise SourceError("redirect has no destination")
                url = urljoin(url, location)
                continue   # check the destination's host and robots before following
            if status != 200:
                raise SourceError(f"source returned HTTP {status}")
            digest = hashlib.sha256(body).hexdigest()
            self.raw.mkdir(parents=True, exist_ok=True)
            path = self.raw / (digest + (".pdf" if body.startswith(b"%PDF") else ".html"))
            if not path.exists():
                path.write_bytes(body)
            return body, path, digest
        raise SourceError("too many redirects")
