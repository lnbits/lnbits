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