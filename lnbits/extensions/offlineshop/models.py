import json
from collections import OrderedDict
from quart import url_for
from typing import NamedTuple, Optional, List
from lnurl import encode as lnurl_encode  # type: ignore
from lnurl.types import LnurlPayMetadata  # type: ignore
from lnurl.models import LnurlPaySuccessAction, UrlAction  # type: ignore

shop_counters = {}


class ShopCounter(object):
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
            for i in range(to_remove):
                self.fulfilled_payments.popitem(False)

        return word


class Shop(NamedTuple):
    id: int
    wallet: str
    wordlist: str

    def get_word(self, payment_hash):
        sc = ShopCounter.invoke(self)
        return sc.get_word(payment_hash)


class Item(NamedTuple):
    shop: int
    id: int
    name: str
    description: str
    image: str
    enabled: bool
    price: int
    unit: str

    @property
    def lnurl(self) -> str:
        return lnurl_encode(url_for("offlineshop.lnurl_response", item_id=self.id, _external=True))

    def values(self):
        values = self._asdict()
        values["lnurl"] = self.lnurl
        return values

    async def lnurlpay_metadata(self) -> LnurlPayMetadata:
        metadata = [["text/plain", self.description]]

        if self.image:
            metadata.append(self.image.split(":")[1].split(","))

        return LnurlPayMetadata(json.dumps(metadata))

    def success_action(self, shop: Shop, payment_hash: str) -> Optional[LnurlPaySuccessAction]:
        if not shop.wordlist:
            return None

        return UrlAction(
            url=url_for("offlineshop.confirmation_code", p=payment_hash, _external=True),
            description="Open to get the confirmation code for your purchase.",
        )
