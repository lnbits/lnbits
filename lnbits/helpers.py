import json
import sqlite3


class MegaEncoder(json.JSONEncoder):
    def default(self, o):
        if type(o) == sqlite3.Row:
            val = {}
            for k in o.keys():
                val[k] = o[k]
            return val
        return o


def megajson(obj):
    return json.dumps(obj, cls=MegaEncoder)
