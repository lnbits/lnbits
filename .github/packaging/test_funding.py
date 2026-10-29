"""Funding lifecycle tests use isolated data and never create real payments."""

import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import desktop
import funding
from embit.bip39 import mnemonic_is_valid


class FundingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        resources = self.folder / "bundled"
        (resources / "spark").mkdir(parents=True)
        for filename in (
            "node",
            "node.exe",
            "phoenixd",
            "supervisor.mjs",
            "spark/server.mjs",
        ):
            (resources / filename).touch()
        self.enterContext(patch("funding.bundled_path", return_value=resources))
        self.enterContext(patch("funding.check_port"))
        self.enterContext(patch.dict(os.environ, {}, clear=True))
        self.process = Mock()
        self.process.poll.return_value = None
        self.process.stdin.close.side_effect = lambda: setattr(
            self.process.poll, "return_value", 0
        )
        self.popen = self.enterContext(
            patch("funding.subprocess.Popen", return_value=self.process)
        )
        self.enterContext(patch("funding.threading.Thread"))

    def start(self, provider="spark", port=8765):
        environment = desktop.configuration(
            "127.0.0.1",
            5000,
            str(self.folder / "data"),
            False,
            True,
            provider,
            port,
            True,
        )
        daemon = funding.Funding(environment)
        self.addCleanup(daemon.close)
        daemon.start()
        return daemon

    def test_identity_survives_restart_and_port_change(self):
        for provider, words in (("spark", 24), ("phoenixd", 12)):
            if provider == "phoenixd" and sys.platform == "win32":
                continue
            with self.subTest(provider=provider):
                # Each backing wallet owns a separate LNbits data folder.
                self.folder = self.folder / provider
                self.folder.mkdir()
                self.process.poll.return_value = None
                daemon = self.start(provider)
                seed = daemon.folder / provider / "seed.dat"
                mnemonic = seed.read_text().strip()
                self.assertTrue(mnemonic_is_valid(mnemonic))
                self.assertEqual(len(mnemonic.split()), words)
                old_key = (
                    daemon.environment.get("SPARK_L2_EXTERNAL_API_KEY")
                    or daemon.environment["PHOENIXD_API_PASSWORD"]
                )
                daemon.close()
                self.process.poll.return_value = None
                restarted = self.start(provider, 9876)
                self.assertEqual(seed.read_text().strip(), mnemonic)
                self.assertEqual(funding.load_profile(seed.parents[2])["port"], 9876)
                key = (
                    restarted.environment.get("SPARK_L2_EXTERNAL_API_KEY")
                    or restarted.environment["PHOENIXD_API_PASSWORD"]
                )
                self.assertNotEqual(key, old_key)
                self.assertNotIn(mnemonic, " ".join(self.popen.call_args.args[0]))
                if os.name != "nt":
                    self.assertEqual(seed.stat().st_mode & 0o777, 0o600)
                restarted.close()

    def test_missing_or_invalid_seed_is_never_replaced(self):
        daemon = self.start()
        seed = daemon.folder / "spark/seed.dat"
        daemon.close()
        seed.unlink()
        with self.assertRaisesRegex(ValueError, "seed is missing"):
            self.start()
        self.assertFalse(seed.exists())
        seed.write_text("damaged")
        with self.assertRaisesRegex(ValueError, "seed is invalid"):
            self.start()
        self.assertEqual(seed.read_text(), "damaged")

    def test_existing_balance_cannot_be_assigned_a_new_backing_wallet(self):
        data = self.folder / "data"
        data.mkdir()
        (data / "database.sqlite3").touch()
        with self.assertRaisesRegex(ValueError, "new data folder"):
            self.start()
        self.popen.assert_not_called()

    def test_one_owner_per_wallet(self):
        daemon = self.start()
        with self.assertRaises(OSError):
            self.start()
        daemon.close()
        self.start().close()

    def test_provider_change_and_corrupt_profile_are_rejected(self):
        daemon = self.start()
        daemon.close()
        profile = daemon.folder / "profile.json"
        data = json.loads(profile.read_text())
        data["provider"] = "phoenixd"
        profile.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "separate data folder"):
            self.start()
        profile.write_text("[]")
        with self.assertRaisesRegex(ValueError, "profile is invalid"):
            self.start()

    def test_local_only_authenticated_configuration(self):
        daemon = self.start()
        env = self.popen.call_args.kwargs["env"]
        self.assertEqual(env["SPARK_SIDECAR_HOST"], "127.0.0.1")
        self.assertEqual(
            env["SPARK_SIDECAR_API_KEY"],
            daemon.environment["SPARK_L2_EXTERNAL_API_KEY"],
        )
        self.assertEqual(env["SPARK_MNEMONIC"], daemon.environment["SPARK_L2_MNEMONIC"])
        self.assertEqual(env["SPARK_ONCHAIN_ENABLED"], "false")

    def test_ports_cannot_conflict(self):
        with self.assertRaisesRegex(ValueError, "different, valid port"):
            desktop.configuration(
                "127.0.0.1", 5000, str(self.folder), False, True, "spark", 5000
            )

    def test_saved_settings_cannot_override_managed_connection(self):
        from lnbits.core.services.settings import update_cached_settings
        from lnbits.settings import readonly_variables, settings

        original = readonly_variables.copy()
        self.addCleanup(lambda: readonly_variables.__setitem__(slice(None), original))
        env = {
            "LNBITS_DESKTOP_FUNDING": "spark",
            "LNBITS_BACKEND_WALLET_CLASS": "SparkL2Wallet",
            "SPARK_L2_EXTERNAL_ENDPOINT": "http://127.0.0.1:8765",
        }
        with (
            patch.object(settings, "lnbits_backend_wallet_class", "VoidWallet"),
            patch.object(settings, "spark_l2_external_endpoint", ""),
            patch.object(settings, "lnbits_database_url", None),
        ):
            funding.protect_settings(env)
            update_cached_settings(
                {
                    "lnbits_backend_wallet_class": "VoidWallet",
                    "spark_l2_external_endpoint": "http://old.invalid",
                }
            )
            self.assertEqual(settings.lnbits_backend_wallet_class, "SparkL2Wallet")
            self.assertEqual(
                settings.spark_l2_external_endpoint, env["SPARK_L2_EXTERNAL_ENDPOINT"]
            )

    def test_readiness_requires_wallet_balance(self):
        daemon = self.start()
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.side_effect = [
            '{"status":"missing_mnemonic"}',
            '{"balance_sats":"0"}',
        ]
        client = Mock()
        client.open.return_value = response
        # _wait_ready normally runs in its background thread.
        with patch("funding.urllib.request.build_opener", return_value=client):
            daemon._wait_ready(Mock())
        self.assertTrue(daemon.ready.is_set())
        self.assertEqual(client.open.call_count, 2)

    def test_server_waits_for_daemon_and_stops_if_it_dies(self):
        env = desktop.configuration(
            "127.0.0.1", 5000, str(self.folder), False, True, "spark"
        )
        server = desktop.Server(env)
        self.addCleanup(server.stop)
        daemon = Mock(error=None)
        daemon.ready = threading.Event()
        daemon.poll.return_value = None
        with (
            patch("desktop.Funding", return_value=daemon),
            patch("desktop.socket.create_server"),
            patch.object(server, "_start_worker") as start_worker,
        ):
            server.start()
            self.assertIsNone(server.poll())
            start_worker.assert_not_called()
            daemon.ready.set()
            server.poll()
            start_worker.assert_called_once()
            daemon.poll.return_value = 1
            self.assertEqual(server.poll(), 1)
            self.assertTrue(server.stop_event.is_set())
            daemon.stop.assert_called_once()
            daemon.close.assert_called_once()

    def test_daemon_survives_lnbits_restart(self):
        server = desktop.Server(
            {"HOST": "127.0.0.1", "PORT": "5000", "LNBITS_DESKTOP_FUNDING": "spark"}
        )
        daemon = Mock(error=None)
        daemon.poll.return_value = None
        daemon.ready.is_set.return_value = True
        server.funding = daemon
        server.process = Mock(exitcode=75)
        server.process.is_alive.return_value = False
        with (
            patch("desktop.socket.create_server"),
            patch.object(server, "_start_worker") as start_worker,
        ):
            self.assertIsNone(server.poll())
            start_worker.assert_called_once()
            daemon.stop.assert_not_called()
            daemon.start.assert_not_called()
