from array import array
from typing import Any, Optional, List
import httpx
from http import HTTPStatus
from starlette.exceptions import HTTPException
import json
from pydantic import BaseModel, parse_obj_as
from os import getenv


class StrikeCurrency(BaseModel):
    currency: str
    isDefaultCurrency: bool
    isAvailable: bool

class StrikeProfile(BaseModel):
    handle: str
    description: Optional[str]
    canReceive: bool
    currencies: List[StrikeCurrency]

class StrikeRate(BaseModel):
    amount: float
    sourceCurrency: str
    targetCurrency: str

class StrikeAmount(BaseModel):
    amount: float
    currency: str

class StrikeQuote(BaseModel):
    quoteId: str
    description: str
    lnInvoice: str
    targetAmount: StrikeAmount
    sourceAmount: StrikeAmount
    conversionRate: StrikeRate

class StrikeApiClient():

    def __init__(self):
        endpoint = getenv("STRIKE_API_ENDPOINT") or "https://api.strike.me"
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint

        self.api_key = getenv("STRIKE_API_KEY")
        self.headers = {
            'accept': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    async def get_profile(self, handle: str) -> StrikeProfile:
        async with httpx.AsyncClient() as client:
            r = await client.get(f'{self.endpoint}/v1/accounts/handle/{handle}/profile', headers=self.headers)
            if(r.status_code == 404):
                raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=f"Strike account with handle '{handle}' doesn't exist")
            self.throw_on_400(r) 
        try:
            data = StrikeProfile(**r.json())
            return data
        except Exception as e:
            self.throw_bad_request(f"Failed to load Strike profile, error: '{str(e)}'")

    async def get_tickers(self) -> List[StrikeRate]:
        async with httpx.AsyncClient() as client:
            r = await client.get(f'{self.endpoint}/v1/rates/ticker', headers=self.headers)
            self.throw_on_400(r)
        try:
            data = parse_obj_as(List[StrikeRate], r.json())
            return data
        except Exception as e:
            self.throw_bad_request(f"Failed to load Strike tickers, error: '{str(e)}'")

    async def issue_invoice(self, handle: str, amount: float, currency: str, description: str) -> str:
        invoice_request = {
            'description': description, 
            'amount': {
                'currency': currency,
                'amount': str(amount)
            }
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(f'{self.endpoint}/v1/invoices/handle/{handle}', json=invoice_request, headers=self.headers)
            self.throw_on_400(r) 
        try:
            data = r.json()
            return data['invoiceId']
        except Exception as e:
            self.throw_bad_request(f"Failed to issue Strike invoice, error: '{str(e)}'")

    async def create_quote(self, invoice_id: str) -> StrikeQuote:
        async with httpx.AsyncClient() as client:
            r = await client.post(f'{self.endpoint}/v1/invoices/{invoice_id}/quote', headers=self.headers)
            self.throw_on_400(r) 
        try:
            data = StrikeQuote(**r.json())
            return data
        except Exception as e:
            self.throw_bad_request(f"Failed to issue Strike quote, error: '{str(e)}'")
    
    def throw_on_400(self, r):
        if(r.status_code >= 400):
            res_json = r.json()['data']
            raise HTTPException(status_code=HTTPStatus(r.status_code), detail=f"Strike error: {res_json['code']} - {res_json['message']}")
    
    def throw_bad_request(self, msg):
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=msg)
