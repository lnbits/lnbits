# views_api.py is for you API endpoints that could be hit by another service

# add your dependencies here

# import httpx
# (use httpx just like requests, except instead of response.ok there's only the
#  response.is_error that is its inverse)

from . import example_ext

# add your endpoints here


@example_ext.get("/api/v1/tools")
async def api_example():
    """Try to add descriptions for others."""
    tools = [
        {
            "name": "fastAPI",
            "url": "https://fastapi.tiangolo.com/",
            "language": "Python",
        },
        {
            "name": "Vue.js",
            "url": "https://vuejs.org/",
            "language": "JavaScript",
        },
        {
            "name": "Quasar Framework",
            "url": "https://quasar.dev/",
            "language": "JavaScript",
        },
    ]

    return tools
