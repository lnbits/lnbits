import os
import time
from http import HTTPStatus
from shutil import make_archive
from subprocess import Popen
from typing import Optional
from urllib.parse import urlparse
from typing import List, Any
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException
from loguru import logger
from pydantic import BaseModel

from lnbits.core.crud import get_wallet
from lnbits.core.models import CreateTopup, User
from lnbits.core.services import (
    get_balance_delta,
    update_cached_settings,
    update_wallet_balance,
)
from lnbits.decorators import check_admin, check_super_user
from lnbits.server import server_restart
from lnbits.settings import AdminSettings, UpdateSettings, settings

from .. import core_app_extra
from ..crud import delete_admin_settings, get_admin_settings, update_admin_settings

install_router = APIRouter()

class PackageRelease(BaseModel):
    name: str
    version: str
    archive: str
    source_repo: str
    is_github_release: bool = False
    hash: Optional[str] = None
    min_lnbits_version: Optional[str] = None
    is_version_compatible: Optional[bool] = True
    html_url: Optional[str] = None
    description: Optional[str] = None
    warning: Optional[str] = None
    repo: Optional[str] = None
    icon: Optional[str] = None

class InstallablePackage(BaseModel):
    id: str
    name: str
    short_description: Optional[str] = None
    icon: Optional[str] = None
    dependencies: List[str] = []
    is_admin_only: bool = False
    stars: int = 0
    featured = False
    latest_release: Optional[PackageRelease] = None
    installed_release: Optional[PackageRelease] = None
    archive: Optional[str] = None

class CreateExtension(BaseModel):
    ext_id: str
    archive: str
    source_repo: str

class Manifest(BaseModel):
    featured: List[str] = []
    extensions: List["PackageRelease"] = []

@install_router.get("/apps")
async def get_installable_packages(
    cls,
    dependencies=[Depends(check_super_user)],
) -> List["InstallablePackage"]:
    return await fetch_nix_apps()

@install_router.get("/config")
async def get_nix_config(cls, ext_id: str,
    dependencies=[Depends(check_super_user)],) -> List["PackageRelease"]:
    extension_releases: List[PackageRelease] = []

    return extension_releases

@install_router.get("/installed")
async def get_installed(
    dependencies=[Depends(check_super_user)],) -> List["PackageRelease"]:
    extension_releases: List[PackageRelease] = []

    return extension_releases

async def fetch_nix_apps() -> Manifest:
    url = "https://raw.githubusercontent.com/fort-nix/nix-bitcoin/master/modules/modules.nix"
    error_msg = "Cannot fetch extensions manifest"
    manifest = await github_api_get(url, error_msg)
    return Manifest.parse_obj(manifest)

async def github_api_get(url: str, error_msg: Optional[str]) -> Any:
    async with httpx.AsyncClient() as client:
        headers = (
            {"Authorization": "Bearer " + settings.lnbits_ext_github_token}
            if settings.lnbits_ext_github_token
            else None
        )
        resp = await client.get(
            url,
            headers=headers,
        )
        if resp.status_code != 200:
            logger.warning(f"{error_msg} ({url}): {resp.text}")
        resp.raise_for_status()
        return resp.json()
