from quart import jsonify
from lnbits.helpers import urlsafe_short_hash
from typing import List, Optional
from . import db, wal_db
import json

async def usrFromWallet(inKey:str)->str:
    row = await wal_db.fetchone(f"SELECT user FROM wallets WHERE inkey = '{inKey}'")
    if row is None:
        return jsonify(error='No user found')
    return row[0]

async def widFromWallet(user:str)->str:
    row = await wal_db.fetchone(f"SELECT id FROM wallets WHERE user = '{user}'")
    if row is None:
        return jsonify(error='No user found')
    return row[0]

async def getUser(id:str, local:bool)-> dict:
    if local:
        row = await db.fetchone(f"SELECT * FROM users WHERE id = '{id}'")
        if row is None:
            return jsonify(error='No user found')
        return dict(row)
    else:
        return dict(row)

async def getUsers(admin_id:str, local:bool)-> dict:
    if local:
        row = await db.fetchall(f"SELECT * FROM users WHERE admin = '{admin_id}'")
        if row is None:
            return jsonify(error='No user found')
        return [dict(ix) for ix in row]
    else:
        return dict(row)