import json
import re
from http import HTTPStatus
from pathlib import Path
from typing import Any, List, Optional

import httpx
from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from lnbits.settings import settings

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


class SaveConfig(BaseModel):
    config: str


class Manifest(BaseModel):
    featured: List[str] = []
    extensions: List["PackageRelease"] = []


@install_router.get("/admin/api/v1/apps")
async def get_installable_packages():
    ####### LATER FOR BEING FANCY AND PULLING FROM THE NIX REPO #########
    # url = "https://raw.githubusercontent.com/fort-nix/nix-bitcoin/master/modules/modules.nix"
    # error_msg = "Cannot fetch extensions manifest"
    # manifest = await github_api_get(url, error_msg)
    # return manifest
    file_contents = ""
    with open("lnbits/core/static/nix/nix.json", "r") as json_file:
        file_contents = json.load(json_file)
    return file_contents


@install_router.get("/admin/api/v1/installed")
async def get_installed():
    return "extension_releases"


@install_router.get("/admin/api/v1/config/{packageId}")
async def get_nix_config(packageId: str):
    try:
        packages_conf = None
        with open("lnbits/core/static/nix/nix.json", "r") as file:
            packages_conf = file.read()
        assert packages_conf, "Cannot find NIX packages config file."
        conf = json.loads(packages_conf)
        assert "packages" in conf, "NIX packages config has no packages"

        package = next((p for p in conf["packages"] if p["id"] == packageId), None)
        assert package, f"Package '{packageId}' could not be found"
        assert "repo" in package, f"Package '{package}' has no repo filed"

        async with httpx.AsyncClient(follow_redirects=True) as client:
            r = await client.get(package["repo"], timeout=5)
            r.raise_for_status()

        package_data_file = Path(
            settings.lnbits_data_folder, "nix", "config", f"{packageId}.json"
        )

        package_data = None
        if package_data_file.exists():
            with open(package_data_file, "r") as file:
                text = file.read()
                package_data = json.loads(text)

        return {"config": r.text, "data": package_data}

    except Exception as e:
        logger.warning(e)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=(f"Failed to get package '{packageId}' config"),
        )


@install_router.put("/admin/api/v1/config/{packageId}")
async def get_nix_update_config(packageId: str, data: SaveConfig):
    try:
        nix_config_dir = Path(settings.lnbits_data_folder, "nix", "config")
        nix_config_dir.mkdir(parents=True, exist_ok=True)
        package_data_file = Path(nix_config_dir, f"{packageId}.json")
        with open(package_data_file, "w") as file:
            file.write(data.config)
    except Exception as e:
        logger.warning(e)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=(f"Failed to get package '{packageId}' config"),
        )


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
        imports_match = re.search(r"imports\s*=\s*\[([\s\S]*?)\];", resp.text)
        if imports_match:
            imports_text = imports_match.group(1)
            imports_list = re.findall(r"\./[\w/.-]+", imports_text)
            for x, imp in enumerate(imports_list):
                imports_list[x] = re.sub(r"\./|\.nix", "", imp)
        return imports_list
