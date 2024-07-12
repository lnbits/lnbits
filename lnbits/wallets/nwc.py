import asyncio
import hashlib
import json
from typing import AsyncGenerator, Dict, Optional
import secp256k1
from loguru import logger
from urllib.parse import urlparse, parse_qs, unquote
from lnbits.settings import settings
import time
from .base import (
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    PaymentFailedStatus,
    StatusResponse,
    Wallet,
)
import websockets
from Cryptodome import Random
from Cryptodome.Cipher import AES
import base64
import random
from typing import Union
 
class NWCWallet(Wallet):
    """
    A funding source that connects to a Nostr Wallet Connect (NWC) service provider. 
    https://nwc.dev/
    """

    def _parse_nwc(self, nwc) -> Dict:
        """
        Parses a Nostr Wallet Connect URL (nostr+walletconnect://...) and extracts relevant information.

        Args:
            nwc (str): The Nostr Wallet Connect URL to be parsed.

        Returns:
            Dict[str, str]: A dictionary containing the extracted information:'pubkey', 'relay', and 'secret'. 
            If the URL is invalid, an exception is raised.

        Example:
            >>> _parse_nwc("nostr+walletconnect://000000...000000?relay=example.com&secret=123")
            {'pubkey': '000000...000000', 'relay': 'example.com', 'secret': '123'}
        """
        data = {}
        prefix = "nostr+walletconnect://"
        if nwc and nwc.startswith(prefix):
            nwc = nwc[len(prefix):]
            parsed_url = urlparse(nwc)
            data['pubkey'] = parsed_url.path
            query_params = parse_qs(parsed_url.query)
            for key, value in query_params.items():
                if key in ["relay", "secret"] and value:
                    data[key] = unquote(value[0])
            if "pubkey" not in data or "relay" not in data or "secret" not in data:
                raise ValueError("Invalid NWC pairing url")
        else:
            raise ValueError("Invalid NWC pairing url")
        return data


    def __init__(self):
        # Parse pairing url (if invalid an exception is raised)
        nwc_data = self._parse_nwc(settings.nwc_pairing_url)
       
        # Extract account keys (used to sign nwc events and identify the holder of the nwc account)
        self.account_private_key = secp256k1.PrivateKey(bytes.fromhex(nwc_data["secret"]))
        self.account_private_key_hex = nwc_data["secret"]
        self.account_public_key = self.account_private_key.pubkey
        self.account_public_key_hex = self.account_public_key.serialize().hex()[2:]

        # Extract service key (used for message encryption and to identify the nwc service provider)
        self.service_pubkey = secp256k1.PublicKey(bytes.fromhex("02" + nwc_data["pubkey"]), True)          
        self.service_pubkey_hex = nwc_data["pubkey"]

        # Extract relay url
        self.relay = nwc_data["relay"]
        
        # nwc events create temporary subscriptions that are stored until the response is received or the timeout expires
        self.subscriptions = {} 
        # Timeout in seconds after which a subscription is closed if no response is received
        self.subscription_timeout = 10 
        # Incremental counter to generate unique subscription ids for the connection
        self.subscriptions_count=0

        # websocket connection
        self.ws = None 
        # if True the websocket is connected
        self.connected = False
        # if True the wallet is shutting down
        self.shutdown = False 

        # cached info about the service provider
        self.info=None 

        # This task handles connection and reconnection to the relay
        self.connection_task = asyncio.create_task(self._connect_to_relay())       
        
        # This task periodically checks if any subscriptions have timed out, and closes them.
        self.subscription_timeout_task = asyncio.create_task(self._handle_subscription_timeout())

        logger.info("NWCWallet is ready. relay: "+self.relay+" account: "+self.account_public_key_hex+" service: "+self.service_pubkey_hex)


    def _json_dumps(self, data: Union[Dict,list]) -> str:
        """
        Converts a Python dictionary to a JSON string with compact encoding.

        Args:
            data (Dict): The dictionary to be converted.
        
        Returns:
            str: The compact JSON string.
        """
        if isinstance(data, Dict):
            data = {k: v for k, v in data.items() if v is not None}
        return json.dumps(data, separators=(',', ':'), ensure_ascii=False)   


    def _is_shutting_down(self) -> bool:
        """
        Returns True if the wallet is shutting down.
        """
        return self.shutdown or not settings.lnbits_running


    async def _send(self,data: Dict):
        """
        Sends data to the NWC relay.

        Args:
            data (Dict): The data to be sent.
        """
        if self._is_shutting_down():
            logger.warning("Trying to send data while shutting down")
            return
        await self._wait_for_connection() # ensure the connection is established
        tx = self._json_dumps(data)
        await self.ws.send(tx)


    def _get_new_subid(self) -> str:
        """
        Generates a unique subscription id.

        Returns:
            str: The generated 64 characters long subscription id (eg. lnbits0abc...)
        """
        subid="lnbits"+str(self.subscriptions_count)
        self.subscriptions_count+=1
        maxLength = 64
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        n = maxLength - len(subid)
        if n>0:
            for i in range(n):
                subid += chars[random.randint(0, len(chars) - 1)]
        return subid        


    async def _close_subscription_by_subid(self, sub_id:str, sendEvent:bool = True) -> Dict:
        """
        Closes a subscription by its sub_id.

        Args:
            sub_id (str): The subscription id.
            sendEvent (bool): If True, sends a CLOSE event to the relay.

        Returns:
            Dict: The subscription that was closed.
        """
        logger.debug("Closing subscription "+sub_id)
        sub_to_close = None
        for subscription in self.subscriptions.values():
            if subscription["sub_id"] == sub_id:
                sub_to_close = subscription
                # send CLOSE event to the relay if the subscription is not already closed and sendEvent is True
                if not subscription["closed"] and sendEvent: 
                    await self._send(["CLOSE", sub_id])
                # mark as closed
                subscription["closed"] = True
                break
        # remove the subscription from the list
        if sub_to_close:
            self.subscriptions.pop(sub_to_close["event_id"], None)
        return sub_to_close


    async def _close_subscription_by_eventid(self, event_id, sendEvent = True) -> Dict:
        """
        Closes a subscription associated to an event_id.

        Args:
            event_id (str): The event id associated to the subscription.
            sendEvent (bool): If True, sends a CLOSE event to the relay.
        
        Returns:
            Dict: The subscription that was closed.
        """
        logger.debug("Closing subscription for event "+event_id)
        # find and remove the subscription
        subscription = self.subscriptions.pop(event_id, None)
        if subscription:
            # send CLOSE event to the relay if the subscription is not already closed and sendEvent is True
            if not subscription["closed"] and sendEvent:
                await self._send(["CLOSE", subscription["sub_id"]])
            # mark as closed
            subscription["closed"] = True
        return subscription

   
    async def _wait_for_connection(self):
        """
        Waits until the wallet is connected to the relay.
        """
        while not self.connected:
            if self._is_shutting_down():
                raise Exception("Connection is closing")
            logger.debug("Waiting for connection...")
            await asyncio.sleep(1)


    async def _handle_subscription_timeout(self): 
        """
        Periodically checks if any subscriptions have timed out, and closes them.
        """
        try:
            while not self._is_shutting_down(): 
                try:       
                    await asyncio.sleep(int(self.subscription_timeout*0.5)) 
                    # skip if connection is not established
                    if not self.connected:
                        continue
                    # Find all subscriptions that have timed out
                    now = time.time()
                    subscriptions_to_close = []
                    for subscription in self.subscriptions.values():
                        t = now - subscription["timestamp"]
                        if t > self.subscription_timeout:
                            logger.warning("Subscription "+subscription["sub_id"]+" timed out")
                            subscriptions_to_close.append(subscription["sub_id"])
                            # if not already closed, pass the "time out" exception to the future
                            if not subscription["closed"]:
                                subscription["future"].set_exception(Exception("timed out"))                    
                    # Close all timed out subscriptions
                    for sub_id in subscriptions_to_close:
                        await self._close_subscription_by_subid(sub_id)
                except Exception as e:
                    logger.error("Error handling subscription timeout: "+str(e))
        except Exception as e:
            logger.error("Error handling subscription timeout: "+str(e))

 
    async def _on_message(self, ws, message: str):
        """
        Handle incoming messages from the relay.
        """
        try:
            msg = json.loads(message)
            if msg[0] == "OK": # Event status message
                event_id = msg[1]
                status = msg[2]
                info = msg[3] or ""               
                if not status:
                    # close subscription and pass an exception if the event was rejected by the relay
                    subscription = await self._close_subscription_by_eventid(event_id)
                    if subscription: # Check if the subscription exists first
                        subscription["future"].set_exception(Exception(info))
            elif msg[0] == "EVENT": # Event message
                sub_id = msg[1]
                event = msg[2]
                if not self._verify_event(event): # Ensure the event is valid (do not trust relays)
                    raise Exception("Invalid event signature")
                tags = event["tags"]
                if event["kind"] == 13194: # An info event
                    # info events are handled specially, they are stored in the subscriptions list
                    # using the subscription id for both sub_id and event_id 
                    subscription = await self._close_subscription_by_eventid(sub_id) # sub_id is the event_id for info events
                    if subscription: # Check if the subscription exists first
                        if subscription["method"] != "info_sub": # Ensure the subscription is for an info event
                            raise Exception("Unexpected info event")
                        # create an info dictionary with the supported methods that is passed to the future
                        content = event["content"]
                        subscription["future"].set_result({
                            "supported_methods": content.split(" ")
                        })
                else: # A response event
                    subscription = None
                    # find the first "e" tag that is handled by a registered subscription
                    # Note: usually we expect only one "e" tag, but we are handling multiple "e" tags just in case
                    for tag in tags:
                        if tag[0] == "e":
                            subscription = await self._close_subscription_by_eventid(tag[1])
                            if subscription:
                                break
                    # if a subscription was found, pass the result to the future
                    if subscription:
                        content = self._decrypt_content(event["content"])
                        content = json.loads(content)
                        result_type = content.get("result_type","")
                        error = content.get("error", None)
                        result = content.get("result", None)
                        if result_type != subscription["method"]: # ensure the result is for the expected method
                            raise Exception("Unexpected result type")
                        if error: # if an error occurred, pass the error to the future
                            subscription["future"].set_exception(Exception(error["code"]+" "+error["message"]))
                        else:
                            if not result: 
                                raise Exception("Malformed response")
                            else:
                                subscription["future"].set_result(result)
            elif msg[0] == "EOSE":
                # Do nothing. No need to handle this message type for NWC
                pass
            elif msg[0] == "CLOSED":
                # Subscription was closed remotely.
                # The change is reflected in the subscriptions list.
                sub_id = msg[1]
                info = msg[2] or ""
                if info:
                    logger.warning("Subscription "+sub_id+" closed remotely: "+info)
                # Note: sendEvent=false because the action was initiated by the relay
                await self._close_subscription_by_subid(sub_id, sendEvent=False) 
            elif msg[0] == "NOTICE":
                # A message from the relay, mostly useless, but we log it anyway
                logger.info("Notice from relay "+self.relay+": "+str(msg[1]))
            else:
                raise Exception("Unknown message type")
        except Exception as e:
            logger.error("Error parsing event: "+str(e))
  

    async def _connect_to_relay(self):      
        """
        Initiate websocket connection to the relay.
        """        
        logger.debug("Connecting to NWC relay "+self.relay)        
        while not self._is_shutting_down(): # Reconnect until the wallet is shutting down
            logger.debug('Creating new connection...')
            try:
                async with websockets.connect(self.relay) as ws:
                    self.ws=ws
                    self.connected=True
                    while not self._is_shutting_down(): # receive messages until the wallet is shutting down
                        try:
                            reply = await ws.recv()
                            await self._on_message(ws, reply)
                        except Exception as e:
                            logger.debug("Error receiving message: " + str(e))
                            break
                logger.debug("Connection to NWC relay closed")
            except Exception as e:
                logger.error("Error connecting to NWC relay: "+str(e))
            # the connection was closed, so we set the connected flag to False
            # this will make the methods calling _wait_for_connection() to wait until the connection is re-established
            self.connected=False
            if not self._is_shutting_down():
                # Wait some time before reconnecting
                logger.debug("Reconnecting to NWC relay in 5 seconds...")
                await asyncio.sleep(5)
                    

    def _encrypt_content(self, content:str) -> str:
        """
        Encrypts the content to be sent to the service.

        Args:
            content (str): The content to be encrypted.

        Returns:
            str: The encrypted content.
        """       
        shared = self.service_pubkey.tweak_mul(bytes.fromhex(self.account_private_key_hex)).serialize()[1:]
        # random iv (16B)
        iv = Random.new().read( AES.block_size )
        aes = AES.new(shared, AES.MODE_CBC, iv)
        # padding        
        pad = lambda s: s + (16 - len(s) % 16) * chr(16 - len(s) % 16)
        content = pad(content).encode("utf-8")        
        # Encrypt
        encryptedB64 = base64.b64encode(aes.encrypt(content)).decode("ascii")
        ivB64 = base64.b64encode(iv).decode("ascii")
        encryptedContent =  encryptedB64 + "?iv=" + ivB64
        return encryptedContent
    

    def _decrypt_content(self, content:str) -> str:
        """
        Decrypts the content coming from the service.

        Args:
            content (str): The encrypted content.

        Returns:
            str: The decrypted content.
        """
        shared = self.service_pubkey.tweak_mul(bytes.fromhex(self.account_private_key_hex)).serialize()[1:]
        # extract iv and content
        (encryptedContentB64, ivB64) = content.split("?iv=")
        encryptedContent = base64.b64decode(encryptedContentB64.encode("ascii"))
        iv = base64.b64decode(ivB64.encode("ascii"))        
        # Decrypt
        aes = AES.new(shared, AES.MODE_CBC, iv)
        decrypted = aes.decrypt(encryptedContent).decode("utf-8")
        unpad = lambda s : s[:-ord(s[len(s)-1:])]
        return unpad(decrypted)


    def _verify_event(self, event:Dict) -> bool:
        """
        Signs the event (in place) with the service secret

        Args:
            event (Dict): The event to be signed.

        Returns:
            Dict: The input event with the signature added.
        """
        signature_data=self._json_dumps([
            0,
            event["pubkey"],
            event["created_at"],
            event["kind"],
            event["tags"],
            event["content"]
        ])
        event_id = hashlib.sha256(signature_data.encode()).hexdigest()
        if event_id != event["id"]: # Invalid event id
            return False
        pubkeyHex = event["pubkey"]
        pubkey = secp256k1.PublicKey(bytes.fromhex("02" + pubkeyHex), True)
        if not pubkey.schnorr_verify(bytes.fromhex(event_id), bytes.fromhex(event["sig"]), None, raw=True):
            return False
        return True


    def _sign_event(self, event:Dict) -> Dict:
        """
        Signs the event (in place) with the service secret

        Args:
            event (Dict): The event to be signed.

        Returns:
            Dict: The input event with the signature added.
        """
        signature_data=self._json_dumps([
            0,
            self.account_public_key_hex,
            event["created_at"],
            event["kind"],
            event["tags"],
            event["content"]
        ])

        event_id = hashlib.sha256(signature_data.encode()).hexdigest()
        event["id"] = event_id
        event["pubkey"] = self.account_public_key_hex

        signature = (self.account_private_key.schnorr_sign( bytes.fromhex(event_id), None, raw=True)).hex()   
        event["sig"] = signature
        return event


    async def _call(self, method:str, params:Dict) -> Dict:
        """
        Call a NWC method.

        Args:
            method (str): The method name.
            params (Dict): The method parameters.

        Returns:
            Dict: The result of the method call.
        """
        await self._wait_for_connection()        
        logger.debug("Calling "+method+" with params: "+str(params))
        # Prepare the content
        content = self._json_dumps({
            "method": method,
            "params": params,
        })
        # Encrypt
        content = self._encrypt_content(content)
        # Prepare the NWC event
        event = {
            "kind": 23194,
            "content": content,
            "created_at": int(time.time()),
            "tags":[
                ["p", self.service_pubkey_hex]
            ]
        }
        # Sign
        self._sign_event(event)        
        # Subscribe for a response to this event
        sub_filter = {
            "kinds":[23195],
            "#p":[self.account_public_key_hex],
            "#e":[event["id"]],
            "since": int(time.time())
        }
        sub_id = self._get_new_subid()         
        # register a future to receive the response asynchronously
        future = asyncio.get_event_loop().create_future()
        # Check if the subscription already exists (this means there is a bug somewhere, should not happen)
        if event["id"] in self.subscriptions: 
            raise Exception("Subscription for this event id already exists?")        
        # Store the subscription in the list
        self.subscriptions[event["id"]] = {
            "method": method,
            "future": future,
            "sub_id": sub_id,
            "event_id": event["id"],
            "timestamp": time.time(),
            "closed": False
        }
        # Send the events
        await self._send(["REQ", sub_id, sub_filter])
        await self._send(["EVENT",  event])
        # Wait for the response       
        return await future


    async def _get_info(self) -> Dict:
        """
        Get the info about the service provider and cache it.

        Returns:
            Dict: The info about the service provider.        
        """
        if not self.info: # if not cached
            try:                
                await self._wait_for_connection()
                # Prepare filter to request the info note
                sub_filter = {
                    "kinds":[13194],
                    "authors":[self.service_pubkey_hex]
                }
                # We register a special subscription using the sub_id as the event_id
                sub_id = self._get_new_subid()
                future = asyncio.get_event_loop().create_future()
                self.subscriptions[sub_id] = {
                    "method": "info_sub",
                    "future": future,
                    "sub_id": sub_id,
                    "event_id": sub_id,
                    "timestamp": time.time(),
                    "closed": False
                }
                # Send the request
                await self._send(["REQ", sub_id, sub_filter])
                # Wait for the response
                self.info = await future # cache
            except Exception as e: 
                logger.error("Error getting info: "+str(e))
                # The error could mean that the service provider does not provide an info note
                # So we just assume it supports the bare minimum to be Nip47 compliant
                self.info={ 
                    "supported_methods":[
                        "pay_invoice"
                    ],
                }
        return self.info


    async def cleanup(self):
        logger.debug("Closing NWCWallet connection")
        self.shutdown = True # Mark for shutdown
        # cancel all tasks
        try: 
            self.subscription_timeout_task.cancel()
        except Exception as e:
            logger.warning("Error cancelling subscription timeout task: "+str(e))       
        try:
            self.connection_task.cancel()
        except Exception as e:
            logger.warning("Error cancelling connection task: "+str(e))
        # close the websocket
        try:
            await self.ws.close()
        except Exception as e:
            logger.warning("Error closing wallet connection: "+str(e))

        
    async def create_invoice(self,   
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs
    ) -> InvoiceResponse:                
        desc = ""
        desc_hash = None
        if description_hash:
            desc_hash = description_hash.hex()
            desc = unhashed_description or ""
        elif unhashed_description:
            desc = unhashed_description.decode()
            desc_hash = hashlib.sha256(desc.encode()).hexdigest()
        else:
            desc = memo
        try:
            info = await self._get_info()
            if not "make_invoice" in info["supported_methods"]:
                return InvoiceResponse(None, None, None, "make_invoice is not supported by this NWC service.")            
            resp = await self._call("make_invoice",{
                "amount": int(amount*1000), # nwc uses msats denominations
                "description_hash": desc_hash,
                "description": desc
            })
            checking_id = str(resp["payment_hash"])
            payment_request = resp.get("invoice", None)
            return InvoiceResponse(True, checking_id, payment_request, None)
        except Exception as e:
            return InvoiceResponse(ok=False, error_message=str(e) )


    async def status(self) -> StatusResponse:
        try:
            info = await self._get_info()
            if not "get_balance" in info["supported_methods"]:
                logger.debug("get_balance is not supported by this NWC service.")
                return StatusResponse(None, 0)            
            resp = await self._call("get_balance",{})
            balance = int(resp["balance"])
            return StatusResponse(None, balance)
        except Exception as e:
            return StatusResponse(str(e), 0)


    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        try:
            resp = await self._call("pay_invoice", {
                "invoice": bolt11            
            })
            preimage = str(resp["preimage"])
            # pay_invoice doesn't return payment data, so we need to call lookup_invoice too (if supported)
            info = await self._get_info()
            if "lookup_invoice" in info["supported_methods"]:
                payment_data = await self._call("lookup_invoice",{
                    "invoice": bolt11
                })
                settled = "preimage" in payment_data 
                checking_id = str(payment_data["payment_hash"])
                if not settled:
                    return PaymentResponse(None, checking_id, None, None, None)
                else:
                    fee_msat = int(payment_data["fees_paid"])
                    return PaymentResponse(True, checking_id, fee_msat, preimage, None)
            else: # if not supported, we compute the payment_hash
                preimage_byte = bytes.fromhex(preimage)
                payment_hash = hashlib.sha256(preimage_byte).hexdigest()
                return PaymentResponse(True, payment_hash, None, preimage, None)

        except Exception as e:
            return PaymentResponse(ok=False, error_message=str(e))


    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        return await self.get_payment_status(checking_id)


    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        try:
            info = await self._get_info()
            if "lookup_invoice" in info["supported_methods"]:
                payment_data = await self._call("lookup_invoice",{
                    "payment_hash": checking_id
                })
                settled = "settled_at" in payment_data and int(payment_data["settled_at"]) > 0 and "preimage" in payment_data
                fee_msat = int(payment_data["fees_paid"])
                preimage = payment_data.get("preimage", None)
                return PaymentStatus(True if settled else None, fee_msat=fee_msat, preimage=preimage)
            else:
                return PaymentStatus(None, fee_msat=None, preimage=None)
        except Exception as e:
            logger.error("Error getting payment status: "+str(e))
            return PaymentFailedStatus()


    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        self.queue: asyncio.Queue = asyncio.Queue(0)
        while not self._is_shutting_down():
            value = await self.queue.get()
            yield value

