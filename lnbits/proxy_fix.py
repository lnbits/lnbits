from functools import partial
from typing import Callable, List, Optional
from urllib.parse import urlparse
from urllib.request import parse_http_list as _parse_list_header

from quart import Request
from quart_trio.asgi import TrioASGIHTTPConnection
from werkzeug.datastructures import Headers


class ASGIProxyFix(TrioASGIHTTPConnection):
    def _create_request_from_scope(self, send: Callable) -> Request:
        headers = Headers()
        headers["Remote-Addr"] = (self.scope.get("client") or ["<local>"])[0]
        for name, value in self.scope["headers"]:
            headers.add(name.decode("latin1").title(), value.decode("latin1"))
        if self.scope["http_version"] < "1.1":
            headers.setdefault("Host", self.app.config["SERVER_NAME"] or "")

        path = self.scope["path"]
        path = path if path[0] == "/" else urlparse(path).path

        x_proto = self._get_real_value(1, headers.get("X-Forwarded-Proto"))
        if x_proto:
            self.scope["scheme"] = x_proto

        x_host = self._get_real_value(1, headers.get("X-Forwarded-Host"))
        if x_host:
            headers["host"] = x_host.lower()

        return self.app.request_class(
            self.scope["method"],
            self.scope["scheme"],
            path,
            self.scope["query_string"],
            headers,
            self.scope.get("root_path", ""),
            self.scope["http_version"],
            max_content_length=self.app.config["MAX_CONTENT_LENGTH"],
            body_timeout=self.app.config["BODY_TIMEOUT"],
            send_push_promise=partial(self._send_push_promise, send),
            scope=self.scope,
        )

    def _get_real_value(self, trusted: int, value: Optional[str]) -> Optional[str]:
        """Get the real value from a list header based on the configured
        number of trusted proxies.
        :param trusted: Number of values to trust in the header.
        :param value: Comma separated list header value to parse.
        :return: The real value, or ``None`` if there are fewer values
            than the number of trusted proxies.
        .. versionchanged:: 1.0
            Renamed from ``_get_trusted_comma``.
        .. versionadded:: 0.15
        """
        if not (trusted and value):
            return None

        values = self.parse_list_header(value)
        if len(values) >= trusted:
            return values[-trusted]

        return None

    def parse_list_header(self, value: str) -> List[str]:
        result = []
        for item in _parse_list_header(value):
            if item[:1] == item[-1:] == '"':
                item = self.unquote_header_value(item[1:-1])
            result.append(item)
        return result

    def unquote_header_value(self, value: str, is_filename: bool = False) -> str:
        r"""Unquotes a header value.  (Reversal of :func:`quote_header_value`).
        This does not use the real unquoting but what browsers are actually
        using for quoting.
        .. versionadded:: 0.5
        :param value: the header value to unquote.
        :param is_filename: The value represents a filename or path.
        """
        if value and value[0] == value[-1] == '"':
            # this is not the real unquoting, but fixing this so that the
            # RFC is met will result in bugs with internet explorer and
            # probably some other browsers as well.  IE for example is
            # uploading files with "C:\foo\bar.txt" as filename
            value = value[1:-1]

            # if this is a filename and the starting characters look like
            # a UNC path, then just return the value without quotes.  Using the
            # replace sequence below on a UNC path has the effect of turning
            # the leading double slash into a single slash and then
            # _fix_ie_filename() doesn't work correctly.  See #458.
            if not is_filename or value[:2] != "\\\\":
                return value.replace("\\\\", "\\").replace('\\"', '"')
        return value
