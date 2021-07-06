from quart import jsonify
from lnbits.helpers import urlsafe_short_hash
from lnbits.core.services import create_invoice, pay_invoice, check_invoice_status
from .models import Setup, Users, Logs, Payments
from .helpers import (
    usrFromWallet,
    widFromWallet,
    inKeyFromWallet,
    adminKeyFromWallet,
    getUser,
    getUsers,
    getLogs,
    createLog,
    getPayoutBalance,
    handleCredits,
    numPayments,
    klankyRachet,
    L_HOST,
)
from typing import List, Optional, Dict
from . import db
import json
import httpx


async def accountSetup(
    usr_id: str, invoice_wallet: str, payout_wallet: str, data: Optional[str]
) -> Setup:
    # data = None if data is None else None
    await db.execute(
        """
        INSERT OR REPLACE INTO setup (usr_id, invoice_wallet, payout_wallet,data)
        VALUES (?,?,?,?)
        """,
        (usr_id, invoice_wallet, payout_wallet, data),
    )
    row = await getSettings(None, usr_id)
    return {"success": row["success"]}


async def createdb_user(
    usr_id: str,
    id: str,
    lnurl_auth: Optional[str],
    admin: str,
    payout_wallet: str,
    credits: int,
    active: bool,
    data: Optional[str],
) -> Users:
    data = None if data is None else data
    try:
        await db.execute(
            """
            INSERT INTO users (usr_id, id, lnurl_auth, admin,payout_wallet,credits,active,data)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (usr_id, id, lnurl_auth, admin, payout_wallet, credits, active, data),
        )
        await createLog(id, "User Created", None, None, None, None, None)
        return jsonify(success=True)
    except:
        print("log error")
        return jsonify(error="Server error. User not created")


async def getSettings(inKey: Optional[str], admin: Optional[str]) -> dict:
    usr = admin if admin is not None else await usrFromWallet(inKey)
    try:
        row = await db.fetchone(f"SELECT * FROM setup WHERE usr_id = '{usr}'")
        d = dict(row)
        del d["usr_id"]
        return {"success": d}
    except:
        return {"success": {}}


async def addPayment(
    id: str,
    admin_id: str,
    usr_id: str,
    amount: int,
    credits: int,
    paid: False,
    cmd: str,
    data: Optional[str],
) -> Payments:
    try:
        await db.execute(
            """
            INSERT INTO payments (id, admin_id, usr_id,amount,credits,paid,cmd,data)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (id, admin_id, usr_id, amount, credits, paid, cmd, data),
        )
        return True
    except:
        print("log error")
        return False


async def handlePaymentWebhook(id: str, params: dict) -> dict:
    if not "payment" in params:
        if not {"withdraw", "ln_id", "hash"} <= set(params):
            return {"error": "missing parameters"}
        if params["withdraw"] == "check":
            if not "inKey" in params:
                return {"error": "Not Authorized"}
            update_check = await db.fetchone(
                f"SELECT * FROM payments WHERE id = '{id}'"
            )
            if update_check is None:
                return {"error": "No withdrawal found"}
            uc = dict(update_check)
            if uc["paid"]:
                return {"success": {"withdraw": True, "id": id, "amount": uc["amount"]}}
            usr_inkey = await inKeyFromWallet(
                (await getUser(uc["usr_id"], True, None, None))["usr_id"]
            )
            print(usr_inkey)
            # async call to check used need onion option
            url = (
                "https://"
                + params["host"]
                + "/withdraw/api/v1/links/"
                + params["ln_id"]
            )
            headers = {"Content-Type": "application/json", "X-Api-Key": usr_inkey}
            lnurlw_status = None
            async with httpx.AsyncClient() as client:
                try:
                    r = await client.get(
                        url,
                        headers=headers,
                        timeout=40,
                    )
                    lnurlw_status = r.json()
                except:
                    return {"error": "Withdraw link error!"}
            # if true then db and return {"success":{"paid":True, "id": id}}
            print(lnurlw_status)
            if lnurlw_status["used"]:
                await db.execute(f"UPDATE payments SET paid = True WHERE id = '{id}'")
                log = await createLog(
                    usr=uc["usr_id"],
                    cmd="withdraw",
                    wl=None,
                    credits=None,
                    multi=None,
                    sats=uc["amount"],
                    data=None,
                )
                return {"success": {"withdraw": True, "id": id, "amount": uc["amount"]}}
            else:
                return {"success": {"withdraw": False, "id": id}}
    else:
        pay_row = await db.fetchone(f"SELECT * FROM payments WHERE id = '{id}'")
        if pay_row is None:
            return {"error": "No payment found"}
        pay_row = dict(pay_row)
        if pay_row["paid"]:
            return {"error": "Payment already processed"}
        # wal_id = (await getSettings(None, pay_row['admin_id']))['success']['invoice_wallet']
        # pay_hash = json.loads(pay_row['data'])['payment_hash']
        # pay_req = await check_invoice_status(wal_id, pay_hash)
        # print(pay_req)
        # if str(pay_req) != 'settled':# might need change if split payment
        #     return {"error": "Payment not paid"}
        await db.execute("UPDATE payments SET paid = TRUE WHERE id = ?", (id))
        usr, amount, credits = pay_row["usr_id"], pay_row["amount"], pay_row["credits"]
        usr_credits = (await getUser(usr, False, None, None))["credits"]
        add_credits = await handleCredits(usr, int(usr_credits + credits))
        if add_credits:
            log = await createLog(
                usr=usr,
                cmd="fund",
                wl=None,
                credits=credits,
                multi=None,
                sats=amount,
                data=None,
            )
            return {"success": {"id": id, "payment": "paid"}}
        else:
            # error
            return {"error": "Not Authorized"}


async def API_createUser(inKey: str, auto: bool, data: Optional[str]) -> dict:
    data, url, local, = (
        data["data"],
        data["url"],
        data["local"],
    )
    local = False if local is None else True
    id = data["id"] if "id" in data is not None else urlsafe_short_hash()
    lnurl_auth = data["lnurl_auth"] if "lnurl_auth" in data else None
    user = await usrFromWallet(inKey)
    # check if user already exists
    ch_lnurl = (
        f"OR lnurl_auth = '{lnurl_auth}' AND admin = '{user}'"
        if lnurl_auth is not None
        else ""
    )
    row = await db.fetchone(f"SELECT * FROM users WHERE id = '{id}' {ch_lnurl}")
    if row is not None:
        return {"error": "User already created"}
    ###
    if auto:
        # base_url = url.rsplit('/', 4)[0]
        base_url = L_HOST
        url = base_url + "/usermanager/api/v1/users"
        headers = {"Content-Type": "application/json", "X-Api-Key": inKey}
        payload = {"admin_id": user, "wallet_name": "Payout", "user_name": id}
        async with httpx.AsyncClient() as client:
            try:
                r = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=40,
                )
                uid = r.json()["id"]
                wid = await widFromWallet(uid)
                newUser = await createdb_user(
                    usr_id=uid,
                    id=id,
                    lnurl_auth=lnurl_auth,
                    admin=user,
                    payout_wallet=wid,
                    credits=0,
                    active=True,
                    data=None,
                )
                rUser = await getUser(id, False, lnurl_auth, None)
                return {"success": rUser}
            except ValueError:
                print(ValueError)
                return jsonify(error="User not created!")
    else:
        uid, wid = data["uid"], data["wid"]
        newUser = await createdb_user(
            usr_id=uid,
            id=id,
            lnurl_auth=None,
            admin=user,
            payout_wallet=wid,
            credits=0,
            active=True,
            data=None,
        )
        User = await getUser(id, local, None, None)
        return {"success": User}


async def API_deleteUser(id: str, url: str, inKey: str, wlOnly: bool) -> dict:
    # base_url = url.rsplit('/', 5)[0]
    base_url = L_HOST
    user = await usrFromWallet(inKey)
    try:
        uid = (await getUser(id, True, None, None))["usr_id"]
    except:
        uid = "123456jsjdka"
    if not wlOnly:
        headers = {"Content-Type": "application/json", "X-Api-Key": inKey}
        url = base_url + "/usermanager/api/v1/users/" + uid
        async with httpx.AsyncClient() as client:
            r = await client.delete(
                url,
                headers=headers,
                timeout=40,
            )
        if int(r.status_code) == 204:
            await db.execute(f"DELETE FROM users WHERE id = '{id}'")
            return jsonify({"success": {"id": id, "deleted": True}})
        else:
            return jsonify({"error": {"id": id, "deleted": False}})
    else:
        await db.execute(f"DELETE FROM users WHERE id = '{id}'")
        return jsonify({"success": {"id": id, "deleted": True}})


async def API_updateUser(p) -> dict:
    await db.execute(
        f"UPDATE users SET {p['set']} = {p['payload']} WHERE id = '{p['id']}'"
    )
    return {"success": "User updated"}


async def API_getUsers(params: dict) -> dict:
    local = params["local"] if "local" in params else False
    limit = params["limit"] if "limit" in params else None
    admin_id = await usrFromWallet(params["inKey"])
    logs = None
    if "id" in params:
        if params["id"] == "lnurl_auth":
            usr = await getUser(
                params["id"], True, params["lnurl_auth"], {"admin": admin_id}
            )
            if "error" in usr:
                return usr
        else:
            usr = await getUser(params["id"], True, None, None)
            if "error" in usr:
                return usr
        del usr["admin"]
        inKey = await inKeyFromWallet(usr["usr_id"])
        url = params["url"].rsplit("?", 1)[0] + "/payout/user"
        balance = await getPayoutBalance(inKey, url)
        if "logs" in params and params["logs"]:
            logs = await getLogs(params["id"], limit)
        usr["balance"] = int(balance["balance"] / 1000)
        # if not local:
        del usr["usr_id"]
        del usr["payout_wallet"]
        del usr["lnurl_auth"]
    else:
        usr = await getUsers(admin_id, local)
        # if local:
        #     for u in usr:
        #         del u['admin']
    data = {"usr": usr}
    data["logs"] = logs if logs is not None else None
    return {"success": data}


async def API_lose(id: str, params: dict) -> dict:
    usr = await getUser(id, True, None, None)
    if "error" in usr:
        return usr
    if not "free_spin" in params:
        acca = int(params["multi"]) * -1 if "multi" in params else -1
        cred = int(usr["credits"]) + acca
        print(cred)
        cred = 0 if cred < 0 else cred
        credit_done = await handleCredits(id, cred)
        if credit_done:
            multi = params["multi"] if "multi" in params else None
            logged = await createLog(id, "lose", "lose", 1, multi, None, None)
            return {"success": {"id": id, "credits": cred, "deducted": acca}}
    else:
        spin_log = await createLog(id, "free spin", None, None, None, None, None)
        return {"success": {"id": id, "credits": int(usr["credits"]), "deducted": 0}}


async def API_win(id: str, params: dict) -> dict:
    payout, credits, total_credits, bal = None, None, None, None
    usr = await getUser(id, True, None, None)
    if not "free_spin" in params:
        acca = int(params["multi"]) * -1 if "multi" in params else -1
        cred = int(usr["credits"]) + acca
        credit_done = await handleCredits(id, cred)
        if credit_done:
            multi = params["multi"] if "multi" in params else None
            logged = await createLog(id, "win", None, 1, multi, None, None)
    if "payout" in params:
        try:
            payout = int(params["payout"])
            admin_id, usr_wallet = usr["admin"], usr["payout_wallet"]
            admin_wallet = (await getSettings(None, admin_id))["success"][
                "payout_wallet"
            ]
            payment_hash, payment_request = await create_invoice(
                wallet_id=usr_wallet, amount=payout, memo=f"Payout - {id}"
            )
            done = await pay_invoice(
                wallet_id=admin_wallet, payment_request=payment_request
            )
            try:
                inKey = await inKeyFromWallet(usr["usr_id"])
                url = params["url"].rsplit("?", 1)[0] + "/payout"
                bal = int((await getPayoutBalance(inKey, url))["balance"] / 1000)
            except:
                pass
            log = await createLog(id, "payout", "win", None, None, payout, None)
        except:
            pass
            # return error no spins used
    if "credits" in params:
        credits = params["credits"]
        usr_cred = int((await getUser(id, True, None, None))["credits"])
        total_credits = int(params["credits"]) + usr_cred
        credits_added = await handleCredits(id, int(total_credits))
        if credits_added:
            log = await createLog(id, "credits", "win", credits, None, None, None)
        else:
            pass
            # return error not spins
    win = int(credits) if credits is not None else payout
    win_type = "credits" if credits is not None else "sat"
    rem_credits = (
        total_credits
        if total_credits is not None
        else int((await getUser(id, True, None, None))["credits"])
    )
    acca = acca if not "free_spin" in params else 0
    return {
        "success": {
            "id": id,
            "win": win,
            "type": win_type,
            "credits": rem_credits,
            "payout_balance": bal,
            "deducted": acca,
        }
    }


async def API_fund(id: str, params: dict) -> dict:
    uni_id = urlsafe_short_hash()
    user = await getUser(id, True, None, None)
    if not user["active"]:
        return {"error": {"id": id, "active": False}}
    admin_id = user["admin"]
    try:
        webHook = str(L_HOST + f"/winlose/api/v1/payments/{uni_id}")
        invoice_wallet = (await getSettings(None, admin_id))["success"][
            "invoice_wallet"
        ]
        # c = await klankyRachet(await numPayments(admin_id))
        payment_request, payment_hash = await create_invoice(
            wallet_id=invoice_wallet,
            amount=int(params["amount"]),
            memo=f"Fund - {id}",
            webhook=webHook,
        )
        data = json.dumps({"payment_hash": payment_hash})
        pend_payments = await addPayment(
            id=uni_id,
            admin_id=admin_id,
            usr_id=id,
            amount=params["amount"],
            credits=params["credits"],
            paid=False,
            cmd="payment",
            data=data,
        )
        return {
            "success": {
                "usr_id": id,
                "payment_hash": payment_hash,
                "payment_request": payment_request,
                "amount": int(params["amount"]),
            }
        }
    except ValueError:
        print(ValueError)
        return {"error": "Processing error. Try again!"}


async def API_withdraw(id: str, params: dict) -> dict:
    usr = await getUser(id, True, None, None)
    if not usr["active"]:
        return {"error": {"id": id, "active": False}}
    protocol = params["url"].rsplit("//", 1)[0].rsplit(":", 1)[0]
    if protocol != "https":  # need to add support for TOR
        return {"error": "withdrawal must be over https"}
    inKey = await inKeyFromWallet(usr["usr_id"])
    adminKey = await adminKeyFromWallet(usr["usr_id"])
    url = protocol + "://" + params["host"] + "/withdraw/api/v1/links"
    bal = int((await getPayoutBalance(inKey, url))["balance"])
    if bal == 0:
        return {"error": "No funds available"}
    bal = int(bal / 1000)
    uni_id = urlsafe_short_hash()
    headers = {"Content-Type": "application/json", "X-Api-Key": adminKey}
    payload = {
        "title": "Withdraw - " + id,
        "min_withdrawable": bal,
        "max_withdrawable": bal,
        "uses": 1,
        "wait_time": 1,
        "is_unique": True,
    }
    withdraw_link = None
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                url,
                headers=headers,
                json=payload,
                timeout=40,
            )
            withdraw_link = r.json()
        except:
            return {"error": "Withdraw link error!"}
    chk_url = (
        protocol
        + "://"
        + params["host"]
        + "/winlose/api/v1/payments/"
        + uni_id
        + "?withdraw=check&ln_id="
        + withdraw_link["id"]
        + "&hash="
        + withdraw_link["unique_hash"]
    )
    if withdraw_link:
        data = json.dumps({"withdraw_link": withdraw_link})
        pend_withdraw = await addPayment(
            id=uni_id,
            admin_id=usr["admin"],
            usr_id=id,
            amount=bal,
            credits=0,
            paid=False,
            cmd="withdraw",
            data=data,
        )
        return {
            "success": {
                "lnurl": withdraw_link["lnurl"],
                "chk_url": chk_url,
                "amount": bal,
            }
        }
    else:
        return {"error": "Server Error"}
