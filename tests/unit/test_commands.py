import asyncio
from unittest.mock import AsyncMock

from click.testing import CliRunner
from pytest_mock.plugin import MockerFixture

from lnbits.commands import lnbits_cli


def test_database_migrate_without_existing_loop(mocker: MockerFixture):
    asyncio.set_event_loop(None)
    migrate = mocker.patch("lnbits.commands.migrate_databases", new_callable=AsyncMock)

    result = CliRunner().invoke(lnbits_cli, ["db", "migrate"])

    assert result.exit_code == 0, result.exception
    migrate.assert_awaited_once_with()
