from quart import jsonify
from lnbits.helpers import urlsafe_short_hash
from typing import List, Optional
from .models import Logs
from . import db, wal_db
from environs import Env
import json, httpx, math
from datetime import date, datetime 
env = Env()
env.read_env()
HOST = env.str("HOST", default="0.0.0.0")
PORT = env.int("PORT", default=5000)
L_HOST = f"http://{HOST}:{PORT}"

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

async def adminKeyFromWallet(user:str)->str:
    row = await wal_db.fetchone(f"SELECT adminkey FROM wallets WHERE user = '{user}'")
    if row is None:
        return '0'
    else:
        return row[0]

async def getUser(id:str, local:bool, lnurl_auth:Optional[str], params:Optional[dict])-> dict:
    if lnurl_auth is not None:
        if params is not None and "admin" in params:
            row = await db.fetchone("SELECT * FROM users WHERE lnurl_auth = ? AND admin = ?",(lnurl_auth, params['admin']))
        else:
            row = await db.fetchone("SELECT * FROM users WHERE lnurl_auth = ?",(lnurl_auth))
    else:
        row = await db.fetchone("SELECT * FROM users WHERE id = ?",(id))
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
        del usr['lnurl_auth']
    return users

async def getPayoutBalance(inKey:str, url:str)->int:
    headers = {
        "Content-Type":"application/json",
        "X-Api-Key":inKey
        }
    #base_url = url.rsplit('/', 6)[0]
    base_url = L_HOST
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

async def accountRecovery(params:dict)->dict:
    try:
        user_exists = await db.fetchone("SELECT * FROM users WHERE lnurl_auth = ?",(params['linking_key']))
        if user_exists is not None:
            return {"error": "Account already exists!"}
        row =  await db.execute("UPDATE users SET lnurl_auth = ? WHERE lnurl_auth = ? ",(params['linking_key'],params['recovery_key']))
        usr = await getUser('lnurl_auth', False, params['linking_key'],None)
        return json.dumps({"success": usr})
    except ValueError:
        return {"error": "Unable to recover account"}

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

async def klankyRachet(count:int)->float:
    base_fee = 0.01
    if count == 0:
        return base_fee
    else:
        percent = float(math.log10(count)/100)*2
        fee = base_fee if percent <= 0.04 else 0.1 if percent >= 0.074 else percent
        return fee
