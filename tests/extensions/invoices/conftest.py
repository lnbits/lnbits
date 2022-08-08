import pytest
import pytest_asyncio

from lnbits.core.crud import create_account, create_wallet
from lnbits.extensions.invoices.models import CreateInvoiceData


@pytest_asyncio.fixture
async def invoices_wallet():
    user = await create_account()
    wallet = await create_wallet(user_id=user.id, wallet_name="invoices_test")
    
    return wallet
    
