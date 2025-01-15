from enum import Enum

from pydantic import BaseModel


class NotificationType(Enum):
    settings_update = "settings_update"
    balance_update = "balance_update"


class NotificationMessage(BaseModel):
    message_type: NotificationType
    values: dict


NOTIFICATION_TEMPLATES = {
    "settings_update": """
        *SETTINGS UPDATED*
        User: `{username}`.
    """,
    "balance_update": """
        *BALANCE UPDATED*
        Wallet `{wallet_name}` balance updated with `{amount}` sats.
        *Current balance*: `{balance}` sats.
        *Wallet ID*: `{wallet_id}`
        """,
}
