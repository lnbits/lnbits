from lnbits.core.models import CoreAppExtra
from lnbits.db import Database

db = Database("database")
core_app_extra: CoreAppExtra = CoreAppExtra()
