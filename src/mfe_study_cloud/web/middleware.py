"""Small ASGI middleware for browser trust boundaries and response hardening."""

from __future__ import annotations

from collections.abc import MutableMapping

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from mfe_study_cloud.security import csrf_matches

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class CsrfOriginMiddleware:
    def __init__(self, app: ASGIApp, *, expected_origin: str) -> None:
        self.app = app
        self.expected_origin = expected_origin.rstrip("/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in UNSAFE_METHODS:
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        origin = request.headers.get("origin", "").rstrip("/")
        session = scope.get("session", {})
        expected_token = session.get("csrf") if isinstance(session, MutableMapping) else None
        supplied_token = request.headers.get("x-csrf-token") or request.cookies.get("mfe_csrf")
        if origin != self.expected_origin or not csrf_matches(expected_token, supplied_token):
            response = PlainTextResponse("CSRF validation failed.", status_code=403)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, production: bool) -> None:
        self.app = app
        self.production = production

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["content-security-policy"] = (
                    "default-src 'self'; base-uri 'none'; object-src 'none'; "
                    "frame-ancestors 'none'; form-action 'self'; script-src 'self'; "
                    "style-src 'self'; img-src 'self' data:; connect-src 'self'; "
                    "manifest-src 'self'; worker-src 'self'"
                )
                headers["x-content-type-options"] = "nosniff"
                headers["x-frame-options"] = "DENY"
                headers["referrer-policy"] = "strict-origin-when-cross-origin"
                headers["permissions-policy"] = (
                    "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
                )
                headers["cross-origin-opener-policy"] = "same-origin"
                path = str(scope.get("path", ""))
                if path.startswith("/static/") and path != "/static/offline.html":
                    headers["cache-control"] = "public, max-age=86400"
                else:
                    headers["cache-control"] = "no-store"
                if self.production:
                    headers["strict-transport-security"] = "max-age=31536000; includeSubDomains"
            await send(message)

        await self.app(scope, receive, send_with_headers)
