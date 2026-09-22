"""Check DMG staging without requiring macOS command-line tools."""

import contextlib
import hashlib
import plistlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from macos import dmg, release
from macos.common import ReleaseError


class DmgTests(unittest.TestCase):
    def test_staging_preserves_app_and_verifies_before_publishing_checksum(self):
        for fail_verification in (False, True):
            with (
                self.subTest(fail_verification=fail_verification),
                tempfile.TemporaryDirectory() as folder,
                contextlib.chdir(folder),
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
                self.assertEqual(dmg.output_path(), output)
                signed_metadata = []

                def sign(*args, original=original, signed_metadata=signed_metadata):
                    signed_metadata.append((original / "Info.plist").read_bytes())

                def run(
                    operation,
                    *args,
                    output=output,
                    signed_metadata=signed_metadata,
                    **kwargs,
                ):
                    if args[0] == "/usr/bin/ditto":
                        shutil.copytree(args[-2], args[-1], symlinks=True)
                    if args[:2] == ("/usr/bin/hdiutil", "create"):
                        staging = Path(args[args.index("-srcfolder") + 1])
                        app = staging / "LNbits.app/Contents"
                        info = plistlib.loads((app / "Info.plist").read_bytes())
                        self.assertEqual(
                            (app / "Info.plist").read_bytes(), signed_metadata[0]
                        )
                        self.assertEqual(info["CFBundleShortVersionString"], "1.6.2")
                        self.assertEqual(info["LSMinimumSystemVersion"], "15.0")
                        self.assertEqual(
                            info["CFBundleIdentifier"], "com.lnbits.desktop"
                        )
                        self.assertTrue((app / "Frameworks").is_symlink())
                        self.assertEqual(
                            (staging / "Applications").readlink(), Path("/Applications")
                        )
                        Path(args[-1]).write_bytes(b"uncompressed image")
                    if args[:2] == ("/usr/bin/hdiutil", "convert"):
                        output.write_bytes(b"final disk image")

                def verify(*args, output=output, fail_verification=fail_verification):
                    self.assertFalse(output.with_suffix(".dmg.sha256").exists())
                    if fail_verification:
                        raise ReleaseError("Verify final DMG: rejected")

                runner = Mock()
                runner.run.side_effect = run
                session = Mock()
                with (
                    patch("macos.release.bundled_data"),
                    patch("macos.release.sign_app", side_effect=sign),
                    patch("macos.release.verify_image", side_effect=verify) as verified,
                ):
                    if fail_verification:
                        with self.assertRaisesRegex(ReleaseError, "Verify final DMG"):
                            release.release(
                                runner,
                                session,
                                signed=False,
                                credentials={},
                                arch="arm64",
                                skip_build=True,
                            )
                        self.assertFalse(output.exists())
                        self.assertFalse(output.with_suffix(".dmg.sha256").exists())
                    else:
                        release.release(
                            runner,
                            session,
                            signed=False,
                            credentials={},
                            arch="arm64",
                            skip_build=True,
                        )
                        checksum = output.with_suffix(".dmg.sha256").read_text()
                        digest = hashlib.sha256(b"final disk image").hexdigest()
                        self.assertEqual(
                            checksum,
                            f"{digest}  {output.name}\n",
                        )
                    verified.assert_called_once_with(
                        runner, session, output, "arm64", None
                    )
                session.cleanup.assert_called_once_with()
                session.setup.assert_not_called()
                self.assertEqual(
                    (original / "Info.plist").read_bytes(), signed_metadata[0]
                )
