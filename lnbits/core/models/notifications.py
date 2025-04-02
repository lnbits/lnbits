from enum import Enum

from pydantic import BaseModel


class NotificationType(Enum):
    server_status = "server_status"
    settings_update = "settings_update"
    balance_update = "balance_update"
    watchdog_check = "watchdog_check"
    balance_delta = "balance_delta"
    server_start_stop = "server_start_stop"
    incoming_payment = "incoming_payment"
    outgoing_payment = "outgoing_payment"
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
        *LNbits balance*: `{lnbits_balance_sats}` sats.
        *Node balance*: `{node_balance_sats}` sats.""",
    "server_start_stop": """*SERVER*
        {message}
        *Time*: `{up_time}` seconds.
    """,
    "settings_update": """*SETTINGS UPDATED*
        User: `{username}`.
    """,
    "balance_update": """*WALLET CREDIT/DEBIT*
        Wallet `{wallet_name}` balance updated with `{amount}` sats.
        *Current balance*: `{balance}` sats.
        *Wallet ID*: `{wallet_id}`
        """,
    "watchdog_check": """*WATCHDOG BALANCE CHECK*
        *Delta*: `{delta_sats}` sats.
        *LNbits balance*: `{lnbits_balance_sats}` sats.
        *Node balance*: `{node_balance_sats}` sats.
        *Switching to Void Wallet*: `{switch_to_void_wallet}`.
        """,
    "balance_delta": """*BALANCE DELTA CHANGED*
        *New delta*: `{delta_sats}` sats.
        *Old delta*: `{old_delta_sats}` sats.
        *LNbits balance*: `{lnbits_balance_sats}` sats.
        *Node balance*: `{node_balance_sats}` sats.
        """,
    "outgoing_payment": """*PAYMENT SENT*
        *Amount*: {fiat_value_fmt}`{amount_sats}`*sats*.
        *Wallet*: `{wallet_name}` ({wallet_id}).""",
    "incoming_payment": """*PAYMENT RECEIVED*
        *Amount*: {fiat_value_fmt}`{amount_sats}`*sats*.
        *Wallet*: `{wallet_name}` ({wallet_id}).
        """,
}
