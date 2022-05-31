async def m001_initial(db):
    """
    Initial copilot table.
    """

    await db.execute(
        f"""
        CREATE TABLE copilot.copilots (
            id TEXT NOT NULL PRIMARY KEY,
            "user" TEXT,
            title TEXT,
            lnurl_toggle INTEGER,
            wallet TEXT,
            animation1 TEXT,
            animation2 TEXT,
            animation3 TEXT,
            animation1threshold INTEGER,
            animation2threshold INTEGER,
            animation3threshold INTEGER,
            animation1webhook TEXT,
            animation2webhook TEXT,
            animation3webhook TEXT,
            lnurl_title TEXT,
            show_message INTEGER,
            show_ack INTEGER,
            show_price INTEGER,
            amount_made INTEGER,
            fullscreen_cam INTEGER,
            iframe_url TEXT,
            timestamp TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )


async def m002_fix_data_types(db):
    """
    Fix data types.
    """

    if db.type != "SQLITE":
        await db.execute(
            "ALTER TABLE copilot.copilots ALTER COLUMN show_price TYPE TEXT;"
        )


async def m003_fix_data_types(db):
    await db.execute(
        f"""
         CREATE TABLE copilot.newer_copilots (
             id TEXT NOT NULL PRIMARY KEY,
             "user" TEXT,
             title TEXT,
             lnurl_toggle INTEGER,
             wallet TEXT,
             animation1 TEXT,
             animation2 TEXT,
             animation3 TEXT,
             animation1threshold INTEGER,
             animation2threshold INTEGER,
             animation3threshold INTEGER,
             animation1webhook TEXT,
             animation2webhook TEXT,
             animation3webhook TEXT,
             lnurl_title TEXT,
             show_message INTEGER,
             show_ack INTEGER,
             show_price TEXT,
             amount_made INTEGER,
             fullscreen_cam INTEGER,
             iframe_url TEXT,
             timestamp TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
         );
     """
    )

    await db.execute(
        "INSERT INTO copilot.newer_copilots SELECT * FROM copilot.copilots"
    )
