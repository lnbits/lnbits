from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from lnbits.core.crud.users import get_account

from ..storage.crud import (
    storage_delete_row,
    storage_get_paginated_rows,
    storage_get_row,
    storage_set_row,
)
from .models import (
    StorageDeleteRequest,
    StorageDeleteResponse,
    StorageGetRequest,
    StorageGetResponse,
    StoragePaginatedRequest,
    StoragePaginatedResponse,
    StorageSetRequest,
    StorageSetResponse,
)
from .registry import extension_api_method

if TYPE_CHECKING:
    from .host import ExtensionHostAPI

# User owners are SHA-256 digests; this namespace cannot collide with a user.
SHARED_STORAGE_OWNER = "extension:shared"


def shared_storage_tables(policies: list[Any] | None) -> set[str]:
    if not policies:
        raise ValueError("Shared storage requires table policies.")
    tables: set[str] = set()
    for policy in policies:
        if not isinstance(policy, dict) or set(policy) != {"table"}:
            raise ValueError("Shared storage policies must specify a table.")
        table = policy["table"]
        if not isinstance(table, str) or not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*", table
        ):
            raise ValueError("Invalid shared storage table.")
        if table in tables:
            raise ValueError("Shared storage policies must have unique tables.")
        tables.add(table)
    return tables


class ExtensionSharedStorageAPI:
    def __init__(self, api: ExtensionHostAPI):
        self.api = api

    async def _authorize(self, table: str, *, write: bool = False) -> None:
        permission = "ext.storage.write_shared" if write else "ext.storage.read_shared"
        try:
            tables = shared_storage_tables(self.api.permission_policies.get(permission))
        except ValueError as exc:
            raise PermissionError("Invalid shared storage policies.") from exc
        if table not in tables:
            raise PermissionError("Shared storage table is not approved.")
        if not write:
            return
        if self.api.context == "schedule" and not self.api.user_id:
            return
        if self.api.context == "user" and self.api.user_id:
            account = await get_account(self.api.user_id)
            if account and account.activated and account.is_admin:
                return
        raise PermissionError(
            "Shared writes require an administrator or a shared schedule."
        )

    @extension_api_method(
        method_id="storage.shared.get",
        namespace="storage.shared",
        name="Read shared storage row",
        host_interface="storage-shared",
        host_name="get",
        sdk_name="get",
        description="Read an approved table in this extension's shared storage.",
        required_permission="ext.storage.read_shared",
    )
    async def get(self, request: StorageGetRequest) -> StorageGetResponse:
        await self._authorize(request.table)
        row = await storage_get_row(
            self.api.extension_id, request.table, request.id, SHARED_STORAGE_OWNER
        )
        return StorageGetResponse(data_json=json.dumps(row) if row else None)

    @extension_api_method(
        method_id="storage.shared.set",
        namespace="storage.shared",
        name="Write shared storage row",
        host_interface="storage-shared",
        host_name="set",
        sdk_name="set",
        description=(
            "Write an approved shared table from an admin request or shared schedule."
        ),
        required_permission="ext.storage.write_shared",
    )
    async def set(self, request: StorageSetRequest) -> StorageSetResponse:
        await self._authorize(request.table, write=True)
        await storage_set_row(
            self.api.extension_id, request.table, request.data, SHARED_STORAGE_OWNER
        )
        return StorageSetResponse()

    @extension_api_method(
        method_id="storage.shared.get_paginated",
        namespace="storage.shared",
        name="List shared storage rows",
        host_interface="storage-shared",
        host_name="get_paginated",
        sdk_name="getPaginated",
        description="Read filtered, sorted pages from an approved shared table.",
        required_permission="ext.storage.read_shared",
    )
    async def get_paginated(
        self, request: StoragePaginatedRequest
    ) -> StoragePaginatedResponse:
        await self._authorize(request.table)
        page = await storage_get_paginated_rows(
            self.api.extension_id,
            request.table,
            request.filters,
            owner_id=SHARED_STORAGE_OWNER,
            search=request.search,
            search_fields=request.search_fields,
            sort_by=request.sort_by,
            descending=request.descending,
            limit=request.limit,
            offset=request.offset,
        )
        return StoragePaginatedResponse(
            rows_json=json.dumps(page["data"]), total=page["total"]
        )

    @extension_api_method(
        method_id="storage.shared.delete",
        namespace="storage.shared",
        name="Delete shared storage row",
        host_interface="storage-shared",
        host_name="delete",
        sdk_name="delete",
        description=(
            "Delete an approved shared row from an admin request or shared schedule."
        ),
        required_permission="ext.storage.write_shared",
    )
    async def delete(self, request: StorageDeleteRequest) -> StorageDeleteResponse:
        await self._authorize(request.table, write=True)
        await storage_delete_row(
            self.api.extension_id, request.table, request.id, SHARED_STORAGE_OWNER
        )
        return StorageDeleteResponse()
