
from .crud import get_cashu
from .mint_helper import derive_keys, derive_pubkeys


def get_pubkeys(xpriv: str):
    """Returns public keys for possible amounts."""
    
    keys = derive_keys(xpriv)
    pub_keys = derive_pubkeys(keys)

    return {a: p.serialize().hex() for a, p in pub_keys.items()}