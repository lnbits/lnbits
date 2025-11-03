---
layout: default
title: FastAPI extension upgrade
nav_order: 1
---

## Defining a route with path parameters

**old:**

```python
# with <>
@offlineshop_ext.route("/lnurl/<item_id>", methods=["GET"])
```

**new:**

```python
# with curly braces: {}
@offlineshop_ext.get("/lnurl/{item_id}")
```

## Check if a user exists and access user object

**old:**

```python
# decorators
@check_user_exists()
async def do_routing_stuff():
    pass
```

**new:**
If user doesn't exist, `Depends(check_user_exists)` will raise an exception.
If user exists, `user` will be the user object

```python
# depends calls
@core_html_routes.get("/my_route")
async def extensions(user: User = Depends(check_user_exists)):
    pass
```

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

## Extensions

**old:**

```python
from quart import Blueprint

amilk_ext: Blueprint = Blueprint(
    "amilk", __name__, static_folder="static", template_folder="templates"
)
```

**new:**

```python
from fastapi import APIRouter
from lnbits.jinja2_templating import Jinja2Templates
from lnbits.helpers import template_renderer
from fastapi.staticfiles import StaticFiles

offlineshop_ext: APIRouter = APIRouter(
    prefix="/Extension",
    tags=["Offlineshop"]
)

offlineshop_ext.mount(
    "lnbits/extensions/offlineshop/static",
    StaticFiles("lnbits/extensions/offlineshop/static")
)

offlineshop_rndr = template_renderer([
    "lnbits/extensions/offlineshop/templates",
])
```

## Possible optimizations

### Use Redis as a cache server

Instead of hitting the database over and over again, we can store a short lived object in [Redis](https://redis.io) for an arbitrary key.
Example:

- Get transactions for a wallet ID
- User data for a user id
- Wallet data for a Admin / Invoice key
