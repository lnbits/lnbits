import json
import os
import sqlite3

from types import SimpleNamespace
from typing import List

from .settings import LNBITS_PATH


class ExtensionManager:
    def __init__(self):
        self._extension_folders: List[str] = [x[1] for x in os.walk(os.path.join(LNBITS_PATH, "extensions"))][0]

    @property
    def extensions(self) -> List[SimpleNamespace]:
        output = []

        for extension in self._extension_folders:
            try:
                with open(os.path.join(LNBITS_PATH, "extensions", extension, "config.json")) as json_file:
                    config = json.load(json_file)
                is_valid = True
            except Exception:
                config = {}
                is_valid = False

            output.append(SimpleNamespace(**{
                **{
                    "code": extension,
                    "is_valid": is_valid,
                    "path": os.path.join(LNBITS_PATH, "extensions", extension),
                },
                **config
            }))

        return output


class MegaEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, sqlite3.Row):
            return {k: obj[k] for k in obj.keys()}
        return obj


def megajson(obj):
    return json.dumps(obj, cls=MegaEncoder)
