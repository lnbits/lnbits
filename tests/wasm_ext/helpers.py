from __future__ import annotations

from dataclasses import dataclass
from typing import Any

EXTENSION_ID = "lnbits-wasm-test-extension"
SERVER_HOST = "127.0.0.1"


@dataclass(frozen=True)
class LiveLNbitsServer:
    base_url: str
    auth_cookies: list[dict[str, Any]]
    extension_id: str = EXTENSION_ID
