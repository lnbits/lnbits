import os
import time
from http import HTTPStatus
from shutil import make_archive
from subprocess import Popen
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException

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

admin_router = APIRouter()   

class InstallableExtension(BaseModel):
    id: str
    name: str
    short_description: Optional[str] = None
    icon: Optional[str] = None
    dependencies: List[str] = []
    is_admin_only: bool = False
    stars: int = 0
    featured = False
    latest_release: Optional[ExtensionRelease] = None
    installed_release: Optional[ExtensionRelease] = None
    archive: Optional[str] = None

    @classmethod
    async def get_installable_packages(
        cls,
    ) -> List["InstallableExtension"]:
        extension_list: List[InstallableExtension] = []
        extension_id_list: List[str] = []

        for url in settings.lnbits_extensions_manifests:
            try:
                manifest = await fetch_manifest(url)

                for r in manifest.repos:
                    ext = await InstallableExtension.from_github_release(r)
                    if not ext:
                        continue
                    existing_ext = next(
                        (ee for ee in extension_list if ee.id == r.id), None
                    )
                    if existing_ext:
                        existing_ext.check_latest_version(ext.latest_release)
                        continue

                    ext.featured = ext.id in manifest.featured
                    extension_list += [ext]
                    extension_id_list += [ext.id]

                for e in manifest.extensions:
                    release = ExtensionRelease.from_explicit_release(url, e)
                    existing_ext = next(
                        (ee for ee in extension_list if ee.id == e.id), None
                    )
                    if existing_ext:
                        existing_ext.check_latest_version(release)
                        continue
                    ext = InstallableExtension.from_explicit_release(e)
                    ext.check_latest_version(release)
                    ext.featured = ext.id in manifest.featured
                    extension_list += [ext]
                    extension_id_list += [e.id]
            except Exception as e:
                logger.warning(f"Manifest {url} failed with '{str(e)}'")

        return extension_list

    @classmethod
    async def get_extension_releases(cls, ext_id: str) -> List["ExtensionRelease"]:
        extension_releases: List[ExtensionRelease] = []

        for url in settings.lnbits_extensions_manifests:
            try:
                manifest = await fetch_manifest(url)
                for r in manifest.repos:
                    if r.id == ext_id:
                        repo_releases = await ExtensionRelease.all_releases(
                            r.organisation, r.repository
                        )
                        extension_releases += repo_releases

                for e in manifest.extensions:
                    if e.id == ext_id:
                        extension_releases += [
                            ExtensionRelease.from_explicit_release(url, e)
                        ]

            except Exception as e:
                logger.warning(f"Manifest {url} failed with '{str(e)}'")

        return extension_releases

    @classmethod
    async def get_extension_release(
        cls, ext_id: str, source_repo: str, archive: str
    ) -> Optional["ExtensionRelease"]:
        all_releases: List[
            ExtensionRelease
        ] = await InstallableExtension.get_extension_releases(ext_id)
        selected_release = [
            r
            for r in all_releases
            if r.archive == archive and r.source_repo == source_repo
        ]

        return selected_release[0] if len(selected_release) != 0 else None


class CreateExtension(BaseModel):
    ext_id: str
    archive: str
    source_repo: str


def get_valid_extensions() -> List[Extension]:
    return [
        extension for extension in ExtensionManager().extensions if extension.is_valid
    ]
