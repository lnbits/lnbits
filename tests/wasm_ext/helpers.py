from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXTENSION_ID = "lnbits-wasm-test-extension"
REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_HOST = "127.0.0.1"


@dataclass(frozen=True)
class LiveLNbitsServer:
    base_url: str
    auth_cookies: list[dict[str, Any]]
    extension_id: str = EXTENSION_ID
