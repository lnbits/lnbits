from datetime import datetime

from pydantic import BaseModel


class CreateWebPushSubscription(BaseModel):
    subscription: str


class WebPushSubscription(BaseModel):
    endpoint: str
    user: str
    data: str
    host: str
    timestamp: datetime
