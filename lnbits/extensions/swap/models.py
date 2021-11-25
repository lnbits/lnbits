import json
from typing import Optional

from fastapi.params import Query
from pydantic.main import BaseModel  # type: ignore


class SwapOut(BaseModel):
    id: str
    wallet: str
    onchainwallet: Optional[str]
    onchainaddress: str
    amount: int
    recurrent: bool
    fee: int
    time: int

class CreateSwapOut(BaseModel):
    wallet: str = Query(...)
    onchainwallet: str = Query(None)
    onchainaddress: str = Query(...)
    amount: int = Query(..., ge=1) #I'd set a minimum amount to prevent dust 1000/5000 ??
    recurrent: bool = Query(False)
    fee: int = Query(..., ge=1)



# class CreateDomain(BaseModel):
#     wallet: str = Query(...) 
#     domain: str = Query(...)
#     cf_token: str = Query(...)
#     cf_zone_id: str = Query(...)
#     webhook: str = Query(None)
#     cost: int = Query(..., ge=0)

# class Domains(BaseModel):
#     id: str
#     wallet: str
#     domain: str
#     cf_token: str
#     cf_zone_id: str
#     webhook: str
#     cost: int
#     time: int

# class CreateAddress(BaseModel):
#     domain: str = Query(...)
#     username: str = Query(...)
#     email: str = Query(None)
#     wallet_endpoint: str = Query(...)
#     wallet_key: str = Query(...)
#     sats: int = Query(..., ge=0)
#     duration: int = Query(..., ge=1)

# class Addresses(BaseModel):
#     id: str
#     wallet: str
#     domain: str
#     email: str
#     username: str
#     wallet_key: str
#     wallet_endpoint: str
#     sats: int
#     duration: int
#     paid: bool
#     time: int

#     async def lnurlpay_metadata(self) -> LnurlPayMetadata:
#         text = f"Payment to {self.username}"
#         metadata = [["text/plain", text]]

#         return LnurlPayMetadata(json.dumps(metadata))
