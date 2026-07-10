from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def _do_nothing(*_):
    pass


async def _do_nothing_async(_: Any) -> None:
    pass


class CoreAppExtra:
    register_new_ext_routes: Callable = _do_nothing
    register_new_wasm_ext_routes: Callable = _do_nothing
    register_new_ratelimiter: Callable
    dispatch_extension_invoice_paid: Callable[[Any], Awaitable[None]] = (
        _do_nothing_async
    )

    def __init__(self) -> None:
        self.wasm_extension_registry = WasmExtensionRegistry()


class WasmExtensionRegistry:
    def __init__(self) -> None:
        self._extensions: dict[str, Any] = {}

    def register(self, extension: Any) -> None:
        self.require_available(extension)
        self._extensions[extension.id] = extension

    def require_available(self, extension: Any) -> None:
        existing = self._extensions.get(extension.id)
        if existing and not _same_wasm_extension_registration(existing, extension):
            raise ValueError(
                f"WASM extension id '{extension.id}' is already registered."
            )

    def get(self, ext_id: str) -> Any | None:
        return self._extensions.get(ext_id)

    def list(self) -> list[Any]:
        return list(self._extensions.values())


def _same_wasm_extension_registration(left: Any, right: Any) -> bool:
    try:
        return Path(left.root_path).resolve() == Path(right.root_path).resolve()
    except (AttributeError, TypeError):
        return left is right


class ConversionData(BaseModel):
    from_: str = "sat"
    amount: float
    to: str = "usd"


class Callback(BaseModel):
    callback: str


class BalanceDelta(BaseModel):
    lnbits_balance_sats: int
    node_balance_sats: int

    @property
    def delta_sats(self) -> int:
        return int(self.lnbits_balance_sats - self.node_balance_sats)


class SimpleStatus(BaseModel):
    success: bool
    message: str


class SimpleItem(BaseModel):
    id: str
    name: str


class DbVersion(BaseModel):
    db: str
    version: int


class Image(BaseModel):
    filename: str
    directory: str = "library"
