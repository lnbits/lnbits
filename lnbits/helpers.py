import glob
import hashlib
import json
import os
import shutil
import urllib.request
from http import HTTPStatus
from typing import Any, List, NamedTuple, Optional

import httpx
import jinja2
import shortuuid  # type: ignore
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.types import ASGIApp, Receive, Scope, Send

from lnbits.jinja2_templating import Jinja2Templates
from lnbits.requestvars import g
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
    def zip_path(self):
        extensions_data_dir = os.path.join(settings.lnbits_data_folder, "extensions")
        os.makedirs(extensions_data_dir, exist_ok=True)
        return os.path.join(extensions_data_dir, f"{self.id}.zip")

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


def urlsafe_short_hash() -> str:
    return shortuuid.uuid()


def get_js_vendored(prefer_minified: bool = False) -> List[str]:
    paths = get_vendored(".js", prefer_minified)

    def sorter(key: str):
        if "moment@" in key:
            return 1
        if "vue@" in key:
            return 2
        if "vue-router@" in key:
            return 3
        if "polyfills" in key:
            return 4
        return 9

    return sorted(paths, key=sorter)


def get_css_vendored(prefer_minified: bool = False) -> List[str]:
    paths = get_vendored(".css", prefer_minified)

    def sorter(key: str):
        if "quasar@" in key:
            return 1
        if "vue@" in key:
            return 2
        if "chart.js@" in key:
            return 100
        return 9

    return sorted(paths, key=sorter)


def get_vendored(ext: str, prefer_minified: bool = False) -> List[str]:
    paths: List[str] = []
    for path in glob.glob(
        os.path.join(settings.lnbits_path, "static/vendor/**"), recursive=True
    ):
        if path.endswith(".min" + ext):
            # path is minified
            unminified = path.replace(".min" + ext, ext)
            if prefer_minified:
                paths.append(path)
                if unminified in paths:
                    paths.remove(unminified)
            elif unminified not in paths:
                paths.append(path)

        elif path.endswith(ext):
            # path is not minified
            minified = path.replace(ext, ".min" + ext)
            if not prefer_minified:
                paths.append(path)
                if minified in paths:
                    paths.remove(minified)
            elif minified not in paths:
                paths.append(path)

    return sorted(paths)


def url_for_vendored(abspath: str) -> str:
    return "/" + os.path.relpath(abspath, settings.lnbits_path)


def url_for(endpoint: str, external: Optional[bool] = False, **params: Any) -> str:
    base = g().base_url if external else ""
    url_params = "?"
    for key in params:
        url_params += f"{key}={params[key]}&"
    url = f"{base}{endpoint}{url_params}"
    return url


def template_renderer(additional_folders: List = []) -> Jinja2Templates:

    t = Jinja2Templates(
        loader=jinja2.FileSystemLoader(
            ["lnbits/templates", "lnbits/core/templates", *additional_folders]
        )
    )

    if settings.lnbits_ad_space_enabled:
        t.env.globals["AD_SPACE"] = settings.lnbits_ad_space.split(",")
        t.env.globals["AD_SPACE_TITLE"] = settings.lnbits_ad_space_title

    t.env.globals["HIDE_API"] = settings.lnbits_hide_api
    t.env.globals["SITE_TITLE"] = settings.lnbits_site_title
    t.env.globals["LNBITS_DENOMINATION"] = settings.lnbits_denomination
    t.env.globals["SITE_TAGLINE"] = settings.lnbits_site_tagline
    t.env.globals["SITE_DESCRIPTION"] = settings.lnbits_site_description
    t.env.globals["LNBITS_THEME_OPTIONS"] = settings.lnbits_theme_options
    t.env.globals["LNBITS_VERSION"] = settings.lnbits_commit
    t.env.globals["EXTENSIONS"] = get_valid_extensions()
    if settings.lnbits_custom_logo:
        t.env.globals["USE_CUSTOM_LOGO"] = settings.lnbits_custom_logo

    if settings.debug:
        t.env.globals["VENDORED_JS"] = map(url_for_vendored, get_js_vendored())
        t.env.globals["VENDORED_CSS"] = map(url_for_vendored, get_css_vendored())
    else:
        t.env.globals["VENDORED_JS"] = ["/static/bundle.js"]
        t.env.globals["VENDORED_CSS"] = ["/static/bundle.css"]

    return t


def get_current_extension_name() -> str:
    """
    Returns the name of the extension that calls this method.
    """
    import inspect
    import json
    import os

    callee_filepath = inspect.stack()[1].filename
    callee_dirname, callee_filename = os.path.split(callee_filepath)

    path = os.path.normpath(callee_dirname)
    extension_director_name = path.split(os.sep)[-1]
    try:
        config_path = os.path.join(callee_dirname, "config.json")
        with open(config_path) as json_file:
            config = json.load(json_file)
        ext_name = config["name"]
    except:
        ext_name = extension_director_name
    return ext_name


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
