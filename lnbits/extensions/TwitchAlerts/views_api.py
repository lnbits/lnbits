# views_api.py is for you API endpoints that could be hit by another service

# add your dependencies here

# import json
# import httpx
# (use httpx just like requests, except instead of response.ok there's only the
#  response.is_error that is its inverse)

from quart import jsonify
from http import HTTPStatus

from . import TwitchAlerts_ext


# add your endpoints here


@TwitchAlerts_ext.route("/api/v1/tools", methods=["GET"])
async def api_TwitchAlerts():
    """Try to add descriptions for others."""
    tools = [
        {
            "name": "Quart",
            "url": "https://pgjones.gitlab.io/quart/",
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

    return jsonify(tools), HTTPStatus.OK
