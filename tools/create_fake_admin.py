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
    "SELECT * FROM accounts WHERE id = ?", (adminkey,)
).fetchone()
if old_account:
    print("fake admin does already exist")
    sys.exit(1)


cursor.execute("INSERT INTO accounts (id) VALUES (?)", (adminkey,))

wallet_id = uuid4().hex
cursor.execute(
    """
    INSERT INTO wallets (id, name, "user", adminkey, inkey)
    VALUES (?, ?, ?, ?, ?)
    """,
    (
        wallet_id,
        "TEST WALLET",
        adminkey,
        adminkey,
        uuid4().hex,  # invoice key is not important
    ),
)

expiration_date = time.time() + 420

# 1 btc in sats
amount = 100_000_000
internal_id = f"internal_{shortuuid.uuid()}"

cursor.execute(
    """
    INSERT INTO apipayments
      (wallet, checking_id, bolt11, hash, preimage,
       amount, status, memo, fee, extra, webhook, expiry, pending)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
        wallet_id,
        internal_id,
        "test_admin_internal",
        "test_admin_internal",
        None,
        amount * 1000,
        "success",
        "test_admin_internal",
        0,
        None,
        "",
        expiration_date,
        False,  # TODO: remove this in next release
    ),
)

print(f"created test admin: {adminkey} with {amount} sats")

conn.commit()
cursor.close()
