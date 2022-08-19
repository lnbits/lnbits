async def m001_initial(db):
    """
    Initial Podcast table.
    """
    await db.execute(
        f"""
        CREATE TABLE podcast.Podcast (
            id TEXT PRIMARY KEY,
            podcast_title TEXT NOT NULL,
            description TEXT NOT NULL,
            wallet TEXT NOT NULL,
            cover_image TEXT NOT NULL,
            no_episodes INTEGER NOT NULL,
            categories TEXT NOT NULL,
            country_origin TEXT NOT NULL,
            hostname TEXT NOT NULL,
            email TEXT NOT NULL,
            website TEXT NOT NULL,
            explicit BOOL NOT NULL,
            language TEXT NOT NULL,
            copyright TEXT NOT NULL
        );
        """
    )

    await db.execute(
        f"""
        CREATE TABLE podcast.Episode (
            id TEXT PRIMARY KEY,
            podcast TEXT NOT NULL,
            episode_title TEXT NOT NULL,
            description TEXT NOT NULL,
            media_file TEXT NOT NULL,
            keywords TEXT NOT NULL,
            series_no TEXT NOT NULL,
            episode_no TEXT NOT NULL,
            episode_type TEXT NOT NULL,
            episode_image TEXT NOT NULL,
            publish_time TEXT NOT NULL
        );
        """
    )