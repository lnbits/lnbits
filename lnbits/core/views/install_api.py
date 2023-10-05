import json
import os
import subprocess
from http import HTTPStatus
from pathlib import Path
from typing import List, Optional

import httpx
from fastapi import APIRouter
from loguru import logger
from packaging import version
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
    try:
        conf = await fetch_nix_packages_config()
        print("### packages_config", conf)
        packages = []
        if "packages" in conf:
            packages += conf["packages"]
        if "support_packages" in conf:
            packages += conf["support_packages"]
        print("### packages", packages)
        os_nix_packages = get_os_nix_packges()
        print("### os_nix_packages", os_nix_packages)
        for package in packages:
            try:
                installed_package = next(
                    (p for p in os_nix_packages if p[0] == package["id"]), None
                )
                package["version"] = installed_package[1]
                package["installed"] = True
            except Exception as e:
                logger.debug(e)

        print("### packages", packages)
        return conf

    except Exception as e:
        logger.warning(e)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=("Failed to get installable packages config"),
        )


@install_router.get("/admin/api/v1/installed")
async def get_installed():
    return "extension_releases"


@install_router.get("/admin/api/v1/config/{packageId}")
async def get_nix_config(packageId: str):
    try:
        conf = await fetch_nix_packages_config()
        packages = []
        if "packages" in conf:
            packages += conf["packages"]
        if "support_packages" in conf:
            packages += conf["support_packages"]

        package = next((p for p in packages if p["id"] == packageId), None)
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


@install_router.get("/admin/api/v1/config")
async def get_nix_config_file():
    file_contents = ""
    with open("lnbits/core/static/nix/config.nix", "r") as file:
        file_contents = file.read()
    return file_contents


@install_router.put("/admin/api/v1/config/{packageId}")
async def get_nix_update_config(packageId: str, data: SaveConfig):
    try:
        path = (
            subprocess.check_output(
                ["echo", "$PATH"],
                stderr=subprocess.DEVNULL,
            )
            .strip()
            .decode("ascii")
        )
        print("### path", path)

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


async def fetch_nix_packages_config():
    # todo: use env var for this
    pachages_config_url = (
        "https://raw.githubusercontent.com/lnbits/nix-lnbits/main/nix-packages.json"
    )
    async with httpx.AsyncClient() as client:
        r = await client.get(pachages_config_url, timeout=15)
        r.raise_for_status()
    return json.loads(r.text)


def get_os_nix_packges():
    path = os.environ["PATH"]
    nix_packages = []
    for path in path.split(os.pathsep):
        p = [p for p in path.split(os.path.sep) if p != ""]
        if len(p) >= 3 and p[0] == "nix" and p[1] == "store":
            name_parts = []
            version_parts = []
            for x in p[2].split("-")[1:]:
                try:
                    version.parse(x)
                    version_parts.append(x)
                except Exception as _:
                    name_parts.append(x)

            nix_packages.append(("-".join(name_parts), "-".join(version_parts)))
    return nix_packages
