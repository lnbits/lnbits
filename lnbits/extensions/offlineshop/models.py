import base64
import hashlib
import json
from collections import OrderedDict
from sqlite3 import Row
from typing import Dict, List, Optional

from lnurl import encode as lnurl_encode
from lnurl.models import ClearnetUrl, Max144Str, UrlAction
from lnurl.types import LnurlPayMetadata
from pydantic import BaseModel
from starlette.requests import Request

from .helpers import totp

shop_counters: Dict = {}


class ShopCounter:
    wordlist: List[str]
    fulfilled_payments: OrderedDict
    counter: int

    @classmethod
    def invoke(cls, shop: "Shop"):
        shop_counter = shop_counters.get(shop.id)
        if not shop_counter:
            shop_counter = cls(wordlist=shop.wordlist.split("\n"))
            shop_counters[shop.id] = shop_counter
        return shop_counter

    @classmethod
    def reset(cls, shop: "Shop"):
        shop_counter = cls.invoke(shop)
        shop_counter.counter = -1
        shop_counter.wordlist = shop.wordlist.split("\n")

    def __init__(self, wordlist: List[str]):
        self.wordlist = wordlist
        self.fulfilled_payments = OrderedDict()
        self.counter = -1

    def get_word(self, payment_hash):
        if payment_hash in self.fulfilled_payments:
            return self.fulfilled_payments[payment_hash]

        # get a new word
        self.counter += 1
        word = self.wordlist[self.counter % len(self.wordlist)]
        self.fulfilled_payments[payment_hash] = word

        # cleanup confirmation words cache
        to_remove = len(self.fulfilled_payments) - 23
        if to_remove > 0:
            for _ in range(to_remove):
                self.fulfilled_payments.popitem(False)

        return word


class Shop(BaseModel):
    id: int
    wallet: str
    method: str
    wordlist: str

    @classmethod
    def from_row(cls, row: Row):
        return cls(**dict(row))

    @property
    def otp_key(self) -> str:
        return base64.b32encode(
            hashlib.sha256(
                ("otpkey" + str(self.id) + self.wallet).encode("ascii")
            ).digest()
        ).decode("ascii")

    def get_code(self, payment_hash: str) -> str:
        if self.method == "wordlist":
            sc = ShopCounter.invoke(self)
            return sc.get_word(payment_hash)
        elif self.method == "totp":
            return totp(self.otp_key)
        return ""


class Item(BaseModel):
    shop: int
    id: int
    name: str
    description: str
    image: Optional[str]
    enabled: bool
    price: float
    unit: str
    fiat_base_multiplier: int

    @classmethod
    def from_row(cls, row: Row) -> "Item":
        data = dict(row)
        if data["unit"] != "sat" and data["fiat_base_multiplier"]:
            data["price"] /= data["fiat_base_multiplier"]
        return cls(**data)

    def lnurl(self, req: Request) -> str:
        return lnurl_encode(req.url_for("offlineshop.lnurl_response", item_id=self.id))

    def values(self, req: Request):
        values = self.dict()
        values["lnurl"] = lnurl_encode(
            req.url_for("offlineshop.lnurl_response", item_id=self.id)
        )
        return values

    async def lnurlpay_metadata(self) -> LnurlPayMetadata:
        metadata = [["text/plain", self.description]]

        if self.image:
            metadata.append(self.image.split(":")[1].split(","))

        return LnurlPayMetadata(json.dumps(metadata))

    def success_action(
        self, shop: Shop, payment_hash: str, req: Request
    ) -> Optional[UrlAction]:
        if not shop.wordlist:
            return None

        return UrlAction(
            url=ClearnetUrl(
                req.url_for("offlineshop.confirmation_code", p=payment_hash),
                scheme="https",
            ),
            description=Max144Str(
                "Open to get the confirmation code for your purchase."
            ),
        )
