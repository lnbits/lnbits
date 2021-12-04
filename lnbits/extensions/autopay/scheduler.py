from .storage import Storage
from .utils import execute_lnurl_payment
from .models import PaymentLogEntry


class Scheduler(object):
    """ Takes care of scheduling payments. """

    def __init__(self, storage: Storage, execute_payment=None):
        self._storage = storage
        self._execute_payment = execute_payment or execute_lnurl_payment

    async def run(self, now):
        """ This should be run periodically.
        Go over all scheduled payments, and if should be run at `now`, execute payment. """
        print("Autopay: Running scheduler")
        for se in await self._storage.read_schedule_entries():
            executed_count = await self._storage.read_payment_count(se.id)
            next = se.next_run(executed_count)
            print(f"Autopay: Checking schedule id={se.id} next={next} now={now}")
            if next < now:
                print(f"Autopay: Executing payment with wallet_id={se.wallet_id} {se.lnurl}")
                hash = await self._execute_payment(se.wallet_id, se.lnurl, se.amount_msat)
                await self._storage.create_payment_log(PaymentLogEntry(0, se.id, 0, hash))
