from quart import Blueprint
from lnbits.db import Database

from .context import AutopayContext


db = Database("ext_autopay")

autopay_ext: Blueprint = Blueprint(
    "autopay", __name__, static_folder="static", template_folder="templates"
)

context = AutopayContext(db)


import sys

if "pytest" not in sys.modules:
    # Only load these in prod, for some reason it fails under pytest
    from .views_api import *  # noqa
    from .views import *  # noqa

    # Spawn a process that periodically hits the scheduler API
    # TODO: use asyncio once lnbits updates to quart 0.16
    # See https://stackoverflow.com/questions/70075859/scheduling-periodic-function-call-in-quart-asyncio
    from lnbits.settings import HOST, PORT
    import subprocess
    scheduler_check_freq_secs = '60'
    p = subprocess.Popen(['watch', '-n', scheduler_check_freq_secs, f"curl -k -X POST https://{HOST}:{PORT}/autopay/api/v1/scheduler"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # p = subprocess.Popen(['watch', '-n', scheduler_check_freq_secs, f"curl -X POST http://{HOST}:{PORT}/autopay/api/v1/scheduler"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
