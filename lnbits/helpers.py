import json
import sqlite3


class MegaEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, sqlite3.Row):
            return {k: obj[k] for k in obj.keys()}
        return obj


def megajson(obj):
    return json.dumps(obj, cls=MegaEncoder)
