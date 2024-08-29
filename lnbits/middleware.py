from http import HTTPStatus
from typing import Any, List, Tuple, Union

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

        upgrade_path = next(
            (
                e
                for e in settings.lnbits_upgraded_extensions
                if e.endswith(f"/{top_path}")
            ),
            None,
        )
        # re-route all trafic if the extension has been upgraded
        if upgrade_path:
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
        redirect = self._find_redirect(scope["path"], req_headers)
        if redirect:
            scope["path"] = self._new_path(redirect, scope["path"])

        await self.app(scope, receive, send)

    def _find_redirect(self, path: str, req_headers: List[Tuple[bytes, bytes]]):
        return next(
            (
                r
                for r in settings.lnbits_extensions_redirects
                if self._redirect_matches(r, path, req_headers)
            ),
            None,
        )

    def _redirect_matches(
        self, redirect: dict, path: str, req_headers: List[Tuple[bytes, bytes]]
    ) -> bool:
        if "from_path" not in redirect:
            return False
        header_filters = (
            redirect["header_filters"] if "header_filters" in redirect else {}
        )
        return self._has_common_path(redirect["from_path"], path) and self._has_headers(
            header_filters, req_headers
        )

    def _has_headers(
        self, filter_headers: dict, req_headers: List[Tuple[bytes, bytes]]
    ) -> bool:
        for h in filter_headers:
            if not self._has_header(req_headers, (str(h), str(filter_headers[h]))):
                return False
        return True

    def _has_header(
        self, req_headers: List[Tuple[bytes, bytes]], header: Tuple[str, str]
    ) -> bool:
        for h in req_headers:
            if (
                h[0].decode().lower() == header[0].lower()
                and h[1].decode() == header[1]
            ):
                return True
        return False

    def _has_common_path(self, redirect_path: str, req_path: str) -> bool:
        redirect_path_elements = redirect_path.split("/")
        req_path_elements = req_path.split("/")
        if len(redirect_path) > len(req_path):
            return False
        sub_path = req_path_elements[: len(redirect_path_elements)]
        return redirect_path == "/".join(sub_path)

    def _new_path(self, redirect: dict, req_path: str) -> str:
        from_path = redirect["from_path"].split("/")
        redirect_to = redirect["redirect_to_path"].split("/")
        req_tail_path = req_path.split("/")[len(from_path) :]

        elements = [
            e for e in ([redirect["ext_id"], *redirect_to, *req_tail_path]) if e != ""
        ]

        return "/" + "/".join(elements)


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
