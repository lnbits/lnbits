from lnbits.core.models import CoreAppExtra
from lnbits.db import Database

db = Database("database", use_lock=False)
core_app_extra: CoreAppExtra = CoreAppExtra()
