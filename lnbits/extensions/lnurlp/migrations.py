def m001_initial(db):
    """
    Initial pay table.
    """
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS pay_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet TEXT NOT NULL,
            description TEXT NOT NULL,
            amount INTEGER NOT NULL,
            served_meta INTEGER NOT NULL,
            served_pr INTEGER NOT NULL
        );
        """
    )


# def m002_webhooks_and_success_actions(db):
#     """
#     Webhooks and success actions.
#     """
#     db.execute("ALTER TABLE pay_links ADD COLUMN webhook_url TEXT;")
#     db.execute("ALTER TABLE pay_links ADD COLUMN success_text TEXT;")
#     db.execute("ALTER TABLE pay_links ADD COLUMN success_url TEXT;")
#     db.execute(
#         """
#         CREATE TABLE invoices (
#             payment_hash PRIMARY KEY,
#             link_id INTEGER NOT NULL REFERENCES pay_links (id),
#             webhook_sent BOOLEAN NOT NULL DEFAULT false
#         );
#         """
#     )
