"""Check the macOS dependency guard without building an application."""

import runpy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

BUILD = Path(__file__).with_name("build.py")


class BuildReadyError(Exception):
    """Stop once dependency validation allows the build to proceed."""


class BuildTests(unittest.TestCase):
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
