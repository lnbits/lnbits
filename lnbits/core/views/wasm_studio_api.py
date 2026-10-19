import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from lnbits.core.models.users import Account
from lnbits.core.wasm_ext.studio_service import (
    build_studio,
    deploy_studio,
    initialize_studio,
    model_identifier,
    public_state,
    read_state,
    require_current_admin,
    review_studio,
    run_chat,
    start_studio_operation,
    studio_lock,
    studio_workspace,
    undo_studio,
)
from lnbits.decorators import check_admin
from lnbits.settings import settings


async def studio_response_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


studio_router = APIRouter(
    prefix="/studio",
    tags=["WASM Extension Studio"],
    dependencies=[Depends(studio_response_headers)],
)


class StudioOpen(BaseModel):
    new: bool = False
    name: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=1000)


class StudioPrompt(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=16000)
    model: str = Field(..., min_length=64, max_length=64)


class StudioApproval(BaseModel):
    digest: str = Field(..., regex=r"^[a-f0-9]{64}$")
    build_id: str = Field(default="", regex=r"^([a-f0-9]{32})?$")
    approved: bool = False


class StudioUndo(BaseModel):
    checkpoint: str = Field(..., regex=r"^[a-f0-9]{32}$")


@studio_router.get("/models/configured")
async def studio_models(account: Account = Depends(check_admin)) -> list[dict]:
    return [
        {
            "id": model_identifier(model),
            "name": (
                model.name
                + (" (OAuth required)" if model.provider == "openai-codex" else "")
            ),
            "provider": model.provider,
            "model": model.model,
            "disable": model.provider == "openai-codex",
        }
        for model in settings.lnbits_wasm_studio_models
    ]


@studio_router.post("/{ext_id}")
async def studio_open(
    ext_id: str,
    data: StudioOpen,
    request: Request,
    account: Account = Depends(check_admin),
) -> dict:
    if data.new and not data.name.strip():
        raise HTTPException(400, "Enter an extension name.")
    workspace = studio_workspace(ext_id, account.id)
    try:
        return await initialize_studio(request.app, ext_id, account, data.dict())
    except HTTPException as exc:
        if exc.status_code == 409 and (workspace / "data/state.json").exists():
            return public_state(workspace, ext_id, account.id)
        raise
    except (ValueError, OSError, KeyError) as exc:
        raise HTTPException(
            400,
            "Studio requires compatible Python source in src/app.py and a valid WASM"
            " manifest. Links and oversized drafts are rejected.",
        ) from exc


@studio_router.get("/{ext_id}")
async def studio_state(ext_id: str, account: Account = Depends(check_admin)) -> dict:
    return await asyncio.to_thread(
        public_state, studio_workspace(ext_id, account.id), ext_id, account.id
    )


@studio_router.get("/{ext_id}/events")
async def studio_events(
    ext_id: str, request: Request, account: Account = Depends(check_admin)
):
    workspace = studio_workspace(ext_id, account.id)
    read_state(workspace)

    async def events():
        revision = -1
        while not await request.is_disconnected():
            try:
                await require_current_admin(account.id)
            except HTTPException:
                return
            state = await asyncio.to_thread(public_state, workspace, ext_id, account.id)
            if state["revision"] != revision:
                revision = state["revision"]
                yield "data: " + json.dumps(state) + "\n\n"
            else:
                yield ": keepalive\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@studio_router.post("/{ext_id}/chat", status_code=202)
async def studio_chat(
    ext_id: str, data: StudioPrompt, account: Account = Depends(check_admin)
) -> dict:
    workspace = studio_workspace(ext_id, account.id)
    if any(
        model_identifier(model) == data.model and model.provider == "openai-codex"
        for model in settings.lnbits_wasm_studio_models
    ):
        raise HTTPException(
            400,
            "OpenAI Codex requires OAuth. Select an API-key provider such as OpenAI.",
        )
    if not data.prompt.strip() or not any(
        model_identifier(model) == data.model
        for model in settings.lnbits_wasm_studio_models
    ):
        raise HTTPException(400, "Enter a prompt and select a configured model.")
    return await start_studio_operation(
        workspace,
        "chat",
        lambda state: run_chat(workspace, account, state, data.prompt, data.model),
    )


@studio_router.post("/{ext_id}/stop")
async def studio_stop(ext_id: str, account: Account = Depends(check_admin)) -> dict:
    workspace = studio_workspace(ext_id, account.id)
    read_state(workspace)
    (workspace / "data/stop").touch(mode=0o600)
    return {"stopping": True}


@studio_router.get("/{ext_id}/review")
async def studio_review(
    ext_id: str, built: bool = False, account: Account = Depends(check_admin)
) -> dict:
    workspace = studio_workspace(ext_id, account.id)
    with studio_lock(workspace):
        try:
            return await review_studio(workspace, ext_id, built=built)
        except (ValueError, KeyError, OSError) as exc:
            raise HTTPException(
                400,
                "Invalid draft. Check config.json and the required Python/WIT source"
                " paths.",
            ) from exc


@studio_router.post("/{ext_id}/build", status_code=202)
async def studio_build(
    ext_id: str,
    data: StudioApproval,
    request: Request,
    account: Account = Depends(check_admin),
) -> dict:
    if not data.approved:
        raise HTTPException(
            400, "Approve the preview permissions, limits and schema first."
        )
    workspace = studio_workspace(ext_id, account.id)
    return await start_studio_operation(
        workspace,
        "build",
        lambda state: build_studio(
            request.app, workspace, ext_id, account, state, data.digest
        ),
    )


@studio_router.post("/{ext_id}/undo", status_code=202)
async def studio_undo(
    ext_id: str, data: StudioUndo, account: Account = Depends(check_admin)
) -> dict:
    workspace = studio_workspace(ext_id, account.id)
    return await start_studio_operation(
        workspace, "undo", lambda state: undo_studio(workspace, state, data.checkpoint)
    )


@studio_router.post("/{ext_id}/deploy", status_code=202)
async def studio_deploy(
    ext_id: str,
    data: StudioApproval,
    request: Request,
    account: Account = Depends(check_admin),
) -> dict:
    if not data.approved or not data.build_id:
        raise HTTPException(400, "Review and approve a successful build first.")
    workspace = studio_workspace(ext_id, account.id)
    return await start_studio_operation(
        workspace,
        "deploy",
        lambda state: deploy_studio(
            request.app, workspace, ext_id, account, state, data.build_id, data.digest
        ),
    )
