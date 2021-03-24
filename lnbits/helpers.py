import json
import os
import glob
import shortuuid  # type: ignore

from typing import List, NamedTuple, Optional

from .settings import LNBITS_DISABLED_EXTENSIONS, LNBITS_PATH


class Extension(NamedTuple):
    code: str
    is_valid: bool
    name: Optional[str] = None
    short_description: Optional[str] = None
    icon: Optional[str] = None
    contributors: Optional[List[str]] = None


class ExtensionManager:
    def __init__(self):
        self._disabled: List[str] = LNBITS_DISABLED_EXTENSIONS
        self._extension_folders: List[str] = [
            x[1] for x in os.walk(os.path.join(LNBITS_PATH, "extensions"))
        ][0]

    @property
    def extensions(self) -> List[Extension]:
        output = []

        for extension in [
            ext for ext in self._extension_folders if ext not in self._disabled
        ]:
            try:
                with open(
                    os.path.join(LNBITS_PATH, "extensions", extension, "config.json")
                ) as json_file:
                    config = json.load(json_file)
                is_valid = True
            except Exception:
                config = {}
                is_valid = False

            output.append(
                Extension(
                    extension,
                    is_valid,
                    config.get("name"),
                    config.get("short_description"),
                    config.get("icon"),
                    config.get("contributors"),
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
        os.path.join(LNBITS_PATH, "static/vendor/**"), recursive=True
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
    return "/" + os.path.relpath(abspath, LNBITS_PATH)
