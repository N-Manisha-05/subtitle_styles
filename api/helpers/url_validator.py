"""
URL validation helper — SSRF protection.

All user-supplied URLs (video_url, srt.url, image_overlays[].url,
video_overlay.url, audio.url) must pass through `validate_url()` before
the server attempts to download them.

Blocks:
  - Non-http/https schemes (file://, ftp://, etc.)
  - Loopback addresses (127.x.x.x, ::1)
  - Private RFC-1918 ranges (10.x, 172.16–31.x, 192.168.x)
  - Link-local (169.254.x — AWS/GCP metadata endpoint)
  - Common internal hostnames (localhost, etc.)
"""

import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import HTTPException

BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain"}


def validate_url(url: str, field: str = "url") -> str:

    if not url:
        return url

    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(status_code=400, detail=f"{field}: malformed URL: {url!r}")

    # Must be http or https
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail=f"{field}: URL scheme must be http or https, got '{parsed.scheme}': {url}",
        )

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail=f"{field}: URL has no hostname: {url}")

    # Block known internal hostnames
    if hostname.lower() in BLOCKED_HOSTNAMES:
        raise HTTPException(
            status_code=400,
            detail=f"{field}: internal hostnames are not allowed: {url}",
        )

    # Try interpreting hostname as a literal IP address
    try:
        ip = ipaddress.ip_address(hostname)
        _check_ip(ip, url, field)
    except ValueError:
        # It's a domain name — resolve it and check the resulting IP
        try:
            resolved = socket.getaddrinfo(hostname, None)
            for item in resolved:
                addr = item[4][0]
                try:
                    _check_ip(ipaddress.ip_address(addr), url, field)
                except ValueError:
                    pass  # skip non-parseable addresses
        except socket.gaierror:
            # DNS resolution failed — let the downloader handle this error naturally
            pass

    return url


def _check_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address, url: str, field: str) -> None:
    """Raise HTTPException if the IP is private/internal."""
    if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved:
        raise HTTPException(
            status_code=400,
            detail=f"{field}: private/internal IP addresses are not allowed: {url}",
        )
