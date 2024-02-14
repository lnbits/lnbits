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
# payment status based on bolt11 as input and error codes
invoice_status = """query Query($input: LnInvoicePaymentStatusInput!) {
  lnInvoicePaymentStatus(input: $input) {
    errors {
      code
      message
      path
    }
    status
  }
}
"""

# fetch payments with proof
proof_query = """
    query PaymentsWithProof($first: Int) {
      me {
        defaultAccount {
          transactions(first: $first) {
            edges {
              node {
                initiationVia {
                  ... on InitiationViaLn {
                    paymentRequest
                    paymentHash
                  }
                }
                settlementVia {
                  ... on SettlementViaIntraLedger {
                    preImage
                  }
                  ... on SettlementViaLn {
                    preImage
                  }
                }
              }
            }
          }
        }
      }
    }
"""

# Transactions by Payment Hash
tx_query = """
query TransactionsByPaymentHash($paymentHash: PaymentHash!) {
  me {
    defaultAccount {
      wallets {
        ... on BTCWallet {
          transactionsByPaymentHash(paymentHash: $paymentHash) {
            createdAt
            direction
            id
            memo
            status
            settlementFee
            settlementVia {
              ... on SettlementViaLn {
                preImage
              }
            }
          }
        }
      }
    }
  }
}
"""

async def graphql_query(payload):
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            data = await response.json()
            return data
        

async def get_tx_status(checking_id):
    # checking_id is the paymentHash
    variables = {"paymentHash": checking_id}
    data = {
        "query": tx_query,
        "variables": variables
    }
    response_data = await graphql_query(data)
    return response_data

async def get_payment_proof(checking_id):
    # checking_id is the paymentHash
    first = 2
    variables = {"first": first}

    data = {
        "query": proof_query,
        "variables": variables
    }
    response_data = await graphql_query(data)

    # look for the paymentHash in the response

    # Get transactions
    transactions = response_data['data']['me']['defaultAccount']['transactions']['edges']
    print(f"transactions: {transactions}\n\n")

    # Find the transaction with the matching paymentHash
    matching_transaction = None
    for transaction in transactions:
        payment_hash = transaction['node']['initiationVia']['paymentHash']
        print(f'payment_hash: {payment_hash}\n')
        if payment_hash == checking_id:
            matching_transaction = transaction
            break

    # Extract paymentRequest and preImage if a matching transaction is found
    if matching_transaction:
        payment_request = matching_transaction['node']['initiationVia']['paymentRequest']
        pre_image = matching_transaction['node']['settlementVia']['preImage']
        print("Payment Request:", payment_request, "\n")
        print("Pre Image:", pre_image, "\n")
        return pre_image, payment_request
    else:
        print("No transaction found with the desired payment hash")
        return False


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
    print(response)
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
    # print("\nGet Fee Estimate")
    # response = await get_fee_estimate(remote_invoice, wallet_id)
    # print(f"remote_invoice {remote_invoice}")
    # print(response)
    # print("------")

    amount = 100
    print(f"\nGet a new Invoice, amount {amount} ")
    # new_invoice = await get_invoice(amount, wallet_id)
    # print(f'new invoice: {new_invoice}')
    # print("------")

    # pay invoice (send payment)
    # remote_invoice ="lnbc1u1pjungqepp5elafqwka4eqlymx2vn5radkyma49ug6qzmy6snkcfyvqwae4t25qdpv2phhwetjv4jzqcneypqyc6t8dp6xu6twva2xjuzzda6qcqzzsxqrrsssp56qj4lssk3wxv2y5y3jxwfkectevdyrf340mm3xd0hn3wtj9rafzs9qyyssqu3zx6ceewal5mea5hs6smaaz3pelw5tce82w7pldfnh7fkx6wzyy384teyvywkccwp300zzx4yd3aupcttp2qwwnxk704a4y060ryjcpm0dayl"
    # response = await pay_invoice(remote_invoice, wallet_id)
    # print(f'pay invoice response: {response}')

    # # get payment status
    response = await get_invoice_status(remote_invoice)
    print(f'payment status response: {response}')

    ## get payment proof based on paymentHash
    checking_id = "c02edf02b3499527fea90739bd17304c16b20b5d30969fdfb2928181456bf5a0"
    # response = await get_payment_proof(checking_id)
    # print(f'payment proof response: {response}')

    # get payment status or invoice status based on paymentHash
    response = await get_tx_status(checking_id)
    print(f'\ntx status response: {response}\n\n')

    txbyPaymentHash = response['data']['me']['defaultAccount']['wallets'][0]['transactionsByPaymentHash'][0]
    print(txbyPaymentHash)

    status = txbyPaymentHash['status']
    print('status: ', status)

    preimage = txbyPaymentHash['settlementVia'].get('preImage')
    print('preimage: ', preimage)

    fee = txbyPaymentHash['settlementFee']
    print(f'fee: {fee}')


if __name__ == "__main__":
    asyncio.run(main())


# example error response for create invoice
# {
#   "data": {
#     "lnInvoiceCreateOnBehalfOfRecipient": {
#       "invoice": null,
#       "errors": [
#         {
#           "message": "Invalid value for WalletId"
#         }
#       ]
#     }
#   }
# }


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
