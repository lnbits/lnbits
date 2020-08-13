from lnbits.db import open_ext_db

def m001_initial(db):

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS forms (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            costpword INTEGER NOT NULL,
            amountmade INTEGER NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
    """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            paid BOOLEAN NOT NULL,
            form TEXT NOT NULL,
            email TEXT NOT NULL,
            ltext TEXT NOT NULL,
            name TEXT NOT NULL,
            wallet TEXT NOT NULL,
            sats INTEGER NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
    """
    )


def m002_changed(db):

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS ticket (
            id TEXT PRIMARY KEY,
            paid BOOLEAN NOT NULL,
            form TEXT NOT NULL,
            email TEXT NOT NULL,
            ltext TEXT NOT NULL,
            name TEXT NOT NULL,
            wallet TEXT NOT NULL,
            sats INTEGER NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
    """
    )
    
    for row in [list(row) for row in db.fetchall("SELECT * FROM tickets")]:
        usescsv = ""

        for i in range(row[5]):
            if row[7]:
                usescsv += "," + str(i + 1)
            else:
                usescsv += "," + str(1)
        usescsv = usescsv[1:]  
        db.execute(
            """
            INSERT INTO ticket (
                id,
                paid,
                title,
                form,
                email,
                ltext,
                name,
                wallet,
                sats
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row[0], 
                True,  
                row[1], 
                row[2], 
                row[3],
                row[4], 
                row[5], 
                row[6], 
                row[7],
                row[8],
            ),
        )
    db.execute("DROP TABLE tickets")

        
def migrate():
    with open_ext_db("lnticket") as db:
        m001_initial(db)
        m002_changed(db)
