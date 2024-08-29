import random
import string
from typing import Optional

from psycopg2 import connect
from psycopg2.errors import InvalidCatalogName

from lnbits import core
from lnbits.db import DB_TYPE, POSTGRES, FromRowModel
from lnbits.wallets import get_funding_source, set_funding_source


class FakeError(Exception):
    pass


class DbTestModel(FromRowModel):
    id: int
    name: str
    value: Optional[str] = None


def get_random_string(iterations: int = 10):
    return "".join(
        random.SystemRandom().choice(string.ascii_uppercase + string.digits)
        for _ in range(iterations)
    )


async def get_random_invoice_data():
    return {"out": False, "amount": 10, "memo": f"test_memo_{get_random_string(10)}"}


set_funding_source()
funding_source = get_funding_source()
is_fake: bool = funding_source.__class__.__name__ == "FakeWallet"
is_regtest: bool = not is_fake


def clean_database(settings):
    if DB_TYPE == POSTGRES:
        conn = connect(settings.lnbits_database_url)
        conn.autocommit = True
        with conn.cursor() as cur:
            try:
                cur.execute("DROP DATABASE lnbits_test")
            except InvalidCatalogName:
                pass
            cur.execute("CREATE DATABASE lnbits_test")
        core.db.__init__("database")
        conn.close()
    else:
        # TODO: do this once mock data is removed from test data folder
        # os.remove(settings.lnbits_data_folder + "/database.sqlite3")
        pass
