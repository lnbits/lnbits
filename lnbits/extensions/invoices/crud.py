from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import (
    CreateInvoiceData,
    CreateInvoiceItemData,
    CreatePaymentData,
    Invoice,
    InvoiceItem,
    Payment,
    UpdateInvoiceData,
    UpdateInvoiceItemData,
)


async def get_invoice(invoice_id: str) -> Optional[Invoice]:
    row = await db.fetchone(
        "SELECT * FROM invoices.invoices WHERE id = ?", (invoice_id,)
    )
    return Invoice.from_row(row) if row else None


async def get_invoice_items(invoice_id: str) -> List[InvoiceItem]:
    rows = await db.fetchall(
        f"SELECT * FROM invoices.invoice_items WHERE invoice_id = ?", (invoice_id,)
    )

    return [InvoiceItem.from_row(row) for row in rows]


async def get_invoice_item(item_id: str) -> InvoiceItem:
    row = await db.fetchone(
        "SELECT * FROM invoices.invoice_items WHERE id = ?", (item_id,)
    )
    return InvoiceItem.from_row(row) if row else None


async def get_invoice_total(items: List[InvoiceItem]) -> int:
    return sum(item.amount for item in items)


async def get_invoices(wallet_ids: Union[str, List[str]]) -> List[Invoice]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM invoices.invoices WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Invoice.from_row(row) for row in rows]


async def get_invoice_payments(invoice_id: str) -> List[Payment]:
    rows = await db.fetchall(
        f"SELECT * FROM invoices.payments WHERE invoice_id = ?", (invoice_id,)
    )

    return [Payment.from_row(row) for row in rows]


async def get_invoice_payment(payment_id: str) -> Payment:
    row = await db.fetchone(
        "SELECT * FROM invoices.payments WHERE id = ?", (payment_id,)
    )
    return Payment.from_row(row) if row else None


async def get_payments_total(payments: List[Payment]) -> int:
    return sum(item.amount for item in payments)


async def create_invoice_internal(wallet_id: str, data: CreateInvoiceData) -> Invoice:
    invoice_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO invoices.invoices (id, wallet, status, currency, company_name, first_name, last_name, email, phone, address)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            invoice_id,
            wallet_id,
            data.status,
            data.currency,
            data.company_name,
            data.first_name,
            data.last_name,
            data.email,
            data.phone,
            data.address,
        ),
    )

    invoice = await get_invoice(invoice_id)
    assert invoice, "Newly created invoice couldn't be retrieved"
    return invoice


async def create_invoice_items(
    invoice_id: str, data: List[CreateInvoiceItemData]
) -> List[InvoiceItem]:
    for item in data:
        item_id = urlsafe_short_hash()
        await db.execute(
            """
            INSERT INTO invoices.invoice_items (id, invoice_id, description, amount)
            VALUES (?, ?, ?, ?)
            """,
            (
                item_id,
                invoice_id,
                item.description,
                int(item.amount * 100),
            ),
        )

    invoice_items = await get_invoice_items(invoice_id)
    return invoice_items


async def update_invoice_internal(wallet_id: str, data: UpdateInvoiceData) -> Invoice:
    await db.execute(
        """
        UPDATE invoices.invoices
        SET wallet = ?, currency = ?, status = ?, company_name = ?, first_name = ?, last_name = ?, email = ?, phone = ?, address = ?
        WHERE id = ?
        """,
        (
            wallet_id,
            data.currency,
            data.status,
            data.company_name,
            data.first_name,
            data.last_name,
            data.email,
            data.phone,
            data.address,
            data.id,
        ),
    )

    invoice = await get_invoice(data.id)
    assert invoice, "Newly updated invoice couldn't be retrieved"
    return invoice


async def update_invoice_items(
    invoice_id: str, data: List[UpdateInvoiceItemData]
) -> List[InvoiceItem]:
    updated_items = []
    for item in data:
        if item.id:
            updated_items.append(item.id)
            await db.execute(
                """
                UPDATE invoices.invoice_items 
                SET description = ?, amount = ?
                WHERE id = ?
                """,
                (item.description, int(item.amount * 100), item.id),
            )

    placeholders = ",".join("?" for i in range(len(updated_items)))
    if not placeholders:
        placeholders = "?"
        updated_items = ("skip",)

    await db.execute(
        f"""
        DELETE FROM invoices.invoice_items 
        WHERE invoice_id = ?
        AND id NOT IN ({placeholders})
        """,
        (
            invoice_id,
            *tuple(updated_items),
        ),
    )

    for item in data:
        if not item.id:
            await create_invoice_items(invoice_id=invoice_id, data=[item])

    invoice_items = await get_invoice_items(invoice_id)
    return invoice_items


async def create_invoice_payment(invoice_id: str, amount: int) -> Payment:
    payment_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO invoices.payments (id, invoice_id, amount)
        VALUES (?, ?, ?)
        """,
        (
            payment_id,
            invoice_id,
            amount,
        ),
    )

    payment = await get_invoice_payment(payment_id)
    assert payment, "Newly created payment couldn't be retrieved"
    return payment
