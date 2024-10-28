# Python script to create a fake admin user for sqlite3,
# for regtest setup as LNbits funding source

import os
import sqlite3
import sys
import time
from uuid import uuid4

import shortuuid

adminkey = "d08a3313322a4514af75d488bcc27eee"
sqfolder = "./data"

if not sqfolder or not os.path.isdir(sqfolder):
    print("missing LNBITS_DATA_FOLDER")
    sys.exit(1)

file = os.path.join(sqfolder, "database.sqlite3")
conn = sqlite3.connect(file)
cursor = conn.cursor()

old_account = cursor.execute(
    "SELECT * FROM accounts WHERE id = :id", {"id": adminkey}
).fetchone()
if old_account:
    print("fake admin does already exist")
    sys.exit(1)


cursor.execute("INSERT INTO accounts (id) VALUES (:adminkey)", {"adminkey": adminkey})

wallet_id = uuid4().hex
cursor.execute(
    """
    INSERT INTO wallets (id, name, "user", adminkey, inkey)
    VALUES (:wallet_id, :name, :user, :adminkey, :inkey)
    """,
    {
        "wallet_id": wallet_id,
        "name": "TEST WALLET",
        "user": adminkey,
        "adminkey": adminkey,
        "inkey": uuid4().hex,  # invoice key is not important
    },
)

expiration_date = time.time() + 420

# 1 btc in sats
amount = 100_000_000
payment_hash = shortuuid.uuid()
internal_id = f"internal_{payment_hash}"

cursor.execute(
    """
    INSERT INTO apipayments
      (wallet_id, checking_id, payment_hash, amount, status, memo, fee, expiry)
    VALUES
      (:wallet_id, :checking_id, :payment_hash, :amount,
       :status, :memo, :fee, :expiry)
    """,
    {
        "wallet_id": wallet_id,
        "checking_id": internal_id,
        "payment_hash": payment_hash,
        "amount": amount * 1000,
        "status": "success",
        "memo": "fake admin",
        "fee": 0,
        "expiry": expiration_date,
        "pending": False,
    },
)

print(f"created test admin: {adminkey} with {amount} sats")

conn.commit()
cursor.close()
