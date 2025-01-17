from enum import Enum

from pydantic import BaseModel


class NotificationType(Enum):
    settings_update = "settings_update"
    balance_update = "balance_update"
    balance_delta = "balance_delta"
    server_start_stop = "server_start_stop"
    text_message = "text_message"


class NotificationMessage(BaseModel):
    message_type: NotificationType
    values: dict


NOTIFICATION_TEMPLATES = {
    "text_message": "{message}",
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
}
