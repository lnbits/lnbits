from lnbits.core.services import fee_reserve, get_wallet


async def check_balance(wallet, amount) -> bool:
    # check if we can pay the invoice before we try and execute on the scheduled payment
    amount_msat = amount * 1000
    fee_reserve_msat = fee_reserve(amount_msat)
    wallet = await get_wallet(wallet)
    assert wallet
    if wallet.balance_msat - fee_reserve_msat < amount_msat:
        return False
    return True
