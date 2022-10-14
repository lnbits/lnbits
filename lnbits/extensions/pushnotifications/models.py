from pydantic import BaseModel

class CreateSubscription(BaseModel):
    subscription: str

class Subscription(BaseModel):
    endpoint: str
    wallet: str
    data: str
    host: str
    timestamp: str
