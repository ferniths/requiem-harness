"""HTTP request tool — authorized outbound HTTP requests with SSRF protection.

By default, requests to private/internal IP ranges are blocked.
Enable `allow_private` in the tool's arguments to override (requires NETWORK permission).
"""

from __future__ import annotations

import ipaddress
import socket
import time
from typing import Any

import httpx

from requiem.security.permissions import PermissionLevel
from requiem.tools.base import Tool, ToolContext, ToolResult, ToolStatus

MAX_RESPONSE_BYTES = 256 * 1024  # 256 KB response limit


def _is_private_url(url: str) -> bool:
    """Check if a URL points to a private/internal network range.

    Returns True for:
    - localhost / 127.0.0.0/8
    - 10.0.0.0/8
    - 172.16.0.0/12
    - 192.168.0.0/16
    - 169.254.0.0/16 (link-local)
    - ::1 / fe80::/10
    - 0.0.0.0
    - metadata service (169.254.169.254)
    """
    try:
        host_part = url.split("://", 1)[1] if "://" in url else url
        host = host_part.split("/")[0].split("?")[0].split(":")[0].lower()

        if host in ("localhost", "0.0.0.0"):
            return True

        try:
            ip = ipaddress.ip_address(host)
            return ip.is_private or ip.is_loopback or ip.is_link_local
        except ValueError:
            # It's a hostname — try to resolve and check
            try:
                addr = socket.getaddrinfo(host, None, socket.AF_INET)[0][4][0]
                return ipaddress.ip_address(addr).is_private
            except (OSError, socket.gaierror):
                return False
    except Exception:
        return False


class HttpRequestTool(Tool):
    name = "http_request"
    description = (
        "Make an authorized HTTP request. Supports GET, POST, PUT, PATCH, DELETE. "
        "Private/internal URLs are blocked by default (SSRF protection)."
    )
    permission_level = PermissionLevel.NETWORK
    timeout_s = 30.0
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Full URL to request."},
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                "default": "GET",
            },
            "headers": {
                "type": "object",
                "description": "Optional request headers.",
            },
            "body": {
                "type": "string",
                "description": "Optional request body (for POST/PUT/PATCH).",
            },
            "timeout_s": {
                "type": "number",
                "description": "Timeout in seconds (default 30, max 120).",
                "default": 30,
            },
            "allow_private": {
                "type": "boolean",
                "description": "Allow requests to private/internal IPs (default false).",
                "default": False,
            },
        },
        "required": ["url"],
    }

    async def execute(self, arguments: dict[str, Any], *, context: ToolContext) -> ToolResult:
        start = time.monotonic()
        url = arguments.get("url", "")
        method = arguments.get("method", "GET").upper()
        headers: dict[str, str] = arguments.get("headers") or {}
        body: str | None = arguments.get("body")
        timeout_s = min(float(arguments.get("timeout_s", self.timeout_s)), 120.0)
        allow_private = arguments.get("allow_private", False)

        if not url:
            return ToolResult(ToolStatus.ERROR, error="URL is required", duration_s=time.monotonic() - start)

        if not allow_private and _is_private_url(url):
            return ToolResult(
                ToolStatus.DENIED,
                error=f"Request to private/internal URL blocked: {url}",
                duration_s=time.monotonic() - start,
            )

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_s)) as client:
                resp = await client.request(
                    method,
                    url,
                    headers=headers,
                    content=body.encode() if body else None,
                )
            content = resp.text
            truncated = False
            if len(content) > MAX_RESPONSE_BYTES:
                content = content[:MAX_RESPONSE_BYTES]
                truncated = True

            return ToolResult(
                ToolStatus.SUCCESS,
                data={
                    "status_code": resp.status_code,
                    "headers": dict(resp.headers),
                    "body": content,
                    "truncated": truncated,
                },
                duration_s=time.monotonic() - start,
            )
        except httpx.ConnectError as e:
            return ToolResult(ToolStatus.ERROR, error=f"Connection failed: {e}", duration_s=time.monotonic() - start)
        except httpx.TimeoutException:
            return ToolResult(ToolStatus.TIMEOUT, error=f"Request timed out after {timeout_s:.0f}s", duration_s=time.monotonic() - start)
        except httpx.HTTPError as e:
            return ToolResult(ToolStatus.ERROR, error=f"HTTP error: {e}", duration_s=time.monotonic() - start)
