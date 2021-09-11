## Returning data from API calls
**old:**
```python
return (
    {
        "id": wallet.wallet.id, 
        "name": wallet.wallet.name, 
        "balance": wallet.wallet.balance_msat
    },
    HTTPStatus.OK,
)
```
FastAPI returns `HTTPStatus.OK` by default id no Exception is raised

**new:**
```python
return {
    "id": wallet.wallet.id, 
    "name": wallet.wallet.name, 
    "balance": wallet.wallet.balance_msat
}
```

To change the default HTTPStatus, add it to the path decorator
```python
@core_app.post("/api/v1/payments", status_code=HTTPStatus.CREATED)
async def payments():
    pass
```

## Raise exceptions
**old:**
```python
return (
    {"message": f"Failed to connect to {domain}."},
    HTTPStatus.BAD_REQUEST,
)
# or the Quart way via abort function
abort(HTTPStatus.INTERNAL_SERVER_ERROR, "Could not process withdraw LNURL.")
```

**new:**

Raise an exception to return a status code other than the default status code.
```python
raise HTTPException(
    status_code=HTTPStatus.BAD_REQUEST,
    detail=f"Failed to connect to {domain}."
)
```
## Possible optimizations
### Use Redis as a cache server
Instead of hitting the database over and over again, we can store a short lived object in [Redis](https://redis.io) for an arbitrary key.
Example:
* Get transactions for a wallet ID
* User data for a user id
* Wallet data for a Admin / Invoice key