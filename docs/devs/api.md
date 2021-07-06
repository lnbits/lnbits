---
layout: default
parent: For developers
title: API reference
nav_order: 3
---


API reference
=============

## Wallet endpoints

* `/api/v1`

  * `/wallet`  </p>
  GET  wallet details  </p>
  Headers  
  {"X-Api-Key": "\<admin-key\>"}  </p>
  Returns 200 OK (application/json)  
  {"id": \<string\>, "name": \<string\>, "balance": \<int\>}  
  or  
  {"message": \<string\>} (error message)  </p>
    _Curl example_  
  curl \<base_url + /api/v1/wallet\> -H "X-Api-Key: \<admin-key\>"  </p>
  _Python example_  
  headers = {"X-Api-Key": "\<admin-key\>", "Content-type": "application/json"}  
  requests.get(\<base_url\> + "/api/v1/wallet", headers=headers)  
  
  * `/payments`  </p>
  POST  invoice creation (incoming)  </p>
  Headers  
  {"X-Api-Key": "\<admin-key\> or \<invoice-key\>"}  </p>
  Body (application/json)  
  {"out": false, "amount": \<int\>, "memo": \<string\>}  </p>
  Returns 201 CREATED (application/json)  
  {"payment_hash": \<string\>, "payment_request": \<string\>}  
  or  
  {"message": \<string\>} (error message)  </p>
  _Curl example_  
  curl -X POST \<base_url + /api/v1/payments\> -d '{"out": false, "amount": \<int\>, "memo": \<string\>, "webhook": \<url:string\>}' -H "X-Api-Key: \<admin-key\> or \<invoice-key\>" -H "Content-type: application/json"  </p>
  _Python example_  
  headers = {"X-Api-Key": "\<admin-key\> or \<invoice-key\>", "Content-type": "application/json"}  
  data = {"out": False, "amount": \<int\>, "memo": \<string\>}  
  requests.post(\<base_url\> + "/api/v1/payments/", data=json.dumps(data), headers=headers) </p>
  * `/payments`  </p>
  POST  invoice payment (outgoing)  </p>
  Headers  
  {"X-Api-Key": "\<admin-key\>"}  </p>
  Body (application/json)  
  {"out": true, "bolt11": \<string\>}  </p>
  Returns 201 CREATED (application/json)  
  {"payment_hash": \<string\>}  
  or  
  {"message": \<string\>} (error message)  </p>
  _Curl example_  
  curl -X POST \<base_url + /api/v1/payments\> -d '{"out": true, "bolt11": \<string\>}' -H "X-Api-Key: \<admin-key\>" -H "Content-type: application/json"  </p>
  _Python example_  
  headers = {"X-Api-Key": "\<admin-key\>", "Content-type": "application/json"}  
  data = {"out": True, "bolt11": \<string\>}  
  requests.post(\<base_url\> + "/api/v1/payments/", data=json.dumps(data), headers=headers) </p>
</br></br></br>
## Simple Python example of a service accounts system (work in progress)

```
import requests, json

base_url = "https://lnbits.com"
# base_url = "https://localhost:5001"
# base_url = "https://<wherever_you_deployed_your_lnbits>[:5001]"

################################################################################
# Create the MANAGER user manually                                             #
################################################################################

# Copy this from the URL <usr> parameter
usr = "151779637d7c42729e189beb053c1145"

# Copy this from the <API info> <Admin key> (right side of the LNbits main page)
# <Invoice/read key> or <Admin key>, both work for creating users
# But to pay an invoice later you will need the <Admin key>
manager_key = "b0aefdca251c47b2959dcfc2ca78899f"

#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!#
#    Don't forget to enable the User Manager extension    #
#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!#

################################################################################
# Create user + initial wallet                                                 #
################################################################################

user_name = "api_created_user"
wallet_name = "api_user_wallet"
data = {"admin_id": usr, "user_name": user_name, "wallet_name": wallet_name}
headers = {"X-Api-Key": manager_key, "Content-type": "application/json"}

post_return = requests.post(base_url+"/usermanager/api/v1/users",
                            data=json.dumps(data),
                            headers=headers)

# This call only returns the new user ID (his keys will be get in the next step)
new_user_ID = post_return.json()["id"]
print("First step: create user.")
print("Newly created user ID:", new_user_ID)


################################################################################
# Get the newly created user wallet details                                    #
################################################################################

headers = {"X-Api-Key": manager_key, "Content-type": "application/json"}

get_return = requests.get(base_url+"/usermanager/api/v1/wallets/"+new_user_ID,
                          headers=headers)

# This response will bring 6 items, but 3 of them are already known
# Already known: manager_id, user_id and user wallet_name
# New info: user wallet_id, user admin_key and user invoice_key
new_user_id = get_return.json()[0]["user"]
new_user_wallet_id = get_return.json()[0]["id"]
new_user_admin_key = get_return.json()[0]["adminkey"]
new_user_invoice_key = get_return.json()[0]["inkey"]

print("\nSecond step: get new user details.")
print("Newly created user ID:", new_user_id, "(should be the same as above)")
print("Newly created user wallet ID:", new_user_wallet_id)
print("Newly created user admin key:", new_user_admin_key)
print("Newly created user read/invoice key:", new_user_invoice_key)


################################################################################
# Create invoice for user                                                      #
################################################################################

amount = 1000 # in sats
memo = "Payment/Tip from service/game XXXXX"
data = {"out": False, "amount": amount, "memo": memo}
headers = {"X-Api-Key":new_user_invoice_key, "Content-type":"application/json"}

post_return = requests.post(base_url+"/api/v1/payments",
                            data=json.dumps(data),
                            headers=headers)

payment_hash = post_return.json()["payment_hash"]
payment_request = post_return.json()["payment_request"]

print("\nThird step: create invoice from user.")
print("Invoice hash:", payment_hash)
print("Invoice request (bolt11):", payment_request)


################################################################################
# Pay invoice to the user wallet (still on your service)                       #
################################################################################

data = {"out": True, "bolt11": payment_request}
headers = {"X-Api-Key": manager_key, "Content-type": "application/json"}

post_return = requests.post(base_url+"/api/v1/payments",
                            data=json.dumps(data),
                            headers=headers)

print("\nFourth step: pay invoice to the user.")
if post_return.status_code == 201:
  payment_hash = post_return.json()["payment_hash"]
  print("Payment successfull.")
  print("Invoice hash:", payment_hash)
else:
  print("Error!", post_return.json()["message"])

```

To be continued...
