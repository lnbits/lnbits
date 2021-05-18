from quart import jsonify
from lnbits.helpers import urlsafe_short_hash
from typing import List, Optional
from .models import Logs
from . import db, wal_db
import json, httpx
from datetime import date, datetime 

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

async def inKeyFromWallet(user:str)->str:
    row = await wal_db.fetchone(f"SELECT inkey FROM wallets WHERE user = '{user}'")
    if row is None:
        return '0'
    else:
        return row[0]

async def getUser(id:str, local:bool)-> dict:
    row = await db.fetchone(f"SELECT * FROM users WHERE id = '{id}'")
    if row is None:
        return {"error":"No user found"}
    if local:
        return dict(row)
    else:
        usr = dict(row)
        del usr['usr_id']
        del usr['admin']
        del usr['payout_wallet']
        return usr

async def getUsers(admin_id:str, local:bool)-> dict:
    row = await db.fetchall(f"SELECT * FROM users WHERE admin = '{admin_id}'")
    if row is None:
        return jsonify(error='No user found')
    # if local:
    #     return [dict(ix) for ix in row]
    # else:
    users = [dict(ix) for ix in row]
    for usr in users:
        del usr['usr_id']
        del usr['admin']
        del usr['payout_wallet']
    return users

async def getPayoutBalance(inKey:str, url:str)->int:
    headers = {
        "Content-Type":"application/json",
        "X-Api-Key":inKey
        }
    base_url = url.rsplit('/', 6)[0]
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                base_url+'/api/v1/wallet',
                headers=headers, 
                timeout=40,
            )
            balance = r.json()
            return balance
        except:
            return jsonify(error=True)

async def getLogs(usr_id:str, limit:Optional[str])-> List:
    t = 'LIMIT 20'if limit is None else '' if limit == 'all' else 'LIMIT '+limit
    row = await db.fetchall(f"SELECT * FROM logs WHERE usr = '{usr_id}' ORDER BY time DESC {t}")
    if row is None:
        return jsonify({'success':[]})
    logs = [dict(ix) for ix in row]
    return logs

async def createLog(
    usr:str,
    cmd:str,
    wl:Optional[str],
    credits:Optional[int],
    multi:Optional[int],
    sats:Optional[int],
    data:Optional[str],
)->Logs:
    try:
        await db.execute(
            """
            INSERT INTO logs (usr,cmd,wl,credits,multi,sats,data)
            VALUES (?,?,?,?,?,?,?)
            """,
            (usr, cmd, wl, credits, multi, sats,data)
            )
        return True
    except ValueError:
        print(ValueError)
        return False

async def handleCredits(id:str, credits:int)-> bool:
    try:
        row =  await db.execute(f"UPDATE users SET credits = {credits} WHERE id = '{str(id)}'")
        return True
    except ValueError:
        return False

async def numPayments(user:str)->int:
    timestamp = int(datetime.timestamp(datetime.now()))
    seven_days = timestamp - int(60*60*24*7)
    count = await db.fetchall(f"SELECT COUNT(time) FROM payments WHERE paid = True AND admin_id = '{user}' AND cmd = 'payment' AND time >= {seven_days} ORDER BY time DESC")
    return int(count[0][0])     
