from importlib.util import find_spec
from pathlib import Path

from fastapi import APIRouter, HTTPException
from starlette.responses import FileResponse

onchain_router = APIRouter(prefix="/onchain", tags=["Onchain"])


def require_onchain_available() -> None:
    if find_spec("wallycore") is None:
        raise HTTPException(503, "Onchain support requires the wallycore package")


@onchain_router.get("/static/{path:path}", include_in_schema=False)
async def static_asset(path: str):
    root = Path(__file__).parent / "static"
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise HTTPException(404)
    return FileResponse(target)


if find_spec("wallycore") is not None:
    from .hot_wallet_api import hot_wallet_router
    from .sync import sync_router
    from .views_api import onchain_api_router

    onchain_router.include_router(onchain_api_router)
    onchain_router.include_router(hot_wallet_router)
    onchain_router.include_router(sync_router)
