from lnbits.core.db import db
from lnbits.core.models.users import Account
from lnbits.db import Connection


async def get_account_by_sso(
    provider: str, subject: str, conn: Connection | None = None
) -> Account | None:
    return await (conn or db).fetchone(
        """
        SELECT accounts.* FROM accounts
        JOIN sso_identities ON sso_identities.user_id = accounts.id
        WHERE sso_identities.provider = :provider AND sso_identities.subject = :subject
        """,
        {"provider": provider, "subject": subject},
        Account,
    )


async def has_sso_identity(user_id: str, conn: Connection | None = None) -> bool:
    return bool(
        await (conn or db).fetchone(
            "SELECT user_id FROM sso_identities WHERE user_id = :user_id LIMIT 1",
            {"user_id": user_id},
        )
    )


async def link_sso_identity(
    provider: str, subject: str, user_id: str, conn: Connection | None = None
) -> None:
    async with db.reuse_conn(conn) if conn else db.connect() as connection:
        await connection.execute(
            """
            INSERT INTO sso_identities (provider, subject, user_id)
            VALUES (:provider, :subject, :user_id)
            ON CONFLICT (provider, subject) DO NOTHING
            """,
            {"provider": provider, "subject": subject, "user_id": user_id},
        )
        account = await get_account_by_sso(provider, subject, conn=connection)
        if not account or account.id != user_id:
            raise ValueError("SSO identity is already linked to another account.")
