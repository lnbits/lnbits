import psycopg2
import sqlite3
import os
import argparse


from environs import Env  # type: ignore

env = Env()
env.read_env()

# Python script to migrate an LNbits SQLite DB to Postgres
# All credits to @Fritz446 for the awesome work


# pip install psycopg2 OR psycopg2-binary


# Change these values as needed


sqfolder = "data/"

LNBITS_DATABASE_URL = env.str("LNBITS_DATABASE_URL", default=None)
if LNBITS_DATABASE_URL is None:
    pgdb = "lnbits"
    pguser = "lnbits"
    pgpswd = "postgres"
    pghost = "localhost"
    pgport = "5432"
    pgschema = ""
else:
    # parse postgres://lnbits:postgres@localhost:5432/lnbits
    pgdb = LNBITS_DATABASE_URL.split("/")[-1]
    pguser = LNBITS_DATABASE_URL.split("@")[0].split(":")[-2][2:]
    pgpswd = LNBITS_DATABASE_URL.split("@")[0].split(":")[-1]
    pghost = LNBITS_DATABASE_URL.split("@")[1].split(":")[0]
    pgport = LNBITS_DATABASE_URL.split("@")[1].split(":")[1].split("/")[0]
    pgschema = ""


def get_sqlite_cursor(sqdb) -> sqlite3:
    consq = sqlite3.connect(sqdb)
    return consq.cursor()


def get_postgres_cursor():
    conpg = psycopg2.connect(
        database=pgdb, user=pguser, password=pgpswd, host=pghost, port=pgport
    )
    return conpg.cursor()


def check_db_versions(sqdb):
    sqlite = get_sqlite_cursor(sqdb)
    dblite = dict(sqlite.execute("SELECT * FROM dbversions;").fetchall())
    sqlite.close()

    postgres = get_postgres_cursor()
    postgres.execute("SELECT * FROM public.dbversions;")
    dbpost = dict(postgres.fetchall())

    for key in dblite.keys():
        if key in dblite and key in dbpost and dblite[key] != dbpost[key]:
            raise Exception(
                f"sqlite database version ({dblite[key]}) of {key} doesn't match postgres database version {dbpost[key]}"
            )

    connection = postgres.connection
    postgres.close()
    connection.close()

    print("Database versions OK, converting")


def fix_id(seq, values):
    if not values or len(values) == 0:
        return

    postgres = get_postgres_cursor()

    max_id = values[len(values) - 1][0]
    postgres.execute(f"SELECT setval('{seq}', {max_id});")

    connection = postgres.connection
    postgres.close()
    connection.close()


def insert_to_pg(query, data):
    if len(data) == 0:
        return

    cursor = get_postgres_cursor()
    connection = cursor.connection

    for d in data:
        try:
            cursor.execute(query, d)
        except Exception as e:
            if args.ignore_errors:
                print(e)
                print(f"Failed to insert {d}")
            else:
                print("query:", query)
                print("data:", d)
                raise ValueError(f"Failed to insert {d}")
    connection.commit()

    cursor.close()
    connection.close()


def migrate_core(sqlite_db_file):
    sq = get_sqlite_cursor(sqlite_db_file)

    # ACCOUNTS
    res = sq.execute("SELECT * FROM accounts;")
    q = f"INSERT INTO public.accounts (id, email, pass) VALUES (%s, %s, %s);"
    insert_to_pg(q, res.fetchall())

    # WALLETS
    res = sq.execute("SELECT * FROM wallets;")
    q = f'INSERT INTO public.wallets (id, name, "user", adminkey, inkey) VALUES (%s, %s, %s, %s, %s);'
    insert_to_pg(q, res.fetchall())

    # API PAYMENTS
    res = sq.execute("SELECT * FROM apipayments;")
    q = f"""
        INSERT INTO public.apipayments(
        checking_id, amount, fee, wallet, pending, memo, "time", hash, preimage, bolt11, extra, webhook, webhook_status)
        VALUES (%s, %s, %s, %s, %s::boolean, %s, to_timestamp(%s), %s, %s, %s, %s, %s, %s);
    """
    insert_to_pg(q, res.fetchall())

    # BALANCE CHECK
    res = sq.execute("SELECT * FROM balance_check;")
    q = f"INSERT INTO public.balance_check(wallet, service, url) VALUES (%s, %s, %s);"
    insert_to_pg(q, res.fetchall())

    # BALANCE NOTIFY
    res = sq.execute("SELECT * FROM balance_notify;")
    q = f"INSERT INTO public.balance_notify(wallet, url) VALUES (%s, %s);"
    insert_to_pg(q, res.fetchall())

    # EXTENSIONS
    res = sq.execute("SELECT * FROM extensions;")
    q = f'INSERT INTO public.extensions("user", extension, active) VALUES (%s, %s, %s::boolean);'
    insert_to_pg(q, res.fetchall())

    print("Migrated: core")


def migrate_ext(sqlite_db_file, schema, ignore_missing=True):

    # skip this file it has been moved to ext_lnurldevices.sqlite3
    if sqlite_db_file == "data/ext_lnurlpos.sqlite3":
        return

    print(f"Migrating {sqlite_db_file}.{schema}")
    sq = get_sqlite_cursor(sqlite_db_file)
    if schema == "bleskomat":
        # BLESKOMAT LNURLS
        res = sq.execute("SELECT * FROM bleskomat_lnurls;")
        q = f"""
            INSERT INTO bleskomat.bleskomat_lnurls(
            id, bleskomat, wallet, hash, tag, params, api_key_id, initial_uses, remaining_uses, created_time, updated_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())

        # BLESKOMATS
        res = sq.execute("SELECT * FROM bleskomats;")
        q = f"""
            INSERT INTO bleskomat.bleskomats(
            id, wallet, api_key_id, api_key_secret, api_key_encoding, name, fiat_currency, exchange_rate_provider, fee)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "captcha":
        # CAPTCHA
        res = sq.execute("SELECT * FROM captchas;")
        q = f"""
            INSERT INTO captcha.captchas(
            id, wallet, url, memo, description, amount, "time", remembers, extras)
            VALUES (%s, %s, %s, %s, %s, %s, to_timestamp(%s), %s, %s);
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "copilot":
        # OLD COPILOTS
        res = sq.execute("SELECT * FROM copilots;")
        q = f"""
            INSERT INTO copilot.copilots(
            id, "user", title, lnurl_toggle, wallet, animation1, animation2, animation3, animation1threshold, animation2threshold, animation3threshold, animation1webhook, animation2webhook, animation3webhook, lnurl_title, show_message, show_ack, show_price, amount_made, fullscreen_cam, iframe_url, "timestamp")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, to_timestamp(%s));
        """
        insert_to_pg(q, res.fetchall())

        # NEW COPILOTS
        q = f"""
           INSERT INTO copilot.newer_copilots(
            id, "user", title, lnurl_toggle, wallet, animation1, animation2, animation3, animation1threshold, animation2threshold, animation3threshold, animation1webhook, animation2webhook, animation3webhook, lnurl_title, show_message, show_ack, show_price, amount_made, fullscreen_cam, iframe_url, "timestamp")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, to_timestamp(%s));
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "events":
        # EVENTS
        res = sq.execute("SELECT * FROM events;")
        q = f"""
            INSERT INTO events.events(
	        id, wallet, name, info, closing_date, event_start_date, event_end_date, amount_tickets, price_per_ticket, sold, "time")
	        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, to_timestamp(%s));
        """
        insert_to_pg(q, res.fetchall())
        # EVENT TICKETS
        res = sq.execute("SELECT * FROM ticket;")
        q = f"""
            INSERT INTO events.ticket(
            id, wallet, event, name, email, registered, paid, "time")
            VALUES (%s, %s, %s, %s, %s, %s::boolean, %s::boolean, to_timestamp(%s));
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "example":
        # Example doesn't have a database at the moment
        pass
    elif schema == "hivemind":
        # Hivemind doesn't have a database at the moment
        pass
    elif schema == "jukebox":
        # JUKEBOXES
        res = sq.execute("SELECT * FROM jukebox;")
        q = f"""
            INSERT INTO jukebox.jukebox(
            id, "user", title, wallet, inkey, sp_user, sp_secret, sp_access_token, sp_refresh_token, sp_device, sp_playlists, price, profit)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
        # JUKEBOX PAYMENTS
        res = sq.execute("SELECT * FROM jukebox_payment;")
        q = f"""
            INSERT INTO jukebox.jukebox_payment(
            payment_hash, juke_id, song_id, paid)
            VALUES (%s, %s, %s, %s::boolean);
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "withdraw":
        # WITHDRAW LINK
        res = sq.execute("SELECT * FROM withdraw_link;")
        q = f"""
            INSERT INTO withdraw.withdraw_link (
                id,
                wallet,
                title,
                min_withdrawable,
                max_withdrawable,
                uses,
                wait_time,
                is_unique,
                unique_hash,
                k1,
                open_time,
                used,
                usescsv,
                webhook_url,
                custom_url
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
        # WITHDRAW HASH CHECK
        res = sq.execute("SELECT * FROM hash_check;")
        q = f"""
            INSERT INTO withdraw.hash_check (id, lnurl_id)
            VALUES (%s, %s);
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "watchonly":
        # WALLETS
        res = sq.execute("SELECT * FROM wallets;")
        q = f"""
            INSERT INTO watchonly.wallets (
                id,
                "user",
                masterpub,
                title,
                address_no,
                balance
            )
            VALUES (%s, %s, %s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
        # ADDRESSES
        res = sq.execute("SELECT * FROM addresses;")
        q = f"""
            INSERT INTO watchonly.addresses (id, address, wallet, amount)
            VALUES (%s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
        # MEMPOOL
        res = sq.execute("SELECT * FROM mempool;")
        q = f"""
            INSERT INTO watchonly.mempool ("user", endpoint)
            VALUES (%s, %s);
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "usermanager":
        # USERS
        res = sq.execute("SELECT * FROM users;")
        q = f"""
            INSERT INTO usermanager.users (id, name, admin, email, password)
            VALUES (%s, %s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
        # WALLETS
        res = sq.execute("SELECT * FROM wallets;")
        q = f"""
            INSERT INTO usermanager.wallets (id, admin, name, "user", adminkey, inkey)
            VALUES (%s, %s, %s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "tpos":
        # TPOSS
        res = sq.execute("SELECT * FROM tposs;")
        q = f"""
            INSERT INTO tpos.tposs (id, wallet, name, currency, tip_wallet, tip_options)
            VALUES (%s, %s, %s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "tipjar":
        # TIPJARS
        res = sq.execute("SELECT * FROM TipJars;")
        q = f"""
            INSERT INTO tipjar.TipJars (id, name, wallet, onchain, webhook)
            VALUES (%s, %s, %s, %s, %s);
        """
        pay_links = res.fetchall()
        insert_to_pg(q, pay_links)
        fix_id("tipjar.tipjars_id_seq", pay_links)
        # TIPS
        res = sq.execute("SELECT * FROM Tips;")
        q = f"""
            INSERT INTO tipjar.Tips (id, wallet, name, message, sats, tipjar)
            VALUES (%s, %s, %s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "subdomains":
        # DOMAIN
        res = sq.execute("SELECT * FROM domain;")
        q = f"""
            INSERT INTO subdomains.domain (
                id,
                wallet,
                domain,
                webhook,
                cf_token,
                cf_zone_id,
                description,
                cost,
                amountmade,
                allowed_record_types,
                time
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, to_timestamp(%s));
        """
        insert_to_pg(q, res.fetchall())
        # SUBDOMAIN
        res = sq.execute("SELECT * FROM subdomain;")
        q = f"""
            INSERT INTO subdomains.subdomain (
                id,
                domain,
                email,
                subdomain,
                ip,
                wallet,
                sats,
                duration,
                paid,
                record_type,
                time
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::boolean, %s, to_timestamp(%s));
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "streamalerts":
        # SERVICES
        res = sq.execute("SELECT * FROM Services;")
        q = f"""
            INSERT INTO streamalerts.Services (
                id,
                state,
                twitchuser,
                client_id,
                client_secret,
                wallet,
                onchain,
                servicename,
                authenticated,
                token
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::boolean, %s);
        """
        services = res.fetchall()
        insert_to_pg(q, services)
        fix_id("streamalerts.services_id_seq", services)
        # DONATIONS
        res = sq.execute("SELECT * FROM Donations;")
        q = f"""
            INSERT INTO streamalerts.Donations (
                id,
                wallet,
                name,
                message,
                cur_code,
                sats,
                amount,
                service,
                posted,
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::boolean);
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "splitpayments":
        # TARGETS
        res = sq.execute("SELECT * FROM targets;")
        q = f"""
            INSERT INTO splitpayments.targets (wallet, source, percent, alias)
            VALUES (%s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "satspay":
        # CHARGES
        res = sq.execute("SELECT * FROM charges;")
        q = f"""
            INSERT INTO satspay.charges (
                id,
                "user",
                description,
                onchainwallet,
                onchainaddress,
                lnbitswallet,
                payment_request,
                payment_hash,
                webhook,
                completelink,
                completelinktext,
                time,
                amount,
                balance,
                timestamp
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, to_timestamp(%s));
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "satsdice":
        # SATSDICE PAY
        res = sq.execute("SELECT * FROM satsdice_pay;")
        q = f"""
            INSERT INTO satsdice.satsdice_pay (
                id,
                wallet,
                title,
                min_bet,
                max_bet,
                amount,
                served_meta,
                served_pr,
                multiplier,
                haircut,
                chance,
                base_url,
                open_time
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
        # SATSDICE WITHDRAW
        res = sq.execute("SELECT * FROM satsdice_withdraw;")
        q = f"""
            INSERT INTO satsdice.satsdice_withdraw (
                id,
                satsdice_pay,
                value,
                unique_hash,
                k1,
                open_time,
                used
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
        # SATSDICE PAYMENT
        res = sq.execute("SELECT * FROM satsdice_payment;")
        q = f"""
            INSERT INTO satsdice.satsdice_payment (
                payment_hash,
                satsdice_pay,
                value,
                paid,
                lost
            )
            VALUES (%s, %s, %s, %s::boolean, %s::boolean);
        """
        insert_to_pg(q, res.fetchall())
        # SATSDICE HASH CHECK
        res = sq.execute("SELECT * FROM hash_checkw;")
        q = f"""
            INSERT INTO satsdice.hash_checkw (id, lnurl_id)
            VALUES (%s, %s);
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "paywall":
        # PAYWALLS
        res = sq.execute("SELECT * FROM paywalls;")
        q = f"""
            INSERT INTO paywall.paywalls(
                id,
                wallet,
                url,
                memo,
                description,
                amount,
                time,
                remembers,
                extras
            )
            VALUES (%s, %s, %s, %s, %s, %s, to_timestamp(%s), %s, %s);
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "offlineshop":
        # SHOPS
        res = sq.execute("SELECT * FROM shops;")
        q = f"""
            INSERT INTO offlineshop.shops (id, wallet, method, wordlist)
            VALUES (%s, %s, %s, %s);
        """
        shops = res.fetchall()
        insert_to_pg(q, shops)
        fix_id("offlineshop.shops_id_seq", shops)
        # ITEMS
        res = sq.execute("SELECT * FROM items;")
        q = f"""
            INSERT INTO offlineshop.items (shop, id, name, description, image, enabled, price, unit)
            VALUES (%s, %s, %s, %s, %s, %s::boolean, %s, %s);
        """
        items = res.fetchall()
        insert_to_pg(q, items)
        fix_id("offlineshop.items_id_seq", items)
    elif schema == "lnurlpos" or schema == "lnurldevice":
        # lnurldevice
        res = sq.execute("SELECT * FROM lnurldevices;")
        q = f"""
            INSERT INTO lnurldevice.lnurldevices (id, key, title, wallet, currency, device, profit, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, to_timestamp(%s));
        """
        insert_to_pg(q, res.fetchall())
        # lnurldevice PAYMENT
        res = sq.execute("SELECT * FROM lnurldevicepayment;")
        q = f"""
            INSERT INTO lnurldevice.lnurldevicepayment (id, deviceid, payhash, payload, pin, sats, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, to_timestamp(%s));
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "lnurlp":
        # PAY LINKS
        res = sq.execute("SELECT * FROM pay_links;")
        q = f"""
            INSERT INTO lnurlp.pay_links (
                id,
                wallet,
                description,
                min,
                served_meta,
                served_pr,
                webhook_url,
                success_text,
                success_url,
                currency,
                comment_chars,
                max,
                fiat_base_multiplier
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        pay_links = res.fetchall()
        insert_to_pg(q, pay_links)
        fix_id("lnurlp.pay_links_id_seq", pay_links)
    elif schema == "lndhub":
        # LndHub doesn't have a database at the moment
        pass
    elif schema == "lnticket":
        # TICKET
        res = sq.execute("SELECT * FROM ticket;")
        q = f"""
            INSERT INTO lnticket.ticket (
                id,
                form,
                email,
                ltext,
                name,
                wallet,
                sats,
                paid,
                time
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::boolean, to_timestamp(%s));
        """
        insert_to_pg(q, res.fetchall())
        # FORM
        res = sq.execute("SELECT * FROM form2;")
        q = f"""
            INSERT INTO lnticket.form2 (
                id,
                wallet,
                name,
                webhook,
                description,
                flatrate,
                amount,
                amountmade,
                time
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, to_timestamp(%s));
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "livestream":
        # LIVESTREAMS
        res = sq.execute("SELECT * FROM livestreams;")
        q = f"""
            INSERT INTO livestream.livestreams (
                id,
                wallet,
                fee_pct,
                current_track
            )
            VALUES (%s, %s, %s, %s);
        """
        livestreams = res.fetchall()
        insert_to_pg(q, livestreams)
        fix_id("livestream.livestreams_id_seq", livestreams)
        # PRODUCERS
        res = sq.execute("SELECT * FROM producers;")
        q = f"""
            INSERT INTO livestream.producers (
                livestream,
                id,
                "user",
                wallet,
                name
            )
            VALUES (%s, %s, %s, %s, %s);
        """
        producers = res.fetchall()
        insert_to_pg(q, producers)
        fix_id("livestream.producers_id_seq", producers)
        # TRACKS
        res = sq.execute("SELECT * FROM tracks;")
        q = f"""
            INSERT INTO livestream.tracks (
                livestream,
                id,
                download_url,
                price_msat,
                name,
                producer
            )
            VALUES (%s, %s, %s, %s, %s, %s);
        """
        tracks = res.fetchall()
        insert_to_pg(q, tracks)
        fix_id("livestream.tracks_id_seq", tracks)
    elif schema == "lnaddress":
        # DOMAINS
        res = sq.execute("SELECT * FROM domain;")
        q = f"""
            INSERT INTO lnaddress.domain(
	        id, wallet, domain, webhook, cf_token, cf_zone_id, cost, "time")
	        VALUES (%s, %s, %s, %s, %s, %s, %s, to_timestamp(%s));
        """
        insert_to_pg(q, res.fetchall())
        # ADDRESSES
        res = sq.execute("SELECT * FROM address;")
        q = f"""
            INSERT INTO lnaddress.address(
            id, wallet, domain, email, username, wallet_key, wallet_endpoint, sats, duration, paid, "time")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::boolean, to_timestamp(%s));
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "discordbot":
        # USERS
        res = sq.execute("SELECT * FROM users;")
        q = f"""
            INSERT INTO discordbot.users(
	        id, name, admin, discord_id)
	        VALUES (%s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
        # WALLETS
        res = sq.execute("SELECT * FROM wallets;")
        q = f"""
            INSERT INTO discordbot.wallets(
            id, admin, name, "user", adminkey, inkey)
            VALUES (%s, %s, %s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
    else:
        print(f"❌ Not implemented: {schema}")
        sq.close()

        if ignore_missing == False:
            raise Exception(
                f"Not implemented: {schema}. Use --ignore-missing to skip missing extensions."
            )
        return

    print(f"✅ Migrated: {schema}")
    sq.close()


parser = argparse.ArgumentParser(
    description="LNbits migration tool for migrating data from SQLite to PostgreSQL"
)
parser.add_argument(
    dest="sqlite_path",
    const=True,
    nargs="?",
    help=f"SQLite DB folder *or* single extension db file to migrate. Default: {sqfolder}",
    default=sqfolder,
    type=str,
)
parser.add_argument(
    "-e",
    "--extensions-only",
    help="Migrate only extensions",
    required=False,
    default=False,
    action="store_true",
)

parser.add_argument(
    "-s",
    "--skip-missing",
    help="Error if migration is missing for an extension",
    required=False,
    default=False,
    action="store_true",
)

parser.add_argument(
    "-i",
    "--ignore-errors",
    help="Don't error if migration fails",
    required=False,
    default=False,
    action="store_true",
)

args = parser.parse_args()

print("Selected path: ", args.sqlite_path)

if os.path.isdir(args.sqlite_path):
    file = os.path.join(args.sqlite_path, "database.sqlite3")
    check_db_versions(file)
    if not args.extensions_only:
        print(f"Migrating: {file}")
        migrate_core(file)

if os.path.isdir(args.sqlite_path):
    files = [
        os.path.join(args.sqlite_path, file) for file in os.listdir(args.sqlite_path)
    ]
else:
    files = [args.sqlite_path]

for file in files:
    filename = os.path.basename(file)
    if filename.startswith("ext_"):
        schema = filename.replace("ext_", "").split(".")[0]
        print(f"Migrating: {file}")
        migrate_ext(
            file,
            schema,
            ignore_missing=args.skip_missing,
        )
