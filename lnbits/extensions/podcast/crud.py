from typing import List, Optional, Union

from lnbits.db import SQLITE

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import CreatePodcastData, Podcast, CreateEpisodeData, Episode

#########PODCASTS##########

async def create_Podcast(data: CreatePodcastData, wallet_id: str) -> Podcast:

    returning = "" if db.type == SQLITE else "RETURNING ID"
    method = db.execute if db.type == SQLITE else db.fetchone
    pod_id = urlsafe_short_hash()
    result = await (method)(
        f"""
        INSERT INTO podcast.Podcast (
            id,
            wallet,
            podcast_title,
            description,
            cover_image,
            no_episodes,
            categories,
            country_origin,
            hostname,
            email,
            website,
            explicit,
            language,
            copyright
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        {returning}
        """,
        (   
            pod_id,
            wallet_id,
            data.podcast_title,
            data.description,
            data.cover_image,
            data.no_episodes,
            data.categories,
            data.country_origin,
            data.hostname,
            data.email,
            data.website,
            data.explicit,
            data.language,
            data.copyright,
        ),
    )

    pod = await get_Podcast(pod_id)
    assert pod, "Newly created pod couldn't be retrieved"
    return pod


async def get_Podcast(pod_id: int) -> Optional[Podcast]:
    row = await db.fetchone("SELECT * FROM podcast.Podcast WHERE id = ?", (pod_id,))
    return Podcast.from_row(row) if row else None


async def get_Podcasts(wallet_ids: Union[str, List[str]]) -> List[Podcast]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"""
        SELECT * FROM podcast.Podcast WHERE wallet IN ({q})
        """,
        (*wallet_ids,),
    )
    return [Podcast.from_row(row) for row in rows]


async def update_Podcast(pod_id: int, **kwargs) -> Optional[Podcast]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE podcast.Podcast SET {q} WHERE id = ?", (*kwargs.values(), pod_id)
    )
    row = await db.fetchone("SELECT * FROM podcast.Podcast WHERE id = ?", (pod_id,))
    return Podcast.from_row(row) if row else None


async def delete_Podcast(pod_id: int) -> None:
    await db.execute("DELETE FROM podcast.Podcast WHERE id = ?", (pod_id,))


#########EPISODES##########

async def create_Episode(data: CreateEpisodeData, wallet_id: str) -> Episode:

    returning = "" if db.type == SQLITE else "RETURNING ID"
    method = db.execute if db.type == SQLITE else db.fetchone
    eps_id = urlsafe_short_hash()
    result = await (method)(
        f"""
        INSERT INTO podcast.Episode (
            eps_id,
            podcast,
            episode_title,
            description,
            media_file,
            keywords,
            series_no,
            episode_no,
            episode_type,
            episode_image,
            publish_time
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        {returning}
        """,
        (
            eps_id,
            data.podcast,
            data.episode_title,
            data.description,
            data.media_file,
            data.keywords,
            data.series_no,
            data.episode_no,
            data.episode_type,
            data.episode_image,
            data.publish_time,
        ),
    )

    eps = await get_Episode(pod_id)
    assert eps, "Newly created pod couldn't be retrieved"
    return eps

async def get_Episode(pod_id: int) -> Optional[Episode]:
    row = await db.fetchone("SELECT * FROM podcast.Episode WHERE id = ?", (pod_id,))
    return Episode.from_row(row) if row else None


async def get_Episodes(wallet_ids: Union[str, List[str]]) -> List[Episode]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"""
        SELECT * FROM podcast.Episode WHERE wallet IN ({q})
        ORDER BY Id
        """,
        (*wallet_ids,),
    )
    return [Episode.from_row(row) for row in rows]


async def update_Episode(pod_id: int, **kwargs) -> Optional[Episode]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE podcast.Episode SET {q} WHERE id = ?", (*kwargs.values(), pod_id)
    )
    row = await db.fetchone("SELECT * FROM podcast.Episode WHERE id = ?", (pod_id,))
    return Episode.from_row(row) if row else None


async def delete_Episode(pod_id: int) -> None:
    await db.execute("DELETE FROM podcast.Episode WHERE id = ?", (pod_id,))