"""Check DMG staging without requiring macOS command-line tools."""

import contextlib
import hashlib
import plistlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from macos import dmg


class DmgTests(unittest.TestCase):
    def test_staging_preserves_app_and_verifies_before_publishing_checksum(self):
        for fail_verification in (False, True):
            with (
                self.subTest(fail_verification=fail_verification),
                tempfile.TemporaryDirectory() as folder,
                contextlib.chdir(folder),
                patch("macos.dmg.sys.platform", "darwin"),
                patch("macos.dmg.platform.machine", return_value="arm64"),
                patch.dict("os.environ", {}, clear=True),
            ):
                Path("pyproject.toml").write_text('[project]\nversion="1.6.2-rc1"\n')
                original = Path("dist/LNbits.app/Contents")
                original.mkdir(parents=True)
                metadata = {"CFBundleIdentifier": "com.lnbits.desktop"}
                (original / "Info.plist").write_bytes(plistlib.dumps(metadata))
                (original / "Resources").mkdir()
                (original / "Frameworks").symlink_to("Resources")
                output = Path("dist/LNbits-v1.6.2rc1-macOS-arm64.dmg").resolve()

                def run(*args, output=output, fail_verification=fail_verification):
                    if args[:2] == ("/usr/bin/hdiutil", "create"):
                        staging = Path(args[args.index("-srcfolder") + 1])
                        app = staging / "LNbits.app/Contents"
                        info = plistlib.loads((app / "Info.plist").read_bytes())
                        self.assertEqual(info["CFBundleShortVersionString"], "1.6.2")
                        self.assertEqual(info["LSMinimumSystemVersion"], "15.0")
                        self.assertTrue((app / "Frameworks").is_symlink())
                        self.assertEqual(
                            (staging / "Applications").readlink(), Path("/Applications")
                        )
                        output.write_bytes(b"disk image")
                    if fail_verification and args[:2] == ("/usr/bin/hdiutil", "verify"):
                        raise subprocess.CalledProcessError(1, args)

                with patch("macos.dmg.run", side_effect=run) as commands:
                    if fail_verification:
                        with self.assertRaises(subprocess.CalledProcessError):
                            dmg.main()
                        self.assertFalse(output.with_suffix(".dmg.sha256").exists())
                    else:
                        dmg.main()
                        checksum = output.with_suffix(".dmg.sha256").read_text()
                        digest = hashlib.sha256(b"disk image").hexdigest()
                        self.assertEqual(
                            checksum,
                            f"{digest}  {output.name}\n",
                        )
                    commands.assert_any_call("/usr/bin/hdiutil", "verify", str(output))
                self.assertEqual(
                    plistlib.loads((original / "Info.plist").read_bytes()), metadata
                )
