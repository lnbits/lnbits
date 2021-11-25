from typing import List, Optional, Union

from lnbits.core.services import pay_invoice

from . import db
from .models import CreateSwapOut, SwapOut


#SWAP OUT
async def get_swapouts(wallet_ids: Union[str, List[str]]) -> List[SwapOut]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM swap.out WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [SwapOut(**row) for row in rows]
