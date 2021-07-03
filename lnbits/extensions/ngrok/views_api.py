# views_api.py is for you API endpoints that could be hit by another service

# add your dependencies here

import pyngrok

# import json
# import httpx
# (use httpx just like requests, except instead of response.ok there's only the
#  response.is_error that is its inverse)

from quart import jsonify
from http import HTTPStatus

from . import freetunnel_ext
