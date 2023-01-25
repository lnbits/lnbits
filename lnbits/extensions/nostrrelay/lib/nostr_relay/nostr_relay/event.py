"""
forked from https://github.com/jeffthibault/python-nostr.git
"""
import functools
import time
from enum import IntEnum
from secp256k1 import PrivateKey, PublicKey
from hashlib import sha256

try:
    import rapidjson
    loads = rapidjson.loads
    dumps = functools.partial(rapidjson.dumps, ensure_ascii=False)
except ImportError:
    import json
    loads = json.loads
    dumps = functools.partial(json.dumps, separators=(',', ':'), ensure_ascii=False)


class EventKind(IntEnum):
    SET_METADATA = 0
    TEXT_NOTE = 1
    RECOMMEND_RELAY = 2
    CONTACTS = 3
    ENCRYPTED_DIRECT_MESSAGE = 4
    DELETE = 5

class Event:
    def __init__(
            self,
            pubkey: str='', 
            content: str='', 
            created_at: int=int(time.time()), 
            kind: int=EventKind.TEXT_NOTE, 
            tags: "list[list[str]]"=[], 
            id: str=None,
            sig: str=None) -> None:
        if not isinstance(content, str):
            raise TypeError("Argument 'content' must be of type str")
        
        if not id:
            id = Event.compute_id(pubkey, created_at, kind, tags, content)
        self.id = id
        self.pubkey = pubkey
        self.content = content
        self.created_at = created_at
        self.kind = kind
        self.tags = tags
        self.sig = sig

    @property
    def id_bytes(self):
        return bytes.fromhex(self.id)

    @property
    def is_ephemeral(self):
        return self.kind >= 20000 and self.kind < 30000

    @property
    def is_replaceable(self):
        return self.kind >= 10000 and self.kind < 20000

    @property
    def is_paramaterized_replaceable(self):
        return self.kind >= 30000 and self.kind < 40000

    @staticmethod
    def serialize(public_key: str, created_at: int, kind: int, tags: "list[list[str]]", content: str) -> bytes:
        data = [0, public_key, created_at, kind, tags, content]
        data_str = dumps(data)
        return data_str.encode()

    @staticmethod
    def compute_id(public_key: str, created_at: int, kind: int, tags: "list[list[str]]", content: str) -> str:
        return sha256(Event.serialize(public_key, created_at, kind, tags, content)).hexdigest()

    @staticmethod
    def from_tuple(row):
        tags = row[4]
        if isinstance(tags, str):
            tags = loads(tags)
        return Event(
            id=row[0].hex(),
            created_at=row[1],
            kind=row[2],
            pubkey=row[3].hex(),
            tags=tags,
            sig=row[5].hex(),
            content=row[6],
        )

    def sign(self, private_key_hex: str) -> None:
        sk = PrivateKey(bytes.fromhex(private_key_hex))
        sig = sk.schnorr_sign(bytes.fromhex(self.id), None, raw=True)
        self.sig = sig.hex()

    def verify(self) -> bool:
        try:
            pub_key = PublicKey(bytes.fromhex("02" + self.pubkey), True) # add 02 for schnorr (bip340)
        except Exception as e:
            return False
        event_id = Event.compute_id(self.pubkey, self.created_at, self.kind, self.tags, self.content)
        verified = pub_key.schnorr_verify(bytes.fromhex(event_id), bytes.fromhex(self.sig), None, raw=True)
        for tag in self.tags:
            if tag[0] == 'delegation':
                # verify delegation signature
                _, delegator, conditions, sig = tag
                to_sign = (':'.join(['nostr', 'delegation', self.pubkey, conditions])).encode('utf8')
                delegation_verified = PublicKey(
                    bytes.fromhex("02" + delegator),
                    True
                ).schnorr_verify(
                    sha256(to_sign).digest(),
                    bytes.fromhex(sig),
                    None,
                    raw=True
                )
                if not delegation_verified:
                    return False
        return verified

    def to_tuple(self):
        return (
            self.id,
            self.pubkey,
            self.created_at,
            self.kind,
            dumps(self.tags),
            self.content,
            self.sig
        )

    def __str__(self):
        return dumps(self.to_json_object())

    def to_json_object(self) -> dict:
        return {
            "id": self.id,
            "pubkey": self.pubkey,
            "created_at": self.created_at,
            "kind": self.kind,
            "tags": self.tags,
            "content": self.content,
            "sig": self.sig
        }
