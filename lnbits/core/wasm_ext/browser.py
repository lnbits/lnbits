"""Browser-only capabilities. These never become server guest host calls."""

import ipaddress
from typing import Any
from urllib.parse import urlsplit

BROWSER_NETWORK_PERMISSIONS = {"ui.network.https", "ui.network.websocket"}
BROWSER_PERMISSIONS = BROWSER_NETWORK_PERMISSIONS | {
    "ui.media.camera",
    "ui.media.microphone",
    "ui.media.screen",
    "ui.media.playback",
}


def browser_policy_origins(permission_id: str, policies: Any) -> set[str]:
    scheme = "https" if permission_id == "ui.network.https" else "wss"
    if not isinstance(policies, list) or not policies or len(policies) > 32:
        raise ValueError("Browser networking requires 1 to 32 explicit origins.")
    origins = set()
    for value in policies:
        if not isinstance(value, str) or len(value) > 512:
            raise ValueError("Browser network policies must be origin strings.")
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        if (
            parsed.scheme != scheme
            or not host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or any(char in value for char in "\\\r\n\t *%")
            or host.endswith((".", ".localhost", ".local", ".internal"))
            or "." not in host
        ):
            raise ValueError("Browser networking requires explicit public origins.")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("Browser networking does not allow private addresses.")
        port = parsed.port
        if port == 0:
            raise ValueError("Browser network ports must be between 1 and 65535.")
        authority = host.encode("idna").decode("ascii").lower()
        if ":" in authority:
            authority = f"[{authority}]"
        if port and port != 443:
            authority += f":{port}"
        origins.add(f"{scheme}://{authority}")
    return origins
