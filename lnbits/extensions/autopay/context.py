from .utils import lnurl_scan
from .storage import SqliteStorage
from .scheduler import Scheduler


class AutopayContext(object):
    """ Object that holds dependencies across requests, so that we can mock these out during tests. Sort of Dependency Injection container. """

    def __init__(self, autopay_db):
        self.lnurl_scan = lnurl_scan
        self.storage = SqliteStorage(autopay_db)

    def get_scheduler(self):
        return Scheduler(self.storage)
