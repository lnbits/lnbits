#views_api.py is for you API endpoints that could be hit by another service

#add your dependencies here

import json
import requests
from flask import jsonify, render_template, request, redirect, url_for
from lnbits.db import open_db, open_ext_db
from lnbits.extensions.example import example_ext

#add your endpoints here

@example_ext.route("/api/v1/example", methods=["GET","POST"])
def api_example():
    """Try to add descriptions for others."""
    #YOUR-CODE
    
    return jsonify({"status": "TRUE"}), 200
