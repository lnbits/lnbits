from __future__ import annotations

import re

_EXTENSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_LOCAL_ITEM_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_-]{0,127}$")


def scoped_websocket_item_id(extension_id: str, item_id: str) -> str:
    if not _EXTENSION_ID_RE.fullmatch(extension_id):
        raise ValueError("Extension websocket namespace is invalid.")
    if not _LOCAL_ITEM_ID_RE.fullmatch(item_id):
        raise ValueError(
            "Extension websocket item ID must be 1-128 characters and contain "
            "only letters, numbers, colon, underscore, or dash."
        )
    return f"ext:{extension_id}:{item_id}"
