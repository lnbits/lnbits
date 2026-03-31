from datetime import datetime, timezone

from pydantic import BaseModel, Field


class TinyURL(BaseModel):
    id: str
    url: str
    endless: bool
    wallet: str
    time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
