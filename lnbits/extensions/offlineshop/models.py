import json
from collections import OrderedDict
from quart import url_for
from typing import NamedTuple, Optional
from lnurl import encode as lnurl_encode  # type: ignore
from lnurl.types import LnurlPayMetadata  # type: ignore
from lnurl.models import LnurlPaySuccessAction, UrlAction  # type: ignore


class Shop(NamedTuple):
    id: int
    wallet: str
    wordlist: str

    def get_word(self, payment_hash):
        # initialize confirmation words cache
        self.fulfilled_payments = self.words or OrderedDict()

        if payment_hash in self.fulfilled_payments:
            return self.fulfilled_payments[payment_hash]

        # get a new word
        self.counter = (self.counter or -1) + 1
        wordlist = self.wordlist.split("\n")
        word = [self.counter % len(wordlist)]

        # cleanup confirmation words cache
        to_remove = self.fulfilled_payments - 23
        if to_remove > 0:
            for i in range(to_remove):
                self.fulfilled_payments.popitem(False)

        return word


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
        return lnurl_encode(url_for("offlineshop.lnurl_response", item_id=self.id))

    async def lnurlpay_metadata(self) -> LnurlPayMetadata:
        metadata = [["text/plain", self.description]]

        if self.image:
            metadata.append(self.image.split(","))

        return LnurlPayMetadata(json.dumps(metadata))

    def success_action(self, shop: Shop, payment_hash: str) -> Optional[LnurlPaySuccessAction]:
        if not self.wordlist:
            return None

        return UrlAction(
            url=url_for("offlineshop.confirmation_code", p=payment_hash, _external=True),
            description="Open to get the confirmation code for your purchase.",
        )
