from http import HTTPStatus
from typing import Any, List, Union

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from lnbits.core.db import core_app_extra
from lnbits.helpers import template_renderer
from lnbits.settings import settings


class InstalledExtensionMiddleware:
    # This middleware class intercepts calls made to the extensions API and:
    #  - it blocks the calls if the extension has been disabled or uninstalled.
    #  - it redirects the calls to the latest version of the extension
    #    if the extension has been upgraded.
    #  - otherwise it has no effect
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        full_path = scope.get("path", "/")
        if full_path == "/":
            await self.app(scope, receive, send)
            return

        top_path, *rest = (p for p in full_path.split("/") if p)
        headers = scope.get("headers", [])

        # block path for all users if the extension is disabled
        if top_path in settings.lnbits_deactivated_extensions:
            response = self._response_by_accepted_type(
                scope, headers, f"Extension '{top_path}' disabled", HTTPStatus.NOT_FOUND
            )
            await response(scope, receive, send)
            return

        # static resources do not require redirect
        if rest[0:1] == ["static"]:
            await self.app(scope, receive, send)
            return

        # re-route all trafic if the extension has been upgraded
        if top_path in settings.lnbits_upgraded_extensions:
            upgrade_path = (
                f"""{settings.lnbits_upgraded_extensions[top_path]}/{top_path}"""
            )
            tail = "/".join(rest)
            scope["path"] = f"/upgrades/{upgrade_path}/{tail}"

        await self.app(scope, receive, send)

    def _response_by_accepted_type(
        self, scope: Scope, headers: List[Any], msg: str, status_code: HTTPStatus
    ) -> Union[HTMLResponse, JSONResponse]:
        """
        Build an HTTP response containing the `msg` as HTTP body and the `status_code`
        as HTTP code. If the `accept` HTTP header is present int the request and
        contains the value of `text/html` then return an `HTMLResponse`,
        otherwise return an `JSONResponse`.
        """
        accept_header: str = next(
            (
                h[1].decode("UTF-8")
                for h in headers
                if len(h) >= 2 and h[0].decode("UTF-8") == "accept"
            ),
            "",
        )

        if "text/html" in accept_header.split(","):
            return HTMLResponse(
                status_code=status_code,
                content=template_renderer()
                .TemplateResponse(Request(scope), "error.html", {"err": msg})
                .body,
            )

        return JSONResponse(
            status_code=status_code,
            content={"detail": msg},
        )


class CustomGZipMiddleware(GZipMiddleware):
    def __init__(self, *args, exclude_paths=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.exclude_paths = exclude_paths or []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if "path" in scope and scope["path"] in self.exclude_paths:
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)


class ExtensionsRedirectMiddleware:
    # Extensions are allowed to specify redirect paths. A call to a path outside the
    # scope of the extension can be redirected to one of the extension's endpoints.
    # Eg: redirect `GET /.well-known` to `GET /lnurlp/api/v1/well-known`

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if "path" not in scope:
            await self.app(scope, receive, send)
            return

        req_headers = scope["headers"] if "headers" in scope else []
        redirect = settings.find_extension_redirect(scope["path"], req_headers)
        if redirect:
            scope["path"] = redirect.new_path_from(scope["path"])

        await self.app(scope, receive, send)


def add_ratelimit_middleware(app: FastAPI):
    core_app_extra.register_new_ratelimiter()
    # latest https://slowapi.readthedocs.io/en/latest/
    # shows this as a valid way to add the handler
    app.add_exception_handler(
        RateLimitExceeded,
        _rate_limit_exceeded_handler,  # type: ignore
    )
    app.add_middleware(SlowAPIMiddleware)


def add_ip_block_middleware(app: FastAPI):
    @app.middleware("http")
    async def block_allow_ip_middleware(request: Request, call_next):
        if not request.client:
            return JSONResponse(
                status_code=403,  # Forbidden
                content={"detail": "No request client"},
            )
        if (
            request.client.host in settings.lnbits_blocked_ips
            and request.client.host not in settings.lnbits_allowed_ips
        ):
            return JSONResponse(
                status_code=403,  # Forbidden
                content={"detail": "IP is blocked"},
            )
        return await call_next(request)


def add_first_install_middleware(app: FastAPI):
    @app.middleware("http")
    async def first_install_middleware(request: Request, call_next):
        if (
            settings.first_install
            and request.url.path != "/api/v1/auth/first_install"
            and request.url.path != "/first_install"
            and not request.url.path.startswith("/static")
        ):
            return RedirectResponse("/first_install")
        return await call_next(request)
