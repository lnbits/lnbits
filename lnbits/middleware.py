from http import HTTPStatus
from typing import List, Tuple

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from lnbits.settings import settings


class InstalledExtensionMiddleware:
    # This middleware class intercepts calls made to the extensions API and:
    #  - it blocks the calls if the extension has been disabled or uninstalled.
    #  - it redirects the calls to the latest version of the extension if the extension has been upgraded.
    #  - otherwise it has no effect
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if "path" not in scope:
            await self.app(scope, receive, send)
            return

        path_elements = scope["path"].split("/")
        if len(path_elements) > 2:
            _, path_name, path_type, *rest = path_elements
        else:
            _, path_name = path_elements
            path_type = None
            rest = []

        # block path for all users if the extension is disabled
        if path_name in settings.lnbits_deactivated_extensions:
            response = JSONResponse(
                status_code=HTTPStatus.NOT_FOUND,
                content={"detail": f"Extension '{path_name}' disabled"},
            )
            await response(scope, receive, send)
            return

        # re-route API trafic if the extension has been upgraded
        if path_type == "api":
            upgraded_extensions = list(
                filter(
                    lambda ext: ext.endswith(f"/{path_name}"),
                    settings.lnbits_upgraded_extensions,
                )
            )
            if len(upgraded_extensions) != 0:
                upgrade_path = upgraded_extensions[0]
                tail = "/".join(rest)
                scope["path"] = f"/upgrades/{upgrade_path}/{path_type}/{tail}"

        await self.app(scope, receive, send)


class ExtensionsRedirectMiddleware:
    # Extensions are allowed to specify redirect paths.
    # A call to a path outside the scope of the extension can be redirected to one of the extension's endpoints.
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
            e for e in ([redirect["ext_id"]] + redirect_to + req_tail_path) if e != ""
        ]

        return "/" + "/".join(elements)
