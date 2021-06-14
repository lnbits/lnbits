import json, os, httpx
from . import db
from lnbits.helpers import urlsafe_short_hash
from environs import Env
env = Env()
env.read_env()
HOST = env.str("HOST", default="0.0.0.0")
PORT = env.int("PORT", default=5000)
L_HOST = f"http://{HOST}:{PORT}"
DB={}

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
                    "payment_hash":'', 
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
            return response
        except:
            return {"error": "Royalty error"}

async def create_royalty(payload:dict) -> dict:
    id = urlsafe_short_hash()
    #add royalty to db (id, paid, data, date)
    DB[id] = payload
    print(DB)
    #returns invoice webhook to be completed on payment
    return {"success":f"{L_HOST}/royalties/api/v1/pay/{id}"}