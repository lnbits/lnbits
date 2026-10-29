"""Check the macOS dependency guard without building an application."""

import runpy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

BUILD = Path(__file__).with_name("build.py")


class BuildReadyError(Exception):
    """Stop once dependency validation allows the build to proceed."""


class BuildTests(unittest.TestCase):
    def test_only_macos_uses_the_native_embit_hook(self):
        for system in ("darwin", "linux", "win32"):
            with self.subTest(system=system), tempfile.TemporaryDirectory() as folder:
                bindepend = Mock()
                bindepend.get_imports.return_value = []
                with (
                    patch.dict(
                        "sys.modules",
                        {
                            "wasmtime": SimpleNamespace(
                                __file__=str(Path(folder) / "__init__.py")
                            ),
                            "PyInstaller": Mock(),
                            "PyInstaller.depend": Mock(),
                            "PyInstaller.depend.bindepend": bindepend,
                        },
                    ),
                    patch("prepare_sidecars.main") as prepare,
                    patch(
                        "pathlib.Path.iterdir",
                        return_value=iter([Path(folder) / "node"]),
                    ),
                    patch("sys.platform", system),
                    patch.dict("os.environ"),
                    patch(
                        "importlib.util.find_spec",
                        return_value=SimpleNamespace(origin="native.so"),
                    ),
                    patch("subprocess.run") as run,
                ):
                    runpy.run_path(str(BUILD))
                command = run.call_args.args[0]
                prepare.assert_called_once_with()
                self.assertIn(f"{Path(folder) / 'node'}:sidecars", command)
                collections = [
                    command[i + 1]
                    for i, item in enumerate(command)
                    if item == "--collect-all"
                ]
                self.assertEqual("embit" in collections, system != "darwin")
                self.assertEqual(
                    "--additional-hooks-dir" in command, system == "darwin"
                )
                self.assertIn("--hidden-import=embit", command)

    def check_bindings(self, imports, error):
        bindepend = Mock()
        bindepend.get_imports.return_value = imports
        with (
            patch("prepare_sidecars.main", side_effect=BuildReadyError) as prepare,
            patch.dict(
                "sys.modules",
                {
                    "wasmtime": Mock(),
                    "PyInstaller": Mock(),
                    "PyInstaller.depend": Mock(),
                    "PyInstaller.depend.bindepend": bindepend,
                },
            ),
            patch("sys.platform", "darwin"),
            patch.dict("os.environ"),
            patch(
                "importlib.util.find_spec",
                return_value=SimpleNamespace(origin="/env/_rust.abi3.so"),
            ),
        ):
            with self.assertRaises(error):
                runpy.run_path(str(BUILD))
            bindepend.get_imports.assert_called_once_with("/env/_rust.abi3.so")
            if error is BuildReadyError:
                prepare.assert_called_once_with()
            else:
                prepare.assert_not_called()

    def test_shared_openssl_is_rejected_before_preparing_sidecars(self):
        for library in (
            "@rpath/libssl.3.dylib",
            "/opt/homebrew/opt/openssl@3/lib/libcrypto.3.dylib",
        ):
            with self.subTest(library=library):
                self.check_bindings({(library, None)}, RuntimeError)

    def test_static_openssl_allows_build(self):
        self.check_bindings(
            {("/usr/lib/libSystem.B.dylib", "/usr/lib/libSystem.B.dylib")},
            BuildReadyError,
        )


class EmbitHookTests(unittest.TestCase):
    def collect(self, arch, entries):
        hooks = SimpleNamespace(collect_all=Mock(return_value=entries))
        with (
            patch.dict(
                "sys.modules",
                {
                    "PyInstaller": Mock(),
                    "PyInstaller.utils": Mock(),
                    "PyInstaller.utils.hooks": hooks,
                },
            ),
            patch("platform.machine", return_value=arch),
        ):
            return runpy.run_path(str(BUILD.parent / "macos/hooks/hook-embit.py"))

    def test_only_native_library_is_collected_as_code_on_each_mac(self):
        libraries = [
            (f"/env/embit/util/prebuilt/libsecp256k1_{suffix}", "embit/util/prebuilt")
            for suffix in (
                "darwin_arm64.dylib",
                "darwin_x86_64.dylib",
                "linux_x86_64.so",
                "windows_amd64.dll",
            )
        ]
        source = ("/env/embit/util/ctypes_secp256k1.py", "embit/util")
        for arch in ("arm64", "x86_64"):
            for as_data in (True, False):
                with self.subTest(arch=arch, as_data=as_data):
                    entries = (
                        ([source, *libraries], [], ["embit.util.ctypes_secp256k1"])
                        if as_data
                        else ([source], libraries, ["embit.util.ctypes_secp256k1"])
                    )
                    hook = self.collect(arch, entries)
                    self.assertEqual(hook["datas"], [source])
                    self.assertEqual(
                        hook["binaries"],
                        [
                            (
                                f"/env/embit/util/prebuilt/libsecp256k1_darwin_{arch}.dylib",
                                "embit/util/prebuilt",
                            )
                        ],
                    )
                    self.assertEqual(hook["hiddenimports"], entries[2])

    def test_missing_native_library_fails_packaging(self):
        with self.assertRaisesRegex(RuntimeError, "Missing native embit prebuild"):
            self.collect(
                "arm64",
                ([], [("libsecp256k1_darwin_x86_64.dylib", "embit/util/prebuilt")], []),
            )
