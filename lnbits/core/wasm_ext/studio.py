from __future__ import annotations

import asyncio
import re
import shutil
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from lnbits.core.crud.extensions import (
    create_user_extension,
    get_installed_extension,
    get_user_extension,
)
from lnbits.core.db import core_app_extra
from lnbits.core.models.extensions import UserExtension
from lnbits.core.models.users import Account
from lnbits.core.services.extensions import resolve_wasm_runtime_limits
from lnbits.core.services.scheduler import scheduler
from lnbits.decorators import check_admin
from lnbits.helpers import sha256s
from lnbits.settings import settings

from .routes.api import register_wasm_extension_api_routes
from .routes.assets import mount_wasm_extension_static
from .routes.ui import register_wasm_extension_ui_routes
from .runtime import StudioExtension, WasmStudioContext
from .storage.crud import migrate_wasm_extension_database
from .wasm.component import warm_wasm_extension
from .wasm.loader import WasmExtension, load_wasm_extension
from .wasm.scheduler import (
    ensure_wasm_extension_schedules,
    register_wasm_schedule_handlers,
)

_workspace_locks: dict[str, asyncio.Lock] = {}


async def open_wasm_studio(
    app: FastAPI, ext_id: str, account: Account
) -> WasmExtension:
    await check_admin(account)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", ext_id):
        raise HTTPException(400, "Invalid extension ID.")
    draft_id = f"{ext_id}_{sha256s(account.id)}"
    async with _workspace_locks.setdefault(draft_id, asyncio.Lock()):
        existing = core_app_extra.wasm_extension_registry.get(draft_id)
        if existing:
            if not existing.studio or existing.studio.user_id != account.id:
                raise HTTPException(409, "Draft extension ID is already in use.")
            return existing
        if await get_installed_extension(draft_id):
            raise HTTPException(409, "Draft extension ID is already in use.")
        source = await get_installed_extension(ext_id)
        if not source or not source.is_wasm:
            raise HTTPException(404, "Installed WASM extension not found.")

        workspace = await asyncio.to_thread(_prepare_workspace, ext_id, account.id)
        extension = await asyncio.to_thread(
            load_wasm_extension, ext_id, root_path=workspace / "ext"
        )
        draft_info = StudioExtension(
            **{**source.dict(), "id": draft_id, "active": True},
            workspace_path=workspace,
        )
        studio = WasmStudioContext(ext_id, account.id, draft_info)
        extension = _draft_extension(extension, studio)
        await asyncio.to_thread(
            warm_wasm_extension, extension, resolve_wasm_runtime_limits(draft_info)
        )
        registry = core_app_extra.wasm_extension_registry
        registry.register(extension)
        try:
            await migrate_wasm_extension_database(draft_info)
            if not await get_user_extension(account.id, draft_id):
                await create_user_extension(
                    UserExtension(user=account.id, extension=draft_id, active=True)
                )
            register_wasm_schedule_handlers(extension)
            await ensure_wasm_extension_schedules(draft_id)
            mount_wasm_extension_static(app, extension)
            register_wasm_extension_ui_routes(app, extension)
            register_wasm_extension_api_routes(app, extension)
        except BaseException:
            registry.unregister(draft_id)
            scheduler.unregister(f"extension:{draft_id}")
            app.router.routes[:] = [
                route
                for route in app.router.routes
                if not str(getattr(route, "name", "")).startswith(
                    (f"{draft_id}:", f"{draft_id}-")
                )
            ]
            app.openapi_schema = None
            raise
        return extension


def _prepare_workspace(ext_id: str, user_id: str) -> Path:
    root = Path(settings.lnbits_data_folder).resolve() / "wasm_studio"
    workspace = root / sha256s(user_id) / ext_id
    for path in (
        root,
        workspace.parent,
        workspace,
        workspace / "data",
        workspace / "ext",
    ):
        if path.is_symlink():
            raise ValueError("Studio workspace must not contain symbolic links.")
    (workspace / "data").mkdir(parents=True, exist_ok=True)
    target = workspace / "ext"
    if target.exists():
        if not target.is_dir():
            raise ValueError("Invalid studio extension directory.")
        _reject_symlinks(target)
        return workspace

    source = settings.wasm_extensions_dir / ext_id
    _reject_symlinks(source)
    temporary = workspace / f".ext-{uuid4().hex}"
    try:
        shutil.copytree(source, temporary)
        temporary.rename(target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return workspace


def _reject_symlinks(root: Path) -> None:
    if root.is_symlink() or any(path.is_symlink() for path in root.rglob("*")):
        raise ValueError("Studio extension must not contain symbolic links.")


def _draft_extension(
    extension: WasmExtension, studio: WasmStudioContext
) -> WasmExtension:
    config = extension.config.copy(deep=True)
    config.id = studio.extension.id
    for route in config.ui_routes:
        prefix = f"/{studio.source_id}"
        if route.path != prefix and not route.path.startswith(prefix + "/"):
            raise ValueError("Studio UI routes must stay inside the extension path.")
        route.path = f"/{config.id}" + route.path[len(prefix) :]
    return replace(extension, id=config.id, config=config, studio=studio)
