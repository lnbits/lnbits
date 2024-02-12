import aiohttp
import asyncio
import json
import os

url =  os.environ.get('BLINK_API_ENDPOINT')
headers = {
    "Content-Type": "application/json",
    "X-API-KEY": os.environ.get('BLINK_TOKEN')
}


balance_query = """
        query Me {
        me {
            defaultAccount {
            wallets {
                walletCurrency
                balance
            }
            }
        }
        }
"""

invoice_query = """mutation LnInvoiceCreateOnBehalfOfRecipient($input: LnInvoiceCreateOnBehalfOfRecipientInput!) {
lnInvoiceCreateOnBehalfOfRecipient(input: $input) {
    invoice {
      paymentRequest
      paymentHash
      paymentSecret
      satoshis
    }
    errors {
      message
    }
  }
}
"""

payment_query = """mutation LnInvoicePaymentSend($input: LnInvoicePaymentInput!) {
        lnInvoicePaymentSend(input: $input) {
        status
            errors {
                message
                path
                code
            }
        }
    }
"""

# Estimate payment fee
fee_query = """mutation lnInvoiceFeeProbe($input: LnInvoiceFeeProbeInput!) {
        lnInvoiceFeeProbe(input: $input) {
            errors {
              message
            }
            amount
        }
    }
"""

# payment status
status_query = """
query LnInvoicePaymentStatus($input: LnInvoicePaymentStatusInput!) {
    lnInvoicePaymentStatus(input: $input) {
    status
    }
}
"""


async def graphql_query(payload):
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            data = await response.json()
            return data

# {'data': {'lnInvoicePaymentSend': {'status': 'SUCCESS', 'errors': []}}}
async def pay_invoice(invoice, wallet_id) -> json:
    payment_variables =  {
         "input": {
            "paymentRequest": invoice,
            "walletId": wallet_id,
            "memo": "Payment memo"
        }
    }
    data = {
        "query": payment_query,
        "variables": payment_variables
    }
    response = await graphql_query(data)
    return response


async def get_fee_estimate(remote_invoice, wallet_id) -> json:
    fee_variables = {
        "input": {
            "paymentRequest": remote_invoice,
            "walletId": wallet_id
        }
    }
    data = {
        "query": fee_query,
        "variables": fee_variables
    }
    response = await graphql_query(data)
    return response

async def get_invoice(amount, wallet_id) -> str:
    invoice_variables = {
        "input": {
            "amount": amount,
            "recipientWalletId": wallet_id
            # "descriptionHash": "Example description hash",
            # "memo": "Example memo"
        }
    }
    data = {
        "query": invoice_query,
        "variables": invoice_variables
    }
    response = await graphql_query(data)
    invoice = response.get('data', {}).get('lnInvoiceCreateOnBehalfOfRecipient', {}).get('invoice', {}).get('paymentRequest', {})
    return invoice


# {'data': {'lnInvoicePaymentStatus': {'status': 'PAID'}}}
# {'data': {'lnInvoicePaymentStatus': {'status': 'PENDING'}}}
async def get_invoice_status(bolt11) -> json:
    status_variables = {"input": {"paymentRequest": bolt11 }}
    data = {
        "query": status_query,
        "variables": status_variables
    }
    response = await graphql_query(data)
    return response


async def get_balance() -> int:
    data = {
        "query": balance_query,
        "variables": {}
    }
    response = await graphql_query(data)
    wallets = response.get("data", {}).get("me", {}).get("defaultAccount", {}).get("wallets", [])
    btc_balance = next((wallet['balance'] for wallet in wallets if wallet['walletCurrency'] == 'BTC'), None)
    return btc_balance

async def get_wallet_id() -> str:
    wallet_payload = {
        "query": "query me { me { defaultAccount { wallets { id walletCurrency }}}}",
        "variables": {}
    }
    response = await graphql_query(wallet_payload)
    wallets = response.get("data", {}).get("me", {}).get("defaultAccount", {}).get("wallets", [])
    btc_wallet_ids = [wallet["id"] for wallet in wallets if wallet["walletCurrency"] == "BTC"]
    wallet_id = btc_wallet_ids[0]
    return wallet_id


async def main():
    # get wallet id payload
    print("\nGet wallet id")
    wallet_id = await get_wallet_id()
    print(f'wallet id: {wallet_id}')
    print("------")

    # get balance payload
    print("\nGet balance")
    btc_balance = await get_balance()
    print(f'btc balance: {btc_balance}')
    print("------")

    print("\nGet Invoice status")
    bolt11 = "lnbc10u1pjunp54pp5u638gnndjgezs8dar5raqpd3s9lkwmjd4ya78mhyrhgz5s3c0w9sdqqcqzpuxqyz5vqsp5k4hw5976p6wk44mzs3ykznwuyczf3zyrqmqjg4u4z0ndkk7m6z9q9qyyssqtvwqww3824293p5fvvuje2fznjt829dze77kexpx3lnay764jj6sa7eduyzcjnnjl930j0fqlg3n93dtjaxfklew6lxqt75jaklkmqgqfymxem"
    print(f"invoice: {bolt11}")
    response = await get_invoice_status(bolt11)
    print(response)
    print("------")

    # get fee estimate
    remote_invoice = "lnbc5u1pjunp9hpp5qtq6hh4udkhndkdsqf05t73j5etquvldv0wekhsgeqnpc6dhvgjsdpv2phhwetjv4jzqcneypqyc6t8dp6xu6twva2xjuzzda6qcqzzsxqrrsssp5c332ejvnvuk75ksh3vwks8tex8tp3lzlmgpmywjm8jpqus0d0l2s9qyyssqre2u2jcn7chtzqu3uarhyw82p5p5xayhjkpmfezep0jukt5wm99nq43chuwavrlst79e30jsxr0exwm0z0ycmtvw70dks9x4534narcp2l750l"
    print("\nGet Fee Estimate")
    response = await get_fee_estimate(remote_invoice, wallet_id)
    print(f"remote_invoice {remote_invoice}")
    print(response)
    print("------")

    amount = 100
    print(f"\nGet a new Invoice, amount {amount} ")
    new_invoice = await get_invoice(amount, wallet_id)
    print(f'new invoice: {new_invoice}')
    print("------")

    # pay invoice (send payment)
    remote_invoice ="lnbc1u1pjungqepp5elafqwka4eqlymx2vn5radkyma49ug6qzmy6snkcfyvqwae4t25qdpv2phhwetjv4jzqcneypqyc6t8dp6xu6twva2xjuzzda6qcqzzsxqrrsssp56qj4lssk3wxv2y5y3jxwfkectevdyrf340mm3xd0hn3wtj9rafzs9qyyssqu3zx6ceewal5mea5hs6smaaz3pelw5tce82w7pldfnh7fkx6wzyy384teyvywkccwp300zzx4yd3aupcttp2qwwnxk704a4y060ryjcpm0dayl"
    response = await pay_invoice(remote_invoice, wallet_id)
    print(f'pay invoice response: {response}')

    # # get payment status
    response = await get_invoice_status(remote_invoice)
    print(f'payment status response: {response}')



if __name__ == "__main__":
    asyncio.run(main())



# Example response Probe fee
# {
#   "data": {
#     "lnInvoiceFeeProbe": {
#       "errors": [
#         {
#           "message": "User tried to pay themselves"
#         }
#       ],
#       "amount": null
#     }
#   }
# }

# example probe fee success
# {
#   "data": {
#     "lnInvoiceFeeProbe": {
#       "errors": [],
#       "amount": 1
#     }
#   }
# }

# Example can't pay self
# {
#   "data": {
#     "lnInvoicePaymentSend": {
#       "status": "FAILURE",
#       "errors": [
#         {
#           "message": "User tried to pay themselves",
#           "path": null,
#           "code": "CANT_PAY_SELF"
#         }
#       ]
#     }
#   }
# }

# Example insufficient balance
# {
#   "data": {
#     "lnInvoicePaymentSend": {
#       "status": "FAILURE",
#       "errors": [
#         {
#           "message": "Payment amount '1001' sats exceeds balance '0'",
#           "path": null,
#           "code": "INSUFFICIENT_BALANCE"
#         }
#       ]
#     }
#   }
# }
