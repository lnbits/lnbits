from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lnbits.core.crud.extensions import get_installed_extension
from lnbits.core.crud.users import get_account
from lnbits.core.db import core_app_extra
from lnbits.core.models.extensions import InstallableExtension


class StudioExtension(InstallableExtension):
    workspace_path: Path

    @property
    def wasm_ext_dir(self) -> Path:
        return self.workspace_path / "ext"

    @property
    def is_wasm(self) -> bool:
        return True


@dataclass(frozen=True)
class WasmStudioContext:
    source_id: str
    user_id: str
    extension: StudioExtension

    @property
    def data_path(self) -> Path:
        return self.extension.workspace_path / "data"


def get_wasm_studio_context(ext_id: str) -> WasmStudioContext | None:
    extension = core_app_extra.wasm_extension_registry.get(ext_id)
    return getattr(extension, "studio", None)


async def get_runtime_extension(ext_id: str) -> InstallableExtension | None:
    """Resolve on-demand drafts without adding them to installed extensions."""
    studio = get_wasm_studio_context(ext_id)
    if studio:
        account = await get_account(studio.user_id)
        if (
            not account
            or not account.activated
            or not account.is_admin
            or not account.has_password
        ):
            return None
        return studio.extension
    return await get_installed_extension(ext_id)
