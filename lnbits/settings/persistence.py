from __future__ import annotations

from pydantic import Field

from .lnbits import LNbitsSettings


class PersistenceSettings(LNbitsSettings):
    lnbits_data_folder: str = Field(default="./data")
    lnbits_database_url: str = Field(default=None)
