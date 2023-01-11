import hashlib
import json
import os
import shutil
import sys
import urllib.request
import zipfile
from http import HTTPStatus
from typing import List, NamedTuple, Optional

import httpx
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.types import ASGIApp, Receive, Scope, Send

from lnbits.settings import settings


class Extension(NamedTuple):
    code: str
    is_valid: bool
    is_admin_only: bool
    name: Optional[str] = None
    short_description: Optional[str] = None
    tile: Optional[str] = None
    contributors: Optional[List[str]] = None
    hidden: bool = False
    migration_module: Optional[str] = None
    db_name: Optional[str] = None
    hash: Optional[str] = ""

    @property
    def module_name(self):
        return (
            f"lnbits.extensions.{self.code}"
            if self.hash == ""
            else f"lnbits.upgrades.{self.code}-{self.hash}.{self.code}"
        )

    @classmethod
    def from_installable_ext(cls, ext_info: "InstallableExtension") -> "Extension":
        return Extension(
            code=ext_info.id,
            is_valid=True,
            is_admin_only=False,  # todo: is admin only
            name=ext_info.name,
            hash=ext_info.hash if ext_info.module_installed else "",
        )


class ExtensionManager:
    def __init__(self, include_disabled_exts=False):
        self._disabled: List[str] = (
            [] if include_disabled_exts else settings.lnbits_disabled_extensions
        )
        self._admin_only: List[str] = settings.lnbits_admin_extensions
        self._extension_folders: List[str] = [
            x[1] for x in os.walk(os.path.join(settings.lnbits_path, "extensions"))
        ][0]

    @property
    def extensions(self) -> List[Extension]:
        output: List[Extension] = []

        if "all" in self._disabled:
            return output

        for extension in [
            ext for ext in self._extension_folders if ext not in self._disabled
        ]:
            try:
                with open(
                    os.path.join(
                        settings.lnbits_path, "extensions", extension, "config.json"
                    )
                ) as json_file:
                    config = json.load(json_file)
                is_valid = True
                is_admin_only = True if extension in self._admin_only else False
            except Exception:
                config = {}
                is_valid = False
                is_admin_only = False

            output.append(
                Extension(
                    extension,
                    is_valid,
                    is_admin_only,
                    config.get("name"),
                    config.get("short_description"),
                    config.get("tile"),
                    config.get("contributors"),
                    config.get("hidden") or False,
                    config.get("migration_module"),
                    config.get("db_name"),
                )
            )

        return output


class InstallableExtension(NamedTuple):
    id: str
    name: str
    archive: str
    hash: str
    short_description: Optional[str] = None
    details: Optional[str] = None
    icon: Optional[str] = None
    dependencies: List[str] = []
    is_admin_only: bool = False
    version: Optional[int] = 0

    @property
    def zip_path(self) -> str:
        extensions_data_dir = os.path.join(settings.lnbits_data_folder, "extensions")
        os.makedirs(extensions_data_dir, exist_ok=True)
        return os.path.join(extensions_data_dir, f"{self.id}.zip")

    @property
    def ext_dir(self) -> str:
        return os.path.join("lnbits", "extensions", self.id)

    @property
    def ext_upgrade_dir(self) -> str:
        return os.path.join("lnbits", "upgrades", f"{self.id}-{self.hash}")

    @property
    def module_name(self) -> str:
        return f"lnbits.extensions.{self.id}"

    @property
    def module_installed(self) -> bool:
        return self.module_name in sys.modules

    def download_archive(self):
        ext_zip_file = self.zip_path
        if os.path.isfile(ext_zip_file):
            os.remove(ext_zip_file)
        try:
            download_url(self.archive, ext_zip_file)
        except Exception as ex:
            logger.warning(ex)
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Cannot fetch extension archive file",
            )

        archive_hash = file_hash(ext_zip_file)
        if self.hash != archive_hash:
            # remove downloaded archive
            if os.path.isfile(ext_zip_file):
                os.remove(ext_zip_file)
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="File hash missmatch. Will not install.",
            )

    def extract_archive(self):
        shutil.rmtree(self.ext_dir, True)
        with zipfile.ZipFile(self.zip_path, "r") as zip_ref:
            zip_ref.extractall(os.path.join("lnbits", "extensions"))

        os.makedirs(os.path.join("lnbits", "upgrades"), exist_ok=True)
        shutil.rmtree(self.ext_upgrade_dir, True)
        with zipfile.ZipFile(self.zip_path, "r") as zip_ref:
            zip_ref.extractall(self.ext_upgrade_dir)

    def nofiy_upgrade(self) -> None:
        """Update the the list of upgraded extensions. The middleware will perform redirects based on this"""
        if not self.hash:
            return

        clean_upgraded_exts = list(
            filter(
                lambda old_ext: not old_ext.endswith(f"/{self.id}"),
                settings.lnbits_upgraded_extensions,
            )
        )
        settings.lnbits_upgraded_extensions = clean_upgraded_exts + [
            f"{self.hash}/{self.id}"
        ]

    def clean_extension_files(self):
        # remove downloaded archive
        if os.path.isfile(self.zip_path):
            os.remove(self.zip_path)

        # remove module from extensions
        shutil.rmtree(self.ext_dir, True)
        
        shutil.rmtree(self.ext_upgrade_dir, True)

    @classmethod
    async def get_extension_info(cls, ext_id: str, hash: str) -> "InstallableExtension":
        installable_extensions: List[
            InstallableExtension
        ] = await InstallableExtension.get_installable_extensions()

        valid_extensions = [
            e for e in installable_extensions if e.id == ext_id and e.hash == hash
        ]
        if len(valid_extensions) == 0:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Unknown extension id: {ext_id}",
            )
        extension = valid_extensions[0]

        # check that all dependecies are installed
        installed_extensions = list(map(lambda e: e.code, get_valid_extensions(True)))
        if not set(extension.dependencies).issubset(installed_extensions):
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=f"Not all dependencies are installed: {extension.dependencies}",
            )

        return extension

    @classmethod
    async def get_installable_extensions(cls) -> List["InstallableExtension"]:
        extension_list: List[InstallableExtension] = []

        async with httpx.AsyncClient() as client:
            for url in settings.lnbits_extensions_manifests:
                resp = await client.get(url)
                if resp.status_code != 200:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Unable to fetch extension list for repository: {url}",
                    )
                for e in resp.json()["extensions"]:
                    extension_list += [
                        InstallableExtension(
                            id=e["id"],
                            name=e["name"],
                            archive=e["archive"],
                            hash=e["hash"],
                            short_description=e["shortDescription"],
                            details=e["details"] if "details" in e else "",
                            icon=e["icon"],
                            dependencies=e["dependencies"]
                            if "dependencies" in e
                            else [],
                        )
                    ]

        return extension_list


class InstalledExtensionMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not "path" in scope:
            await self.app(scope, receive, send)
            return

        path_elements = scope["path"].split("/")
        if len(path_elements) > 2:
            _, path_name, path_type, *rest = path_elements
        else:
            _, path_name = path_elements
            path_type = None

        # block path for all users if the extension is disabled
        if path_name in settings.lnbits_disabled_extensions:
            response = JSONResponse(
                status_code=HTTPStatus.NOT_FOUND,
                content={"detail": f"Extension '{path_name}' disabled"},
            )
            await response(scope, receive, send)
            return

        # re-route API trafic if the extension has been upgraded
        if path_type == "api":
            upgraded_extensions = list(
                filter(
                    lambda ext: ext.endswith(f"/{path_name}"),
                    settings.lnbits_upgraded_extensions,
                )
            )
            if len(upgraded_extensions) != 0:
                upgrade_path = upgraded_extensions[0]
                tail = "/".join(rest)
                scope["path"] = f"/upgrades/{upgrade_path}/{path_type}/{tail}"

        await self.app(scope, receive, send)


def get_valid_extensions(include_disabled_exts=False) -> List[Extension]:
    return [
        extension
        for extension in ExtensionManager(include_disabled_exts).extensions
        if extension.is_valid
    ]


def download_url(url, save_path):
    with urllib.request.urlopen(url) as dl_file:
        with open(save_path, "wb") as out_file:
            out_file.write(dl_file.read())


def file_hash(filename):
    h = hashlib.sha256()
    b = bytearray(128 * 1024)
    mv = memoryview(b)
    with open(filename, "rb", buffering=0) as f:
        while n := f.readinto(mv):
            h.update(mv[:n])
    return h.hexdigest()
