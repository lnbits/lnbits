from __future__ import annotations

import json
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from lnbits.core.crud.users import get_account
from lnbits.core.models.scheduler import ScheduleConfig
from lnbits.core.services.scheduler import (
    SCHEDULER_EXTENSION_PERMISSION,
    SCHEDULER_USER_PERMISSION,
    scheduler,
)

from .registry import extension_api_method

if TYPE_CHECKING:
    from .host import ExtensionHostAPI


class ScheduleScopeRequest(BaseModel):
    scope: Literal["user", "extension"] = "user"

    class Config:
        extra = "forbid"


class ScheduleSetRequest(ScheduleConfig):
    scope: Literal["user", "extension"] = "user"


class ScheduleListRequest(ScheduleScopeRequest):
    limit: int = Field(default=100, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ScheduleDeleteRequest(ScheduleScopeRequest):
    id: str = Field(..., min_length=1, max_length=128)


class ScheduleResponse(BaseModel):
    schedule_json: str


class ScheduleListResponse(BaseModel):
    schedules_json: str


class ScheduleDeleteResponse(BaseModel):
    deleted: bool


class ExtensionSchedulerAPI:
    def __init__(self, api: ExtensionHostAPI):
        self.api = api

    async def _owner(self, scope: str) -> str | None:
        # A scheduled callback must not impersonate an interactive user, even if
        # it has that user's storage/notification context.
        if self.api.context != "user" or not self.api.user_id:
            raise PermissionError(
                "Managing schedules requires an authenticated request."
            )
        account = await get_account(self.api.user_id)
        if not account or not account.activated:
            raise PermissionError("Schedule owner is not active.")
        if scope == "extension":
            if not account.is_admin:
                raise PermissionError(
                    "Extension-wide schedules require an administrator."
                )
            return None
        return self.api.user_id

    @extension_api_method(
        method_id="scheduler.set",
        namespace="scheduler",
        name="Save schedule",
        host_interface="scheduler",
        host_name="set_schedule",
        sdk_name="set",
        description=(
            "Create or update a five-field cron job. "
            "User scope requires scheduler.user; "
            "extension scope requires scheduler.extension and an administrator. "
            "The handler must be an event export."
        ),
    )
    async def set(self, request: ScheduleSetRequest) -> ScheduleResponse:
        owner = await self._owner(request.scope)
        self.api.require_permission(
            SCHEDULER_USER_PERMISSION if owner else SCHEDULER_EXTENSION_PERMISSION
        )
        job = await scheduler.save(
            f"extension:{self.api.extension_id}",
            ScheduleConfig.parse_obj(request.dict(exclude={"scope"})),
            user_id=owner,
        )
        return ScheduleResponse(schedule_json=json.dumps(job.public_data()))

    @extension_api_method(
        method_id="scheduler.list",
        namespace="scheduler",
        name="List schedules",
        host_interface="scheduler",
        host_name="list_schedules",
        sdk_name="list",
        description="List user-owned jobs, or shared jobs for an administrator.",
    )
    async def list(self, request: ScheduleListRequest) -> ScheduleListResponse:
        owner = await self._owner(request.scope)
        jobs = await scheduler.list(
            f"extension:{self.api.extension_id}",
            user_id=owner,
            limit=request.limit,
            offset=request.offset,
        )
        return ScheduleListResponse(
            schedules_json=json.dumps([j.public_data() for j in jobs])
        )

    @extension_api_method(
        method_id="scheduler.delete",
        namespace="scheduler",
        name="Delete schedule",
        host_interface="scheduler",
        host_name="delete_schedule",
        sdk_name="delete",
        description="Delete an owned, idle schedule. Pause running jobs first.",
    )
    async def delete(self, request: ScheduleDeleteRequest) -> ScheduleDeleteResponse:
        owner = await self._owner(request.scope)
        deleted = await scheduler.delete(
            f"extension:{self.api.extension_id}", request.id, user_id=owner
        )
        return ScheduleDeleteResponse(deleted=deleted)
