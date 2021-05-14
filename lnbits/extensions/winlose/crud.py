from quart import jsonify
from lnbits.helpers import urlsafe_short_hash
from lnbits.core.services import create_invoice
from .models import Setup, Users, Logs
from .helpers import (
    usrFromWallet, 
    widFromWallet, 
    inKeyFromWallet,
    getUser, 
    getUsers, 
    getLogs, 
    createLog,
    getPayoutBalance
    )
from typing import List, Optional
from . import db
import json, httpx

async def accountSetup(
    usr_id:str,
    invoice_wallet:str,
    payout_wallet:str,
    data:Optional[str]
)-> Setup:
    data = None if data is None else None
    await db.execute(
        """
        INSERT OR REPLACE INTO setup (usr_id, invoice_wallet, payout_wallet,data)
        VALUES (?,?,?,?)
        """,
        (usr_id, invoice_wallet, payout_wallet, data)
        )
    return jsonify(success='Account updated')

async def createdb_user(
    usr_id:str,
    id:str,
    admin:str,
    payout_wallet:str,
    credits:int,
    active:bool,
    data:Optional[str],
)->Users:
    data = None if data is None else data
    try:
        await db.execute(
            """
            INSERT INTO users (usr_id, id, admin,payout_wallet,credits,active,data)
            VALUES (?,?,?,?,?,?,?)
            """,
            (usr_id, id, admin, payout_wallet,credits, active, data)
            )
        await createLog(id, "User Created",None,None,None,None,None)
        return jsonify(success=True)
    except:
        print('log error')
        return jsonify(error='Server error. User not created')

async def API_createUser(inKey:str, auto:bool, data:Optional[str])-> dict:
    data, url, local = data.values()
    id = data['id'] if 'id' in data is not None else urlsafe_short_hash()
    if auto:
        base_url = url.rsplit('/', 4)[0]
        user = await usrFromWallet(inKey)
        headers = {
            "Content-Type":"application/json",
            "X-Api-Key":inKey
            }
        payload={"admin_id": user, "wallet_name": "Payout", "user_name":id}
        url = base_url+'/usermanager/api/v1/users'
        async with httpx.AsyncClient() as client:
            try:
                r = await client.post(
                    url,
                    headers=headers, 
                    json=payload,
                    timeout=40,
                )
                uid = r.json()['id']
                wid = await widFromWallet(uid)
                newUser = await createdb_user(uid, id, user, wid, 0, True, None)
                local = False if local is None else True
                rUser = await getUser(id, local)
                return {'success':rUser}
            except ValueError:
                print(ValueError)
                return jsonify(error='User not created!')
    else:
        # manual add existing user form user managemnet
        return user

async def API_deleteUser(id:str, url:str, inKey:str)->dict:
    base_url = url.rsplit('/', 5)[0]
    user = await usrFromWallet(inKey)
    try:
        uid = (await getUser(id, True))['usr_id']
    except:
        uid = '123456jsjdka'
    headers = {
        "Content-Type":"application/json",
        "X-Api-Key":inKey
        }
    url = base_url+'/usermanager/api/v1/users/'+uid
    async with httpx.AsyncClient() as client:
        r = await client.delete(
            url,
            headers=headers,
            timeout=40,
        )
    if int(r.status_code) == 204:
        await db.execute(f"DELETE FROM users WHERE id = '{id}'")
        return jsonify({'success':{'id':id,'deleted':True}})
    else:
        return jsonify({'error':{'id':id,'deleted':False}})  

async def API_updateUser(p)-> dict:
    await db.execute(f"UPDATE users SET '{p['set']}' = {p['payload']} WHERE id = '{p['id']}'")
    return {"success":"User updated"}

async def API_getUsers(params:dict)-> dict:
    local = params['local'] if 'local' in params else False
    logs = None
    if 'id' in params:
        usr = await getUser(params['id'], True) 
        del usr['admin']   
        inKey = await inKeyFromWallet(usr['usr_id'])
        url = params['url'].rsplit('?', 1)[0]+'/payout/user'
        balance = await getPayoutBalance(inKey, url)
        if 'logs' in params and params['logs']:
            logs = await getLogs(params['id'])
        usr['balance'] = balance['balance']
        # if not local:
        del usr['usr_id']
        del usr['payout_wallet']
    else:
        admin_id = await usrFromWallet(params['inKey'])
        usr = await getUsers(admin_id, local)
        # if local:
        #     for u in usr: 
        #         del u['admin']
    data = {"usr":usr}
    data['logs'] = logs if logs is not None else None
    return jsonify({'success':data})