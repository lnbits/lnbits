import hashlib
import hmac
from http import HTTPStatus
from fastapi import APIRouter, HTTPException, Request

from lnbits.settings import settings
import urllib.parse
from ..services import websocket_updater
fundingsource_router = APIRouter(tags=["OpennodeWebhook"])


def verify_signature(key:str,charge_id:str,received_signature:str):
    calculated_signature = hmac.new(key.encode(), charge_id.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(received_signature, calculated_signature)

@fundingsource_router.post('/api/v1/opennode-webhook',name="OpennodeWebhook",description="Opennode Webhook Endpoint")
async def api_opennode_webhook(request:Request)->None:
    key = (
            settings.opennode_key
            or settings.opennode_admin_key
            or settings.opennode_invoice_key
        )
    if not key:
        raise ValueError(
                "cannot initialize OpenNodeWallet: "
                "missing opennode_key or opennode_admin_key or opennode_invoice_key"
        )
    try:
        form_data = await request.body()
        form_data_dict=urllib.parse.parse_qs(form_data.decode('utf-8'))
        payload={key: value[0] for key, value in form_data_dict.items()}
        print(payload)
        received_signature = payload['hashed_order']
        charge_id = payload['id']

        if not received_signature or not charge_id:
            raise HTTPException(status_code=400, detail="Invalid payload")

        if verify_signature(key, charge_id,received_signature):
            # Signature is valid
            await websocket_updater('opennode_ws',payload)

            return {"message": "Webhook Processed"}
        
        else:
            # Signature is invalid
            raise HTTPException(status_code=400, detail="Signature is invalid")
    except Exception as  e:
         print(e)
         raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Unable to process webhook"
        ) 