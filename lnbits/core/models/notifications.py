from enum import Enum

from pydantic import BaseModel


class NotificationType(Enum):
    server_status = "server_status"
    settings_update = "settings_update"
    balance_update = "balance_update"
    balance_delta = "balance_delta"
    server_start_stop = "server_start_stop"
    incoming_invoice = "incoming_invoice"
    outgoing_invoice = "outgoing_invoice"
    text_message = "text_message"


class NotificationMessage(BaseModel):
    message_type: NotificationType
    values: dict


NOTIFICATION_TEMPLATES = {
    "text_message": "{message}",
    "server_status": """*SERVER STATUS*
        *Up time*: `{up_time}`.
        *Accounts*: `{accounts_count}`.
        *Wallets*: `{wallets_count}`.
        *In/Out payments*: `{in_payments_count}`/`{out_payments_count}`.
        *Pending payments*: `{pending_payments_count}`.
        *Failed payments*: `{failed_payments_count}`.
        *LNbits balance*: `{lnbits_balance_sats}` sats.""",
    "server_start_stop": """*SERVER*
        {message}
        *Time*: `{up_time}` seconds.
    """,
    "settings_update": """*SETTINGS UPDATED*
        User: `{username}`.
    """,
    "balance_update": """*BALANCE UPDATED*
        Wallet `{wallet_name}` balance updated with `{amount}` sats.
        *Current balance*: `{balance}` sats.
        *Wallet ID*: `{wallet_id}`
        """,
    "balance_delta": """*BALANCE DELTA*
        *Delta*: `{delta_sats}` sats.
        *LNbits balance*: `{lnbits_balance_sats}` sats.
        *Node balance*: `{node_balance_sats}` sats.
        *Switching to Void Wallet*: `{switch_to_void_wallet}`.
        """,
    "outgoing_invoice": """*OUTGOING INVOICE*
        *Wallet*: `{wallet_name}` ({wallet_id}).
        *Amount*: `{amount_sats}` sats.""",
    "incoming_invoice": """*INCOMING INVOICE*
        *Wallet*: `{wallet_name}` ({wallet_id}).
        *Amount*: `{amount_sats}` sats.
        """,
}
