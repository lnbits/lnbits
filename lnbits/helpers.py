import json
import os
import sqlite3

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
    def __init__(self):
        self._extension_folders: List[str] = [x[1] for x in os.walk(os.path.join(LNBITS_PATH, "extensions"))][0]

    @property
    def extensions(self) -> List[Extension]:
        output = []

        for extension in self._extension_folders:
            try:
                with open(os.path.join(LNBITS_PATH, "extensions", extension, "config.json")) as json_file:
                    config = json.load(json_file)
                is_valid = True
            except Exception:
                config = {}
                is_valid = False

            output.append(Extension(**{**{"code": extension, "is_valid": is_valid}, **config}))

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
    TOO_MANY_REQUESTS = 429
    METHOD_NOT_ALLOWED = 405


class MegaEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, sqlite3.Row):
            return {k: obj[k] for k in obj.keys()}
        return obj


def megajson(obj):
    return json.dumps(obj, cls=MegaEncoder)
