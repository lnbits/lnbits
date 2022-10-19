from typing import Any, List, Optional

from cashu.core.base import MintKeyset

from lnbits.db import Connection, Database
from lnbits.helpers import urlsafe_short_hash

from .models import Invoice, Proof


class LedgerCrud:
    """
    Database interface for Cashu mint.

    This class needs to be overloaded by any app that imports the Cashu mint.
    """

    def __init__(self, db: Database):
        self.db = db

    async def get_keyset(
        self,
        id: str = None,
        derivation_path: str = "",
        db: Database = None,
        conn: Optional[Connection] = None,
    ):
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

        rows = await self.db.fetchall(  # type: ignore
            f"""
            SELECT * from cashu.keysets
            {where}
            """,
            tuple(values),
        )
        return [MintKeyset.from_row(row) for row in rows]

    async def get_lightning_invoice(self, cashu_id: str, hash: str):
        row = await self.db.fetchone(
            """
            SELECT * from cashu.invoices
            WHERE cashu_id =? AND hash = ?
            """,
            (
                cashu_id,
                hash,
            ),
        )
        return Invoice.from_row(row)

    async def get_proofs_used(
        self,
        db: Database,
        conn: Optional[Connection] = None,
    ):

        rows = await self.db.fetchall(
            """
            SELECT secret from cashu.proofs_used
            """
        )
        return [row[0] for row in rows]

    async def invalidate_proof(self, cashu_id: str, proof: Proof):
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
                cashu_id,
            ),
        )

    async def store_keyset(
        self,
        keyset: MintKeyset,
        db: Database = None,
        conn: Optional[Connection] = None,
    ):

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

    async def store_lightning_invoice(self, cashu_id: str, invoice: Invoice, **kwargs):
        await self.db.execute(
            """
            INSERT INTO cashu.invoices
            (cashu_id, amount, pr, hash, issued)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                cashu_id,
                invoice.amount,
                invoice.pr,
                invoice.hash,
                invoice.issued,
            ),
        )

    async def store_promise(self, amount: int, B_: str, C_: str, cashu_id: str):
        promise_id = urlsafe_short_hash()

        await self.db.execute(
            """
            INSERT INTO cashu.promises
            (id, amount, B_b, C_b, cashu_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (promise_id, amount, str(B_), str(C_), cashu_id),
        )

    async def update_lightning_invoice(self, cashu_id: str, hash: str, issued: bool):
        await self.db.execute(
            "UPDATE cashu.invoices SET issued = ? WHERE cashu_id = ? AND hash = ?",
            (
                issued,
                cashu_id,
                hash,
            ),
        )
