from quart import jsonify
from lnbits.helpers import urlsafe_short_hash
from lnbits.core.services import create_invoice
from .models import Setup, Users, Logs
from .helpers import usrFromWallet, widFromWallet
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
    payout_wallet:str,
    credits:int,
    active:bool,
    data:Optional[str],
)->Users:
    id = urlsafe_short_hash()
    data = None if data is None else None
    try:
        await db.execute(
            """
            INSERT INTO users (usr_id, id, payout_wallet,credits,active,data)
            VALUES (?,?,?,?,?,?)
            """,
            (usr_id, id, payout_wallet,credits, active, data)
            )
        return {"success":jsonify(id=id, credits=0, active=True)}
    except:
        return jsonify(error='Server error. User not created')



async def API_createUser(inKey:str, auto:bool, data:Optional[str])-> dict:
    id = urlsafe_short_hash()
    if auto:
        js_on = data
        base_url = js_on['url'].rsplit('/', 4)[0]
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
            except:
                pass
        print(id)
        print(uid)
        print(wid)
        # api create user 
        return user
    else:
        return user