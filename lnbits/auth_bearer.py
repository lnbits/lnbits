from fastapi import Request, HTTPException
from fastapi.security.api_key import APIKeyQuery, APIKeyCookie, APIKeyHeader, APIKey

# https://medium.com/data-rebels/fastapi-authentication-revisited-enabling-api-key-authentication-122dc5975680

from fastapi import Security, Depends, FastAPI, HTTPException
from fastapi.security.api_key import APIKeyQuery, APIKeyCookie, APIKeyHeader, APIKey
from fastapi.security.base import SecurityBase



API_KEY = "usr"
API_KEY_NAME = "X-API-key"

api_key_query = APIKeyQuery(name=API_KEY_NAME, auto_error=False)
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)



class AuthBearer(SecurityBase):
    def __init__(self, scheme_name: str = None, auto_error: bool = True):
        self.scheme_name = scheme_name or self.__class__.__name__
        self.auto_error = auto_error
        
    async def __call__(self, request: Request):
        key = await self.get_api_key()
        print(key)
        # credentials: HTTPAuthorizationCredentials = await super(AuthBearer, self).__call__(request)
        # if credentials:
        #     if not credentials.scheme == "Bearer":
        #         raise HTTPException(
        #             status_code=403, detail="Invalid authentication scheme.")
        #     if not self.verify_jwt(credentials.credentials):
        #         raise HTTPException(
        #             status_code=403, detail="Invalid token or expired token.")
        #     return credentials.credentials
        # else:
        #     raise HTTPException(
        #         status_code=403, detail="Invalid authorization code.")
    async def get_api_key(self,
        api_key_query: str = Security(api_key_query),
        api_key_header: str = Security(api_key_header),
    ):
        if api_key_query == API_KEY:
            return api_key_query
        elif api_key_header == API_KEY:
            return api_key_header
        else:
            raise HTTPException(status_code=403, detail="Could not validate credentials")