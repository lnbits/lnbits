import json, os, httpx
from quart import jsonify
from . import db
from typing import Optional
from .models import Royalty, RoyaltyAccount
from lnbits.core.crud import get_wallet_for_key
from lnbits.core.services import create_invoice, pay_invoice
from environs import Env
env = Env()
env.read_env()
HOST = env.str("HOST", default="0.0.0.0")
PORT = env.int("PORT", default=5000)
L_HOST = f"http://{HOST}:{PORT}"

async def royalty(inkey:str, amount:int) -> dict:
    # from environs import Env ## add to imports
    # env = Env()
    # env.read_env()
    # HOST = env.str("HOST", default="0.0.0.0")
    # PORT = env.int("PORT", default=5000)
    # L_HOST = f"http://{HOST}:{PORT}"
    dir_path = os.path.dirname(os.path.realpath(__file__))
    payload = []
    with open(dir_path+'/config.json') as config_file:
        data = json.load(config_file)
        for royalty in data['royalties']:
            url_endpoint = '/royalties/api/v1/generate/'+royalty['key']
            payload.append(
                {
                    "inkey":inkey,
                    "amount":amount, 
                    "payment_request":"",
                    "paid":False, 
                    "url": royalty['url']+url_endpoint+'?amount='+str(int(amount*(royalty['percentage']/100)))
                }
            )
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                L_HOST+'/royalties/api/v1/create',
                headers={
                    "Content-Type":"application/json",
                    "X-Api-Key":inkey
                    },
                data= json.dumps(payload),
                timeout=40
            )
            response = r.json()
            #temporary invoice. Do in stack
            wallet = (await get_wallet_for_key(inkey))[0]
            payment_request, payment_hash = await create_invoice(
                wallet_id=wallet,
                amount=100,
                memo="test invoice",
                webhook= response['success']
            )
            # return response
            return {"success":payment_hash}
        except:
            return {"error": "Royalty error"}

async def create_royalty(id:str ,paid:bool, data:str) -> Royalty:
    try:
        await db.execute(
            """
            INSERT INTO royalties (id, paid, data)
            VALUES (?,?,?)
            """,
            (id, paid, data)
        )
        #returns invoice webhook to be completed on payment
        return {"success":f"{L_HOST}/royalties/api/v1/pay/{id}"}
    except:
        return {"error": "Database error!"}

async def pay_royalty(id:str) -> dict:
    #get royalty entry from db (id)
    row = await db.fetchone("SELECT * FROM royalties WHERE id = ? AND paid = FALSE",(id))
    if row is None:
      return {"error":"No royalty found"}
    row = dict(row)
    all_payments = True
    data = json.loads(row['data'])
    print(data)
    for rlty in data:
        if rlty['paid']:
            pass
        async with httpx.AsyncClient() as client:
            try:
                r = await client.get(
                    rlty['url'],
                    timeout=40
                )
                response = r.json()
                if 'success' in response:
                    wallet = (await get_wallet_for_key(rlty['inkey']))[0]
                    try:
                        paid = await pay_invoice(
                            wallet_id=wallet, 
                            payment_request=response['success']['payment_hash']
                        )
                        print(paid)
                        rlty['payment_request'] = response['success']['payment_hash']
                        rlty['paid'] = True
                        continue
                    except:
                        rlty['payment_request'] = response['success']['payment_hash']
                        all_payments = False
                        continue
                else:
                    print('http request error')
                    continue
            except:
                pass 
    await db.execute("UPDATE royalties SET paid = ?, data = ? WHERE id = ?",(all_payments, json.dumps(data), id))
    #returns nothing
    return {"success": "paid"}

async def generate_royalty(id:str, amount:int) -> dict:
    #get wallet id from royalty_account db (id)
    row = await db.fetchone("SELECT * FROM royalty_account WHERE id = ?",(id))
    if row is None:
        return {"error": "No Account found"}
    invoice_wallet = dict(row)['wallet']
    #generate invoice using core invoice
    try:
        payment_request, payment_hash = await create_invoice(
                wallet_id=invoice_wallet,
                amount=amount,
                memo="Royalty - LNbits"
        )
        #returns payment request
        return {"success":{"payment_hash":payment_hash, "payment_request": payment_request}}
    except:
        return {"error": "Failed to generate invoice"}

async def create_royalty_account(id:str, wallet:str) -> RoyaltyAccount:
    try:
        await db.execute(
            """
            INSERT INTO royalty_account (id, wallet)
            VALUES (?,?)
            """,
            (id, wallet)
        )
        row = await get_royalty_account(id)
        #returns invoice webhook to be completed on payment
        return row
    except:
        return {"error": "Database error!"}

async def get_royalty_account(id:Optional[str])-> dict:
    try:
        if id:
            row = await db.fetchone("SELECT * FROM royalty_account WHERE id = ?",(id))
            row = dict(row)
        else:
            row = await db.fetchall("SELECT * FROM royalty_account")
            row = [dict(ix) for ix in row]
        #returns accounts
        return {"success": row}
    except:
        return {"error": "Database error!"}
        
async def delete_royalty_account(id:str)-> dict:
    try:
        await db.execute("DELETE FROM royalty_account WHERE id =?",(id))
        return {"success":"Account deleted"}
    except:
        return {"error": "Database error!"}