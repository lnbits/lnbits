import glob
import json
import os
from typing import Any, List, NamedTuple, Optional

import jinja2
import shortuuid  # type: ignore

import lnbits.settings as settings
from lnbits.jinja2_templating import Jinja2Templates
from lnbits.requestvars import g


class Extension(NamedTuple):
    code: str
    is_valid: bool
    is_admin_only: bool
    name: Optional[str] = None
    short_description: Optional[str] = None
    icon: Optional[str] = None
    contributors: Optional[List[str]] = None
    hidden: bool = False


class ExtensionManager:
    def __init__(self):
        self._disabled: List[str] = settings.LNBITS_DISABLED_EXTENSIONS
        self._admin_only: List[str] = [
            x.strip(" ") for x in settings.LNBITS_ADMIN_EXTENSIONS
        ]
        self._extension_folders: List[str] = [
            x[1] for x in os.walk(os.path.join(settings.LNBITS_PATH, "extensions"))
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
                        settings.LNBITS_PATH, "extensions", extension, "config.json"
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
                    config.get("icon"),
                    config.get("contributors"),
                    config.get("hidden") or False,
                )
            )

        return output


def get_valid_extensions() -> List[Extension]:
    return [
        extension for extension in ExtensionManager().extensions if extension.is_valid
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
        os.path.join(settings.LNBITS_PATH, "static/vendor/**"), recursive=True
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
    return "/" + os.path.relpath(abspath, settings.LNBITS_PATH)


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

    if settings.LNBITS_AD_SPACE:
        t.env.globals["AD_SPACE"] = settings.LNBITS_AD_SPACE
    t.env.globals["HIDE_API"] = settings.LNBITS_HIDE_API
    t.env.globals["SITE_TITLE"] = settings.LNBITS_SITE_TITLE
    t.env.globals["LNBITS_DENOMINATION"] = settings.LNBITS_DENOMINATION
    t.env.globals["SITE_TAGLINE"] = settings.LNBITS_SITE_TAGLINE
    t.env.globals["SITE_DESCRIPTION"] = settings.LNBITS_SITE_DESCRIPTION
    t.env.globals["LNBITS_THEME_OPTIONS"] = settings.LNBITS_THEME_OPTIONS
    t.env.globals["LNBITS_VERSION"] = settings.LNBITS_COMMIT
    t.env.globals["EXTENSIONS"] = get_valid_extensions()
    if settings.LNBITS_CUSTOM_LOGO:
        t.env.globals["USE_CUSTOM_LOGO"] = settings.LNBITS_CUSTOM_LOGO

    if settings.DEBUG:
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
