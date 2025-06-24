import httpx
from lnbits.core.views.api import api_lnurlscan
from bech32 import bech32_decode, convertbits
import asyncio
from nostr_sdk import (
    Client,
    Keys,
    PublicKey,
    EventBuilder,
    Kind,
    KindStandard,
    Filter,
    EventId,
    NostrSigner,
    Event,
    SingleLetterTag,
    Alphabet,
    HandleNotification,
)

async def get_pr(ln_address, amount):
    data = await api_lnurlscan(ln_address)
    if data.get("status") == "ERROR":
        return
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url=f"{data['callback']}?amount={amount* 1000}")
            if response.status_code != 200:
                return
            return response.json()["pr"]
    except Exception:
        return None

def decode_key_to_hex(key):
    hrp, data = bech32_decode(key)
    if hrp not in ("npub", "nsec") or data is None:
        raise ValueError(f"Invalid npub/nsec: {key}")
    decoded_bytes = bytes(convertbits(data, 5, 8, False))
    return decoded_bytes.hex()


class NostrHelper:
    def __init__(self, secKey_hex: str, relays: list[str] = None):
        keys = Keys.parse(secKey_hex)
        signer = NostrSigner.keys(keys)
        self.client = Client(signer)
        self.connected = False
        self.signer = signer
        self.my_pubkey = keys.public_key()
        self.relays = relays or [
            "wss://relay.damus.io",
            "wss://relay.snort.social",
            "wss://relay.wine",
        ]

    async def connect(self):
        if not self.connected:
            for relay in self.relays:
                await self.client.add_relay(relay)
            await self.client.connect()
            self.connected = True

    async def post_note(self, content: str) -> str:
        builder = EventBuilder.text_note(content)
        output = await self.client.send_event_builder(builder)
        print(f"[post_note] {output}")
        return str(output)

    async def reply_to_note(self, content: str, note_id: str) -> str:
        builder = EventBuilder.text_note(content)
        output = await self.client.send_event_builder(builder)
        print(f"[post_note] {output}")
        return str(output)

    async def subscribe_mentions(self, pubkey_hex: str, since: int = None):
        filter = (
            Filter()
            .kind(Kind.from_std(KindStandard.TEXT_NOTE))
            .custom_tag(SingleLetterTag.lowercase(Alphabet.P), pubkey_hex)
        )
        if since:
            filter = filter.since(since)
        print("[subscribe_mentions] Subscribing to mentions...")
        await self.client.subscribe(filter, None)

    async def run_subscribe_mentions(self, pubkey_hex: str, handler: HandleNotification, since: int = None):
        await self.subscribe_mentions(pubkey_hex, since)
        await self.run_notifications(handler)

    async def send_dm(self, target_pubkey: str, message: str):
        target = PublicKey.parse(target_pubkey)
        output = await self.client.send_private_msg(target, message, [])
        print(f"[send_dm] {output}")
        return str(output)

    async def subscribe_dms(self, since: int = None):
        combined_filter = (
            Filter()
            .pubkey(self.my_pubkey)
            .kinds([
                Kind.from_std(KindStandard.PRIVATE_DIRECT_MESSAGE),
                Kind(14)
            ])
        )
        if since:
            combined_filter = combined_filter.since(since)

        print("[subscribe_dms] Subscribing to DMs (kind 4 + kind 14)...")
        await self.client.subscribe(combined_filter, None)

    async def run_subscribe_dms(self, handler: HandleNotification, since: int = None):
        await self.subscribe_dms(since)
        await self.run_notifications(handler)

    async def send_zap(self, target_pubkey: str, note_id: str, bolt11_invoice: str, preimage_hex: str):
        builder = EventBuilder.zap_receipt(
            bolt11_invoice,
            preimage_hex,
            PublicKey.parse(target_pubkey),
            EventId.from_hex(note_id),
        )
        output = await self.client.send_event_builder(builder)
        print(f"[send_zap] {output}")
        return str(output)

    async def check_zaps_for_note(self, note_id: str, subscription_id: str = None):
        if not subscription_id:
            subscription_id = f"zaps_{note_id}"
        filter = Filter().kind(Kind(9735)).event(EventId.parse(note_id))
        print(f"[check_zaps_for_note] Subscribing to zap receipts... sub_id={subscription_id}")
        await self.client.subscribe(filter, subscription_id)
        return subscription_id  # return so caller can track it

    async def unsubscribe(self, subscription_id: str):
        print(f"[unsubscribe] {subscription_id}")
        await self.client.unsubscribe(subscription_id)


    async def run_notifications(self, handler: HandleNotification):
        print("[run_notifications] Starting notification handler...")
        await self.client.handle_notifications(handler)

####################################################################
### NOSTR HELPER TESTS (RUN WITH poetry python nostr_helpers.py) ###
####################################################################

if __name__ == "__main__":
    async def main():
        my_nsec = "nsec1e73tpex4re95qrx9tzgyrrzzkfpj9usz8su33j5sumk9yyy2dresy5r98q"
        my_keys = Keys.parse(my_nsec)
        my_secKey_hex = my_keys.secret_key().to_hex()

        their_npub = "npub1c878wu04lfqcl5avfy3p5x83ndpvedaxv0dg7pxthakq3jqdyzcs2n8avm"
        their_pubkey_hex = decode_key_to_hex(their_npub)

        target_note_id = "d0c57bea4a62865547bfe0696dc9a69853138f22ec761631b923f309aba02ea4"

        nh = NostrHelper(secKey_hex=my_secKey_hex)
        await nh.connect()

        class MyHandler(HandleNotification):
            async def handle(self, relay_url, subscription_id, event: Event):
                print(f"[notif] {relay_url} {event.kind()} {event.as_json()}")

            async def handle_msg(self, relay_url, msg):
                pass

        async def send_zap_test():
            invoice = await get_pr("bc@nostr.com", 20)
            preimage = "d3b07384d113edec49eaa6238ad5ff00"  # Replace with real preimage
            await nh.send_zap(their_pubkey_hex, target_note_id, invoice, preimage)

        ############################################
        ##### COMMENT IN/OUT TESTS ACCORDINGLY #####
        ############################################

        # await send_zap_test()
        # await nh.subscribe_mentions(their_pubkey_hex)
        # await nh.run_subscribe_mentions(their_pubkey_hex, MyHandler())

        await nh.post_note("Sent from the bot benarc@nostr.com")

        # await nh.send_dm(their_pubkey_hex, "hello from NostrHelper DM!")
        await nh.check_zaps_for_note(target_note_id)
        await nh.run_subscribe_dms(MyHandler())

    asyncio.run(main())

