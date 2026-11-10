"""Desktop funding persistence uses temporary SQLite and deterministic test seeds."""

import traceback
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import desktop
import funding
from embit.bip39 import mnemonic_from_bytes


class FundingSettingsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from lnbits.core.crud import settings as crud
        from lnbits.db import Database
        from lnbits.settings import settings

        self.crud = crud
        self.settings = settings
        temporary = self.enterContext(TemporaryDirectory())
        self.folder = Path(temporary)
        self.enterContext(patch.object(settings, "lnbits_data_folder", temporary))
        self.enterContext(patch.object(settings, "lnbits_database_url", None))
        self.enterContext(patch.object(settings, "lnbits_admin_ui", True))
        for field in (
            "spark_l2_mnemonic_backup_confirmed",
            "phoenixd_mnemonic_backup_confirmed",
        ):
            self.enterContext(patch.object(settings, field, True))
        self.database = Database("funding-sync-test")
        self.enterContext(patch.object(crud, "db", self.database))
        await self.database.execute(
            "CREATE TABLE system_settings "
            "(id TEXT, value TEXT, tag TEXT, UNIQUE(id, tag))"
        )
        await crud.set_settings_field("super_user", "test-superuser")
        await crud.set_settings_field("lnbits_site_title", "Preserved title")
        self.seeds = {}
        for provider, size in (("spark", 32), ("phoenixd", 16)):
            seed = mnemonic_from_bytes(bytes(range(size)))
            path = self.folder / "funding" / provider / "seed.dat"
            path.parent.mkdir(parents=True)
            path.write_text(seed + "\n")
            self.seeds[provider] = seed
        # Synchronizing must never invoke the launcher's seed generation/writer.
        self.enterContext(
            patch("funding.secrets.token_bytes", side_effect=AssertionError)
        )
        self.enterContext(patch("funding.save_private", side_effect=AssertionError))

    async def asyncTearDown(self):
        await self.database.engine.dispose()

    def environment(self, provider):
        values = {
            "LNBITS_DESKTOP_FUNDING": provider,
            "LNBITS_DATA_FOLDER": str(self.folder),
            "LNBITS_BACKEND_WALLET_CLASS": funding.PROVIDERS[provider],
            "LNBITS_SITE_TITLE": "Must not overwrite unrelated settings",
        }
        if provider == "spark":
            values.update(
                SPARK_L2_EXTERNAL_ENDPOINT="http://127.0.0.1:8765",
                SPARK_L2_EXTERNAL_API_KEY="synthetic-spark-key",
                SPARK_L2_MNEMONIC=self.seeds[provider],
                SPARK_L2_NETWORK="MAINNET",
                PHOENIXD_MNEMONIC="must-not-touch-inactive-provider",
            )
        else:
            values.update(
                PHOENIXD_API_ENDPOINT="http://127.0.0.1:9740",
                PHOENIXD_API_PASSWORD="synthetic-phoenix-password",
                PHOENIXD_DATA_DIR=str(self.folder / "funding/phoenixd"),
                PHOENIXD_MNEMONIC=self.seeds[provider],
                SPARK_L2_MNEMONIC="must-not-touch-inactive-provider",
            )
        return values

    async def test_switching_and_restarting_preserve_both_wallets(self):
        confirmed = set()
        for provider in ("spark", "spark", "phoenixd", "phoenixd", "spark", "phoenixd"):
            with self.subTest(provider=provider, confirmed=sorted(confirmed)):
                before = await self.crud.get_settings_by_tag("core")
                prefix = "spark_l2_" if provider == "spark" else "phoenixd_"
                inactive = "phoenixd_" if provider == "spark" else "spark_l2_"
                env = self.environment(provider)
                # Connection credentials may change on every launch.
                key = (
                    "SPARK_L2_EXTERNAL_API_KEY"
                    if provider == "spark"
                    else "PHOENIXD_API_PASSWORD"
                )
                env[key] += str(len(confirmed))
                await funding.sync_settings(env)
                view = await self.crud.get_admin_settings(True)
                self.assertEqual(
                    view.lnbits_backend_wallet_class, funding.PROVIDERS[provider]
                )
                self.assertEqual(
                    getattr(view, prefix + "mnemonic"), self.seeds[provider]
                )
                self.assertEqual(getattr(view, key.lower()), env[key])
                self.assertEqual(
                    getattr(view, prefix + "mnemonic_backup_confirmed"),
                    provider in confirmed,
                )
                after = await self.crud.get_settings_by_tag("core")
                self.assertEqual(
                    {k: v for k, v in before.items() if k.startswith(inactive)},
                    {k: v for k, v in after.items() if k.startswith(inactive)},
                )
                self.assertEqual(after["lnbits_site_title"], "Preserved title")
                for name, seed in self.seeds.items():
                    self.assertEqual(
                        (self.folder / "funding" / name / "seed.dat").read_text(),
                        seed + "\n",
                    )
                await self.crud.set_settings_field(
                    prefix + "mnemonic_backup_confirmed", True
                )
                confirmed.add(provider)

    async def test_different_saved_seed_requires_backup_again(self):
        for provider, prefix in (("spark", "spark_l2"), ("phoenixd", "phoenixd")):
            with self.subTest(provider=provider):
                await self.crud.set_settings_field(
                    prefix + "_mnemonic", "synthetic-old-seed"
                )
                await self.crud.set_settings_field(
                    prefix + "_mnemonic_backup_confirmed", True
                )
                await funding.sync_settings(self.environment(provider))
                view = await self.crud.get_admin_settings(True)
                self.assertFalse(getattr(view, prefix + "_mnemonic_backup_confirmed"))
                self.assertFalse(
                    getattr(self.settings, prefix + "_mnemonic_backup_confirmed")
                )
                self.assertEqual(
                    getattr(view, prefix + "_mnemonic"), self.seeds[provider]
                )

    async def test_missing_invalid_or_mismatched_seed_stops_without_writes(self):
        path = self.folder / "funding/spark/seed.dat"
        for contents in (None, "invalid", self.seeds["phoenixd"]):
            with self.subTest(contents=contents):
                if contents is None:
                    path.unlink()
                else:
                    path.write_text(contents)
                before = await self.crud.get_settings_by_tag("core")
                with self.assertRaises(ValueError):
                    await funding.sync_settings(self.environment("spark"))
                self.assertEqual(await self.crud.get_settings_by_tag("core"), before)
                if contents is None:
                    self.assertFalse(path.exists())
                else:
                    self.assertEqual(path.read_text(), contents)

    async def test_database_failure_is_sanitized_and_does_not_select_new_backend(self):
        await self.crud.set_settings_field(
            "lnbits_backend_wallet_class", "PhoenixdWallet"
        )
        await self.crud.set_settings_field("spark_l2_mnemonic", "old-seed")
        await self.crud.set_settings_field("spark_l2_mnemonic_backup_confirmed", True)
        original = self.crud.set_settings_field

        async def fail_seed(field, value, *args):
            if field == "spark_l2_mnemonic":
                raise RuntimeError("database parameters: synthetic-sensitive-value")
            return await original(field, value, *args)

        with patch.object(self.crud, "set_settings_field", side_effect=fail_seed):
            try:
                await funding.sync_settings(self.environment("spark"))
            except RuntimeError as exc:
                self.assertIn("Startup stopped", str(exc))
                self.assertNotIn("synthetic-sensitive-value", traceback.format_exc())
            else:
                self.fail("A failed settings write must stop startup")
        saved = await self.crud.get_settings_by_tag("core")
        self.assertEqual(saved["lnbits_backend_wallet_class"], "PhoenixdWallet")
        self.assertEqual(saved["spark_l2_mnemonic"], "old-seed")
        self.assertFalse(saved["spark_l2_mnemonic_backup_confirmed"])
        # Retrying a partial save completes using the same seed file.
        await funding.sync_settings(self.environment("spark"))
        saved = await self.crud.get_settings_by_tag("core")
        self.assertEqual(saved["spark_l2_mnemonic"], self.seeds["spark"])
        self.assertEqual(saved["lnbits_backend_wallet_class"], "SparkL2Wallet")

    async def test_unmanaged_and_admin_ui_disabled_do_not_write_settings(self):
        before = await self.crud.get_settings_by_tag("core")
        with patch.object(
            self.crud, "set_settings_field", new_callable=AsyncMock
        ) as write:
            for env in ({}, {"LNBITS_DESKTOP_FUNDING": "none"}):
                await funding.sync_settings(env)
            with patch.object(self.settings, "lnbits_admin_ui", False):
                await funding.sync_settings(self.environment("spark"))
            write.assert_not_awaited()
        self.assertEqual(await self.crud.get_settings_by_tag("core"), before)


class FundingLifespanTests(unittest.IsolatedAsyncioTestCase):
    async def test_sync_happens_after_core_startup_and_before_serving(self):
        for fail in (False, True):
            with self.subTest(fail=fail):
                events = []

                @asynccontextmanager
                async def original(app, events=events):
                    events.append("core-startup")
                    yield {"state": "preserved"}
                    # Match core's existing normal-exit shutdown semantics.
                    events.append("core-shutdown")

                async def sync(env, events=events, fail=fail):
                    self.assertEqual(events, ["core-startup"])
                    events.append("sync")
                    if fail:
                        raise RuntimeError("Cannot save bundled funding settings")

                app = SimpleNamespace(router=SimpleNamespace(lifespan_context=original))
                with patch("funding.sync_settings", side_effect=sync):
                    funding.configure_app(app, {"LNBITS_DESKTOP_FUNDING": "spark"})
                    try:
                        async with app.router.lifespan_context(app) as state:
                            self.assertEqual(state, {"state": "preserved"})
                            events.append("serving")
                    except RuntimeError:
                        self.assertTrue(fail)
                expected = ["core-startup", "sync"]
                if not fail:
                    expected.append("serving")
                self.assertEqual(events, [*expected, "core-shutdown"])

    async def test_unmanaged_lifespan_is_untouched(self):
        original = Mock()
        app = SimpleNamespace(router=SimpleNamespace(lifespan_context=original))
        for env in ({}, {"LNBITS_DESKTOP_FUNDING": "none"}):
            funding.configure_app(app, env)
            self.assertIs(app.router.lifespan_context, original)

    async def test_desktop_factory_wraps_only_its_own_app(self):
        from lnbits import app as core_app

        instance = Mock()
        environment = {"LNBITS_DESKTOP_FUNDING": "spark"}
        with (
            patch.object(core_app, "create_app", return_value=instance) as create,
            patch("desktop.configure_app") as configure,
        ):
            self.assertIs(desktop.create_desktop_app(environment), instance)
            create.assert_called_once_with()
            configure.assert_called_once_with(instance, environment)
