from typing import List, Optional

from . import db
from .models import Admin, Funding
from lnbits.helpers import urlsafe_short_hash
from lnbits.core.crud import create_payment
from lnbits.db import Connection

def update_wallet_balance(wallet_id: str, amount: int) -> str:
    temp_id = f"temp_{urlsafe_short_hash()}"
    internal_id = f"internal_{urlsafe_short_hash()}"
    create_payment(
        wallet_id=wallet_id,
        checking_id=internal_id,
        payment_request="admin_internal",
        payment_hash="admin_internal",
        amount=amount * 1000,
        memo="Admin top up",
        pending=False,
    )
    return "success"

async def get_admin(
    user: Optional[str] = None, 
    site_title: Optional[str] = "LNbits",
    tagline: Optional[str] = "Lightning-network wallet/accounts system",
    primary_color: Optional[str] = None, 
    secondary_color: Optional[str] = None,
    allowed_users: Optional[str] = None, 
    default_wallet_name: Optional[str] = None,
    data_folder: Optional[str] = None, 
    disabled_ext: Optional[str] = "amilk",
    force_https: Optional[bool] = True,     
    service_fee: Optional[int] = 0,
    funding_source_primary: Optional[str] = "",
    edited: Optional[str] = "",
    CLightningWallet: Optional[str] =  '',
    LndRestWallet: Optional[str] =  '',
    LndWallet: Optional[str] =  '',
    LntxbotWallet: Optional[str] =  '',
    LNPayWallet: Optional[str] =  '',
    LnbitsWallet: Optional[str] =  '',
    OpenNodeWallet: Optional[str] =  '',
    conn: Optional[Connection] = None,
) -> Optional[Admin]:
    await (conn or db).execute(
        """
        UPDATE admin
        SET user = ?, site_title = ?, tagline = ?, primary_color = ?, secondary_color = ?, allowed_users = ?, default_wallet_name = ?, data_folder = ?, disabled_ext = ?, force_https = ?, service_fee = ?, funding_source = ?
        WHERE 1
        """,
        (
            user,
            site_title,
            tagline,
            primary_color,
            secondary_color,
            allowed_users,
            default_wallet_name,
            data_folder,
            disabled_ext,
            force_https,
            service_fee,
            funding_source_primary,
        ),
    )
    row = await (conn or db).fetchone("SELECT * FROM admin WHERE 1")
    return Admin(**row) if row else None

async def get_funding(
    CLightningWallet: Optional[str] =  '',
    LndRestWallet: Optional[str] =  '',
    LndWallet: Optional[str] =  '',
    LntxbotWallet: Optional[str] =  '',
    LNPayWallet: Optional[str] =  '',
    LnbitsWallet: Optional[str] =  '',
    OpenNodeWallet: Optional[str] =  '',
    conn: Optional[Connection] = None,
    ) -> List[Funding]:
    sources = [CLightningWallet, LndRestWallet, LndWallet, LntxbotWallet, LNPayWallet, LnbitsWallet, OpenNodeWallet]
    for source in sources:
        fsource = ['1','1','1','1','1','1','1','1','1','1']
        tsource = source.split(',')
        num = 0 
        for ttsource in tsource:
            fsource[num] = ttsource
            num = num + 1
        print(fsource)
        if int(fsource[7]) == 1:
            await (conn or db).execute(
                """
                UPDATE funding
                SET endpoint = ?, port = ?, read_key = ?, invoice_key = ?, admin_key = ?, cert = ?
                WHERE backend_wallet = ?
                """,
            (
                fsource[0],
                fsource[1],
                fsource[2],
                fsource[3],
                fsource[4],
                fsource[5],
                fsource[8],
           ),
        )

    rows = await (conn or db).fetchone("SELECT * FROM funding")
    return [Funding(**row) for row in rows]
