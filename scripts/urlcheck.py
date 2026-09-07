#!/usr/bin/env python3
"""Reject private, local, and credentialed URLs before fetch."""

from __future__ import annotations

import ipaddress
import re
import socket
import ssl
import urllib.error
import urllib.request
from urllib.parse import urlparse

MAX_URL = 500
PROBE_TIMEOUT = 6
READ_BYTES = 2048
MAX_REDIRECTS = 4
USER_AGENT = "tamatv-channel-check/1.0"
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")

BLOCK_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.goog",
    "kubernetes",
    "kubernetes.default",
    "kubernetes.default.svc",
    "instance-data",
}
BLOCK_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".lan",
    ".home",
    ".corp",
    ".invalid",
    ".localdomain",
)


def ip_is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return bool(ip.is_global)


def host_is_blocked(host: str) -> bool:
    name = (host or "").strip().lower().rstrip(".")
    if not name or name in BLOCK_HOSTS:
        return True
    return any(name.endswith(suffix) for suffix in BLOCK_SUFFIXES)


def _hostname(url: str) -> str:
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return ""
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        return ""
    try:
        return host.encode("idna").decode("ascii")
    except Exception:
        return ""


def host_resolves_public(host: str) -> bool:
    name = (host or "").strip().lower().rstrip(".")
    if not name or host_is_blocked(name):
        return False
    try:
        return ip_is_public(ipaddress.ip_address(name))
    except ValueError:
        return bool(resolve_public_ips(name))


def is_safe_https_url(url: str, *, resolve: bool = False) -> bool:
    return is_safe_fetch_url(url, schemes=("https",), resolve=resolve)


def is_safe_fetch_url(url: str, *, schemes: tuple[str, ...] = ("http", "https"), resolve: bool = False) -> bool:
    if not url or len(url) > MAX_URL or CONTROL_RE.search(url):
        return False
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False
    if parsed.scheme not in schemes or parsed.username or parsed.password:
        return False
    if parsed.path and "\\" in parsed.path:
        return False
    host = _hostname(url)
    if not host or host_is_blocked(host):
        return False
    try:
        if not ip_is_public(ipaddress.ip_address(host)):
            return False
    except ValueError:
        if resolve and not resolve_public_ips(host):
            return False
    return True


def resolve_public_ips(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return []
    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        addr = info[4][0]
        if "%" in addr:
            addr = addr.split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return []
        if not ip_is_public(ip):
            return []
        ips.append(ip)
    return ips


class SafeFetchRedirectHandler(urllib.request.HTTPRedirectHandler):
    max_redirections = MAX_REDIRECTS
    schemes = ("http", "https")

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not is_safe_fetch_url(newurl, schemes=self.schemes, resolve=True):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class SafeHTTPSRedirectHandler(SafeFetchRedirectHandler):
    schemes = ("https",)


def opener_for(*, insecure: bool = False, https_only: bool = False):
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    https = urllib.request.HTTPSHandler(context=ctx)
    handler = SafeHTTPSRedirectHandler if https_only else SafeFetchRedirectHandler
    return urllib.request.build_opener(https, handler)


def probe_https(url: str) -> str:
    if not is_safe_https_url(url, resolve=True):
        return "dead"
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*", "Range": "bytes=0-2047"}
    req = urllib.request.Request(url, headers=headers, method="GET")
    opener = opener_for(https_only=True)
    try:
        with opener.open(req, timeout=PROBE_TIMEOUT) as resp:
            status = getattr(resp, "status", 200) or 200
            final = resp.geturl()
            chunk = resp.read(READ_BYTES)
    except urllib.error.HTTPError as err:
        err_url = getattr(err, "url", "") or getattr(err, "filename", "") or url
        if not is_safe_https_url(str(err_url), resolve=True):
            return "dead"
        status = err.code
        try:
            chunk = err.read(READ_BYTES)
        except Exception:
            chunk = b""
        if status in {404, 410, 451}:
            return "dead"
        if status in {401, 403, 407, 429, 457} or status >= 500:
            return "unknown"
        final = str(err_url)
    except Exception:
        return "unknown"
    if final and not is_safe_https_url(final, resolve=True):
        return "dead"
    body = chunk.lstrip().lower()
    if body.startswith((b"<!doctype", b"<html", b"<head")):
        return "dead"
    if status in {200, 206}:
        return "ok"
    if 300 <= status < 400:
        return "dead"
    if status in {404, 410, 451}:
        return "dead"
    return "unknown"
