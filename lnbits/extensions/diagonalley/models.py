from urllib.parse import urlparse, urlunparse, parse_qs, urlencode, ParseResult
from starlette.requests import Request
from fastapi.param_functions import Query
from typing import Optional, Dict
from lnbits.lnurl import encode as lnurl_encode  # type: ignore
from lnurl.types import LnurlPayMetadata  # type: ignore
from pydantic import BaseModel
import json
from sqlite3 import Row


class Stalls(BaseModel):
    id: str = Query(None)
    wallet: str = Query(None)
    name: str = Query(None)
    publickey: str = Query(None)
    privatekey: str = Query(None)
    relays: str = Query(None)

class createStalls(BaseModel):
    wallet: str = Query(None)
    name: str = Query(None)
    publickey: str = Query(None)
    privatekey: str = Query(None)
    relays: str = Query(None)
    shippingzones: str = Query(None)

class Products(BaseModel):
    id: str = Query(None)
    stall: str = Query(None)
    product: str = Query(None)
    categories: str = Query(None)
    description: str = Query(None)
    image: str = Query(None)
    price: int = Query(0)
    quantity: int = Query(0)


class Zones(BaseModel):
    id: str = Query(None)
    wallet: str = Query(None)
    cost: str = Query(None)
    countries: str = Query(None)


class Orders(BaseModel):
    id: str = Query(None)
    productid: str = Query(None)
    stall: str = Query(None)
    product: str = Query(None)
    quantity: int = Query(0)
    shippingzone: int = Query(0)
    address: str = Query(None)
    email: str = Query(None)
    invoiceid: str = Query(None)
    paid: bool
    shipped: bool
