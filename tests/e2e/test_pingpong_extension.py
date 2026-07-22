from __future__ import annotations

from uuid import uuid4

from playwright.sync_api import Page, expect

from tests.e2e.extension_helpers import (
    create_wallet,
    extension_api,
    extension_frame,
    fund_wallet_with_fake_balance,
    grant_background_payment_permission,
    install_and_enable_extension,
    login,
    pay_invoice_with_wallet,
    superuser_wallet,
    wait_for_result,
)
from tests.e2e.helpers import LNbitsE2EServer
from tests.e2e.live_extensions import LIVE_EXTENSIONS, PINGPONG
from tests.e2e.lnurl_helpers import LNURLPayServer


def test_install_pingpong_and_pay_entry_invoice_with_fake_wallet(
    page: Page,
    lnbits_e2e_server: LNbitsE2EServer,
) -> None:
    login(page, lnbits_e2e_server)
    escrow = superuser_wallet(page)
    payer = create_wallet(page, f"PingPong payer {uuid4().hex[:8]}")
    payout_target = create_wallet(page, f"PingPong payout {uuid4().hex[:8]}")
    fund_wallet_with_fake_balance(page, payer.id, amount_sats=100)

    install_and_enable_extension(page, PINGPONG, preload_extensions=LIVE_EXTENSIONS)
    grant_background_payment_permission(
        page,
        PINGPONG.ext_id,
        escrow.id,
        max_amount_sats=100,
    )

    page.goto("/ext/pingpong")
    frame = extension_frame(page, "Ping Pong")
    expect(frame.get_by_text("Lightning Pong tables")).to_be_visible(timeout=60_000)

    table_name = f"Playwright Pong {uuid4().hex[:8]}"
    table = extension_api(
        page,
        PINGPONG.ext_id,
        "POST",
        "/tables",
        {
            "name": table_name,
            "description": "Playwright fake wallet table",
            "walletId": escrow.id,
            "entrySats": 3,
            "gamesToWin": 1,
            "hostPercent": 0,
        },
    )
    assert table["name"] == table_name

    with LNURLPayServer(lnbits_e2e_server.base_url, payout_target) as lnurl_server:
        game = extension_api(
            page,
            PINGPONG.ext_id,
            "POST",
            f"/tables/{table['id']}/games",
            {"lnurl": lnurl_server.lnurl},
        )
        payment_request = game["invoice"]["paymentRequest"]
        assert payment_request.lower().startswith("lnbc")

        pay_invoice_with_wallet(page, payer, payment_request)
        paid_game = wait_for_result(
            "Ping Pong player 1 payment to be recorded",
            lambda: _pingpong_game_if_player1_paid(
                page, str(game["gameId"]), str(game["playerToken"])
            ),
            timeout=30,
        )

    assert paid_game["status"] == "waiting_opponent", paid_game
    assert paid_game["player1Paid"] is True, paid_game

    page.goto("/ext/pingpong")
    frame = extension_frame(page, "Ping Pong")
    expect(frame.get_by_text(table_name)).to_be_visible(timeout=60_000)


def _pingpong_game_if_player1_paid(
    page: Page, game_id: str, player_token: str
) -> dict | None:
    game = extension_api(
        page,
        PINGPONG.ext_id,
        "GET",
        f"/games/{game_id}/public?playerToken={player_token}",
    )
    return game if game.get("player1Paid") is True else None
