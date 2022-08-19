import json
from sqlite3 import Row
from typing import Dict, Optional
from urllib.parse import ParseResult, parse_qs, urlencode, urlparse, urlunparse

from fastapi.param_functions import Query
from pydantic import BaseModel
from starlette.requests import Request

class CreatePodcastData(BaseModel):
    wallet: str = Query(None)
    podcast_title: str = Query(None)
    description: str = Query(None)
    podcast_title: str = Query(None)
    cover_image: str = Query(None)
    no_episodes: int = Query(100, ge=1)
    categories: str = Query(None)
    country_origin: str = Query(None)
    hostname: str = Query(None)
    email: str = Query(None)
    website: str = Query(None)
    explicit: str = Query(None)
    language: str = Query(None)
    copyright: str = Query(None)

class Podcast(BaseModel):
    id: str
    wallet: str
    podcast_title: str
    description: str
    podcast_title: str
    cover_image: Optional[str]
    no_episodes: int
    categories: str
    country_origin: str
    hostname: str
    email: str
    website: str
    explicit: bool
    language: str
    copyright: str

    @classmethod
    def from_row(cls, row: Row) -> "Podcast":
        return cls(**dict(row))

class CreateEpisodeData(BaseModel):
    podcast: str = Query(None)
    episode_title: str = Query(None)
    description: str = Query(None)
    media_file: str = Query(None)
    keywords: str = Query(None)
    series_no: int = Query(100, ge=1)
    episode_no: int = Query(100, ge=1)
    episode_type: str = Query(None)
    episode_image: str = Query(None)
    publish_time: str = Query(None)

class Episode(BaseModel):
    id: str
    podcast: str
    episode_title: str
    description: str
    media_file: str
    keywords: str
    series_no: int
    episode_no: int
    episode_type: str
    episode_image: str
    publish_time: str

    @classmethod
    def from_row(cls, row: Row) -> "Episode":
        return cls(**dict(row))