"""Run with python -m unittest discover -s .github/packaging -v."""

import os
import socket
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import desktop


class DesktopTests(unittest.TestCase):
    def test_gui_only_for_desktop_launch(self):
        with (
            patch("desktop.sys.platform", "linux"),
            patch("desktop.sys.argv", ["lnbits"]),
            patch.dict(os.environ, {"DISPLAY": ":97"}, clear=True),
            patch("desktop.launched_from_terminal", return_value=True),
        ):
            self.assertFalse(desktop.should_show_gui())
        with (
            patch("desktop.sys.platform", "linux"),
            patch("desktop.sys.argv", ["lnbits"]),
            patch.dict(os.environ, {"DISPLAY": ":97"}, clear=True),
            patch("desktop.launched_from_terminal", return_value=False),
        ):
            self.assertTrue(desktop.should_show_gui())
            with patch("desktop.sys.argv", ["lnbits", "--headless"]):
                self.assertFalse(desktop.should_show_gui())
            with patch.dict(os.environ, {}, clear=True):
                self.assertFalse(desktop.should_show_gui())

    def test_redirected_terminal(self):
        with (
            patch("desktop.sys.platform", "linux"),
            patch("desktop.os.O_NOCTTY", 256, create=True),
            patch("desktop.sys.stdin", None),
            patch("desktop.sys.stdout", None),
            patch("desktop.sys.stderr", None),
            patch("desktop.os.open", return_value=42),
            patch("desktop.os.close") as close,
        ):
            self.assertTrue(desktop.launched_from_terminal())
            close.assert_called_once_with(42)
        with (
            patch("desktop.sys.platform", "linux"),
            patch("desktop.os.O_NOCTTY", 256, create=True),
            patch("desktop.sys.stdin", None),
            patch("desktop.sys.stdout", None),
            patch("desktop.sys.stderr", None),
            patch("desktop.os.open", side_effect=OSError),
        ):
            self.assertFalse(desktop.launched_from_terminal())

    def test_windows_console_ownership(self):
        for processes, expected in (
            ([], False),
            ([10, 11], False),
            ([10, 11, 12], True),
        ):

            def get_processes(buffer, size, processes=processes):
                for index, pid in enumerate(processes[:size]):
                    buffer[index] = pid
                return len(processes)

            kernel32 = Mock()
            kernel32.GetConsoleProcessList.side_effect = get_processes
            with (
                patch("ctypes.WinDLL", return_value=kernel32, create=True),
                patch("desktop.sys.frozen", True, create=True),
                patch("desktop.os.getpid", return_value=11),
                patch("desktop.os.getppid", return_value=10),
            ):
                self.assertEqual(desktop.windows_terminal(), expected)

    def test_desktop_defaults_do_not_require_https(self):
        with (
            patch("desktop.sys.argv", ["lnbits"]),
            patch.dict(os.environ, {}, clear=True),
            patch("desktop.default_folder", return_value=Path("test-data")),
            patch("desktop.should_show_gui", return_value=False),
            patch("desktop.mp.freeze_support"),
            patch("desktop.configuration", return_value={}) as configure,
            patch("desktop.signal.signal"),
            patch("desktop.Server") as server,
        ):
            server.return_value.poll.return_value = 0
            with self.assertRaises(SystemExit):
                desktop.main()
            self.assertFalse(configure.call_args.args[3])

    def test_explicit_storage_base_does_not_require_home(self):
        for platform, variable, suffix in (
            ("win32", "LOCALAPPDATA", "LNbits"),
            ("linux", "XDG_DATA_HOME", "lnbits-desktop"),
        ):
            with (
                patch("desktop.sys.platform", platform),
                patch.dict(os.environ, {variable: "storage"}, clear=True),
                patch("desktop.Path.home", side_effect=RuntimeError("No home")),
            ):
                self.assertEqual(desktop.default_folder(), Path("storage") / suffix)

    def test_worker_ctrl_c_exits_cleanly(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict(os.environ, {}, clear=True),
            patch("desktop.os.chdir"),
            patch("desktop.run_server", side_effect=KeyboardInterrupt),
        ):
            desktop.worker({"LNBITS_DATA_FOLDER": folder}, Mock(), Mock())

    def test_configuration(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict(os.environ, {}, clear=True),
        ):
            values = desktop.configuration("127.0.0.1", "5123", folder, False, True)
            self.assertEqual(values["PORT"], "5123")
            self.assertEqual(values["AUTH_HTTPS_ONLY"], "false")
            self.assertEqual(values["LNBITS_ADMIN_UI"], "true")
            self.assertEqual(values["LNBITS_DATA_FOLDER"], str(Path(folder).resolve()))
            for port in ("0", "65536", "invalid"):
                with self.assertRaises(ValueError):
                    desktop.configuration("localhost", port, folder, False, True)
            with self.assertRaises(ValueError):
                desktop.configuration("http://localhost", "5000", folder, False, True)

    def test_stop_tracks_owned_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            server = desktop.Server(
                desktop.configuration("127.0.0.1", 5123, folder, False, True)
            )
            server.stop()
            first = server.stopping_at
            server.stop()
            self.assertTrue(server.stop_event.is_set())
            self.assertEqual(first, server.stopping_at)

    def test_restart_and_stop_are_distinct(self):
        server = desktop.Server({})
        server.process = Mock(exitcode=75)
        server.process.is_alive.return_value = False
        with patch.object(server, "start") as start:
            self.assertIsNone(server.poll())
            start.assert_called_once()
            start.reset_mock()
            server.stop()
            self.assertEqual(server.poll(), 75)
            start.assert_not_called()

    def test_force_stop_only_targets_owned_worker(self):
        server = desktop.Server({})
        server.process = Mock()
        server.process.is_alive.return_value = True
        with patch("desktop.time.monotonic", return_value=100):
            server.stop()
        with patch("desktop.time.monotonic", return_value=131):
            self.assertIsNone(server.poll())
        server.process.kill.assert_called_once()

    def test_window_close_stops_server(self):
        import tkinter as tk
        from tkinter import ttk

        with tempfile.TemporaryDirectory() as folder, socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            sock.close()
            root = tk.Tk()
            deadline = time.monotonic() + 90
            launched = False
            ready = False
            timed_out = False

            def interact():
                nonlocal launched, ready, timed_out
                buttons = [
                    child
                    for frame in root.winfo_children()
                    for child in frame.winfo_children()
                    if isinstance(child, ttk.Button)
                ]
                launch = next(
                    button
                    for button in buttons
                    if button.cget("text") in ("Launch LNbits", "Stop LNbits", "Close")
                )
                browser = next(
                    button
                    for button in buttons
                    if button.cget("text") == "Open in browser"
                )
                if not launched:
                    entries = [
                        child
                        for frame in root.winfo_children()
                        for child in frame.winfo_children()
                        if isinstance(child, ttk.Entry)
                    ]
                    root.setvar(
                        entries[-1].cget("textvariable"), str(Path(folder, "chosen"))
                    )
                    launch.invoke()
                    launched = True
                elif str(browser.cget("state")) == "normal":
                    ready = True
                    root.tk.call(root.protocol("WM_DELETE_WINDOW"))
                    return
                elif time.monotonic() > deadline:
                    timed_out = True
                    root.tk.call(root.protocol("WM_DELETE_WINDOW"))
                    return
                root.after(100, interact)

            environment = dict(  # noqa: C408
                HOST="127.0.0.1",
                PORT=str(port),
                LNBITS_DATA_FOLDER=folder,
                LNBITS_EXTENSIONS_PATH=folder,
                LNBITS_BACKEND_WALLET_CLASS="FakeWallet",
                LNBITS_EXTENSIONS_DEFAULT_INSTALL="[]",
                DEBUG="false",
            )
            with (
                patch.dict(os.environ, environment),
                patch("tkinter.Tk", return_value=root),
            ):
                root.after(100, interact)
                desktop.gui()
            self.assertFalse(timed_out, "Server failed to start from UI")
            self.assertTrue(ready)
            self.assertTrue(Path(folder, "chosen", "database.sqlite3").exists())
            with socket.socket() as probe:
                self.assertNotEqual(probe.connect_ex(("127.0.0.1", port)), 0)


if __name__ == "__main__":
    unittest.main()
