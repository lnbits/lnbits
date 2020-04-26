import json
import os
import shortuuid # type: ignore

from typing import List, NamedTuple, Optional

from .settings import LNBITS_PATH


class Extension(NamedTuple):
    code: str
    is_valid: bool
    name: Optional[str] = None
    short_description: Optional[str] = None
    icon: Optional[str] = None
    contributors: Optional[List[str]] = None


class ExtensionManager:
    def __init__(self, *, disabled: list = []):
        self._disabled = disabled
        self._extension_folders: List[str] = [x[1] for x in os.walk(os.path.join(LNBITS_PATH, "extensions"))][0]

    @property
    def extensions(self) -> List[Extension]:
        output = []

        for extension in [ext for ext in self._extension_folders if ext not in self._disabled]:
            try:
                with open(os.path.join(LNBITS_PATH, "extensions", extension, "config.json")) as json_file:
                    config = json.load(json_file)
                is_valid = True
            except Exception:
                config = {}
                is_valid = False

            output.append(Extension(
                extension,
                is_valid,
                config.get('name'),
                config.get('short_description'),
                config.get('icon'),
                config.get('contributors')
            ))

        return output


class Status:
    OK = 200
    CREATED = 201
    NO_CONTENT = 204
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    PAYMENT_REQUIRED = 402
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    UPGRADE_REQUIRED = 426
    TOO_MANY_REQUESTS = 429
    INTERNAL_SERVER_ERROR = 500


def urlsafe_short_hash() -> str:
    return shortuuid.uuid()
