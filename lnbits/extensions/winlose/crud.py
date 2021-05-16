from quart import jsonify
from lnbits.helpers import urlsafe_short_hash
from lnbits.core.services import create_invoice, pay_invoice
from .models import Setup, Users, Logs
from .helpers import (
    usrFromWallet, 
    widFromWallet, 
    inKeyFromWallet,
    getUser, 
    getUsers, 
    getLogs, 
    createLog,
    getPayoutBalance,
    handleCredits
    )
from typing import List, Optional, Dict
from . import db
import json, httpx

async def accountSetup(
    usr_id:str,
    invoice_wallet:str,
    payout_wallet:str,
    data:Optional[str]
)-> Setup:
    #data = None if data is None else None
    await db.execute(
        """
        INSERT OR REPLACE INTO setup (usr_id, invoice_wallet, payout_wallet,data)
        VALUES (?,?,?,?)
        """,
        (usr_id, invoice_wallet, payout_wallet, data)
        )
    return jsonify({'success': 'Account Updated'})

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

async def getSettings(inKey:Optional[str], admin:Optional[str])->dict:
    usr = admin if admin is not None else await usrFromWallet(inKey)
    try:
        row = await db.fetchone(f"SELECT * FROM setup WHERE usr_id = '{usr}'")
        d = dict(row)
        del d['usr_id']
        return {"success": d}
    except:
        return jsonify({'success': {}})

async def API_createUser(inKey:str, auto:bool, data:Optional[str])-> dict:
    data, url, local, = data['data'], data['url'], data['local']
    local = False if local is None else True
    id = data['id'] if 'id' in data is not None else urlsafe_short_hash()
    user = await usrFromWallet(inKey)
    if auto:
        base_url = url.rsplit('/', 4)[0]
        url = base_url+'/usermanager/api/v1/users'
        headers = {
            "Content-Type":"application/json",
            "X-Api-Key":inKey
            }
        payload={"admin_id": user, "wallet_name": "Payout", "user_name":id}
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
                rUser = await getUser(id, local)
                return {'success':rUser}
            except ValueError:
                print(ValueError)
                return jsonify(error='User not created!')
    else:
        uid, wid = data['uid'], data['wid']
        newUser = await createdb_user(uid, id, user, wid, 0, True, None)
        User = await getUser(id, local)
        return {'success':User}

async def API_deleteUser(id:str, url:str, inKey:str,wlOnly:bool)->dict:
    base_url = url.rsplit('/', 5)[0]
    user = await usrFromWallet(inKey)
    try:
        uid = (await getUser(id, True))['usr_id']
    except:
        uid = '123456jsjdka'
    if not wlOnly:
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
    else:
        await db.execute(f"DELETE FROM users WHERE id = '{id}'")
        return jsonify({'success':{'id':id,'deleted':True}})

async def API_updateUser(p)-> dict:
    await db.execute(f"UPDATE users SET '{p['set']}' = {p['payload']} WHERE id = '{p['id']}'")
    return {"success":"User updated"}

async def API_getUsers(params:dict)-> dict:
    local = params['local'] if 'local' in params else False
    limit = params['limit'] if 'limit' in params else None 
    logs = None
    if 'id' in params:
        usr = await getUser(params['id'], True) 
        del usr['admin']   
        inKey = await inKeyFromWallet(usr['usr_id'])
        url = params['url'].rsplit('?', 1)[0]+'/payout/user'
        balance = await getPayoutBalance(inKey, url)
        if 'logs' in params and params['logs']:
            logs = await getLogs(params['id'], limit)
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

async def API_lose(id:str, params:dict)->dict:
    usr = await getUser(id, True)
    if not 'free_spin' in params:
        acca = int(params["multi"])*-1 if 'multi' in params else -1
        cred = int(usr['credits']) + acca
        cred = 0 if cred < 0 else cred
        credit_done = await handleCredits(id, cred)
        if credit_done:
            multi = params['multi'] if 'multi' in params else None
            logged = await createLog(
                id,
                'lose',
                'lose',
                1,
                multi,
                None,
                None
                )
            return {"success": {"id":id, "credits":cred}}
    else:
        spin_log = await createLog(
                id,
                'free spin',
                None,
                None,
                None,
                None,
                None
                )
        return {"success": {"id":id, "credits":int(usr['credits'])}}

async def API_win(id:str, params:dict)->dict:
    payout, credits, total_credits, bal = None,None,None,None
    usr = await getUser(id, True)
    if 'payout' in params:
        try:
            payout = int(params['payout'])
            admin_id, usr_wallet = usr['admin'], usr['payout_wallet']
            admin_wallet = (await getSettings(None, admin_id))['success']['payout_wallet']
            payment_hash, payment_request = await create_invoice(
                wallet_id=usr_wallet,
                amount=payout,
                memo=f"Payout - {id}")
            done = await pay_invoice(wallet_id=admin_wallet, payment_request=payment_request)
            try:
                inKey = await inKeyFromWallet(usr['usr_id'])
                url = params['url'].rsplit('?',1)[0]+'/payout'
                bal = int((await getPayoutBalance(inKey, url))['balance']/1000)
            except:
                pass
            log = await createLog(
                    id,
                    'payout',
                    'win',
                    None,
                    None,
                    payout,
                    None
                    )
        except:
            pass
            #return error no spins used
    if 'credits' in params:
        credits = params['credits']
        usr_cred = int((await getUser(id, True))['credits'])
        total_credits = int(params['credits']) + usr_cred
        credits_added = await handleCredits(id, total_credits)
        if credits_added:
            log = await createLog(
                id,
                'credits',
                'win',
                credits,
                None,
                None,
                None
                )
        else:
            pass
            #return error not spins
    if not 'free_spin' in params: 
        acca = int(params["multi"])*-1 if 'multi' in params else -1
        cred = int(usr['credits']) + acca
        cred = 0 if cred < 0 else cred
        credit_done = await handleCredits(id, cred)
        if credit_done:
            multi = params['multi'] if 'multi' in params else None
            logged = await createLog(
                id,
                'win',
                None,
                1,
                multi,
                None,
                None
                )
    win = int(credits) if credits is not None else payout
    win_type = 'credits' if credits is not None else 'sat'
    rem_credits = total_credits if total_credits is not None else int((await getUser(id, True))['credits'])
    return {"success": {"id":id,"win":win, "type": win_type, "credits":rem_credits, "payout_balance": bal}}