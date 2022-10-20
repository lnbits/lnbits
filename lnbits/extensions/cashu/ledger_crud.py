from typing import Any, List, Optional

from cashu.core.base import MintKeyset
from cashu.core.migrations import migrate_databases
from cashu.mint import migrations
from cashu.mint.ledger import Ledger

from lnbits.db import Database
from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import Invoice, Proof

cached_ledgers = {}


async def cashu_ledger(cashu_id: str):
    if cashu_id in cached_ledgers:
        return cached_ledgers[cashu_id]

    ledger = Ledger(
        db=db,
        crud=LedgerCrud(db, cashu_id),
        # seed=MINT_PRIVATE_KEY,
        seed="asd",
        derivation_path="0/0/0/1",
    )
    # await migrate_databases(db, migrations)
    await ledger.load_used_proofs()
    await ledger.init_keysets()
    cached_ledgers[cashu_id] = ledger
    return ledger


class LedgerCrud:
    """
    Database interface for Cashu mint.

    This class needs to be overloaded by any app that imports the Cashu mint.
    """

    def __init__(self, db: Database, cashu_id: str):
        self.db = db
        self.cashu_id = cashu_id

    async def get_keyset(self, id: str = None, derivation_path: str = "", **kwargs):
        clauses = []
        values: List[Any] = []
        clauses.append("active = ?")
        values.append(True)
        if id:
            clauses.append("id = ?")
            values.append(id)
        if derivation_path:
            clauses.append("derivation_path = ?")
            values.append(derivation_path)
        where = ""
        if clauses:
            where = f"WHERE {' AND '.join(clauses)}"

        print("### SELECT this: ", where, values)
        rows = await self.db.fetchall(  # type: ignore
            f"""
            SELECT * from cashu.keysets
            {where}
            """,
            tuple(values),
        )
        print("### SELECT this: ", where, values)
        print("### rows", rows)
        return [MintKeyset.from_row(row) for row in rows]

    async def get_lightning_invoice(self, hash: str, **kwargs):
        row = await self.db.fetchone(
            """
            SELECT * from cashu.invoices
            WHERE cashu_id =? AND hash = ?
            """,
            (
                self.cashu_id,
                hash,
            ),
        )
        return Invoice.from_row(row)

    async def get_proofs_used(self, **kwargs):

        rows = await self.db.fetchall(
            """
            SELECT secret from cashu.proofs_used
            """
        )
        return [row[0] for row in rows]

    async def invalidate_proof(self, proof: Proof, **kwargs):
        invalidate_proof_id = urlsafe_short_hash()
        await self.db.execute(
            """
            INSERT INTO cashu.proofs_used
            (id, amount, C, secret, cashu_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                invalidate_proof_id,
                proof.amount,
                str(proof.C),
                str(proof.secret),
                self.cashu_id,
            ),
        )

    async def store_keyset(self, keyset: MintKeyset, **kwargs):

        await self.db.execute(  # type: ignore
            """
            INSERT INTO cashu.keysets
            (id, derivation_path, valid_from, valid_to, first_seen, active, version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                keyset.id,
                keyset.derivation_path,
                keyset.valid_from or self.db.timestamp_now,
                keyset.valid_to or self.db.timestamp_now,
                keyset.first_seen or self.db.timestamp_now,
                True,
                keyset.version,
            ),
        )

    async def store_lightning_invoice(self, invoice: Invoice, **kwargs):
        await self.db.execute(
            """
            INSERT INTO cashu.invoices
            (cashu_id, amount, pr, hash, issued)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                self.cashu_id,
                invoice.amount,
                invoice.pr,
                invoice.hash,
                invoice.issued,
            ),
        )

    async def store_promise(self, amount: int, B_: str, C_: str, **kwargs):
        promise_id = urlsafe_short_hash()

        await self.db.execute(
            """
            INSERT INTO cashu.promises
            (id, amount, B_b, C_b, cashu_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (promise_id, amount, str(B_), str(C_), self.cashu_id),
        )

    async def update_lightning_invoice(self, hash: str, issued: bool, **kwargs):
        await self.db.execute(
            "UPDATE cashu.invoices SET issued = ? WHERE cashu_id = ? AND hash = ?",
            (
                issued,
                self.cashu_id,
                hash,
            ),
        )
