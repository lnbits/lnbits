from typing import Optional, List
from urllib.request import parse_http_list as _parse_list_header

from quart import request


class ProxyFix:
    def __init__(self, app=None, x_for: int = 1, x_proto: int = 1, x_host: int = 0, x_port: int = 0, x_prefix: int = 0):
        self.app = app
        self.x_for = x_for
        self.x_proto = x_proto
        self.x_host = x_host
        self.x_port = x_port
        self.x_prefix = x_prefix

        if app:
            self.init_app(app)

    def init_app(self, app):
        @app.before_request
        async def before_request():
            x_for = self._get_real_value(self.x_for, request.headers.get("X-Forwarded-For"))
            if x_for:
                request.headers["Remote-Addr"] = x_for

            x_proto = self._get_real_value(self.x_proto, request.headers.get("X-Forwarded-Proto"))
            if x_proto:
                request.scheme = x_proto

            x_host = self._get_real_value(self.x_host, request.headers.get("X-Forwarded-Host"))
            if x_host:
                request.headers["host"] = x_host.lower()
                parts = x_host.split(":", 1)
                # environ["SERVER_NAME"] = parts[0]
                # if len(parts) == 2:
                #     environ["SERVER_PORT"] = parts[1]

            x_port = self._get_real_value(self.x_port, request.headers.get("X-Forwarded-Port"))
            if x_port:
                host = request.host
                if host:
                    parts = host.split(":", 1)
                    host = parts[0] if len(parts) == 2 else host
                    request.headers["host"] = f"{host}:{x_port}"
                # environ["SERVER_PORT"] = x_port

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


#                host,             request.root_path,             subdomain,             request.scheme,             request.method,             request.path,             request.query_string.decode(),
