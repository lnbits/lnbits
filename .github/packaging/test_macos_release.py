"""Release gates use dummy credentials and mocked tools; never contact Apple."""

import base64
import contextlib
import hashlib
import io
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from macos import credentials, dmg, release, signing, verify
from macos.common import CREDENTIAL_NAMES, ReleaseError, Runner, validate_credentials

DUMMY = {
    "BUILD_CERTIFICATE_BASE64": base64.b64encode(b"dummy certificate").decode(),
    "P12_PASSWORD": "dummy-p12-secret",
    "KEYCHAIN_PASSWORD": "dummy-keychain-secret",
    "APPLE_ID": "dummy@example.invalid",
    "APPLE_TEAM_ID": "ABCDEFGHIJ",
    "APPLE_APP_SPECIFIC_PASSWORD": "dummy-apple-secret",
}
IDENTITY = "A" * 40
CREATE_DMG = dmg.create
SUBMISSION = "12345678-1234-1234-1234-123456789abc"


def result(stdout="", stderr="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


class PythonPrerequisiteTests(unittest.TestCase):
    def test_missing_tk_fails_before_dependency_installation_with_repair_command(self):
        runner = Mock()
        runner.run.return_value = result(
            stderr="ModuleNotFoundError: No module named '_tkinter'", returncode=1
        )
        with self.assertRaisesRegex(ReleaseError, "brew install python-tk@3.12"):
            release.prepare(runner)
        self.assertEqual(runner.run.call_count, 1)

    def test_dependency_environment_uses_the_checked_python_and_checks_tk_again(self):
        runner = Mock()
        runner.run.return_value = result("/opt/homebrew/opt/openssl@3")
        with patch("macos.release.sys.executable", "/path/to/python3.12"):
            release.prepare(runner)
        calls = runner.run.call_args_list
        self.assertEqual(calls[0].args[:2], ("Check Python/Tk", "/path/to/python3.12"))
        sync = next(
            call
            for call in calls
            if call.args[0] == "Install locked Python dependencies"
        )
        self.assertEqual(
            sync.args[sync.args.index("--python") + 1], "/path/to/python3.12"
        )
        checks = [call for call in calls if call.args[0] == "Check Python/Tk"]
        self.assertEqual(checks[1].args[1:5], ("uv", "run", "--no-sync", "python"))


class CredentialTests(unittest.TestCase):
    def test_each_credential_is_required_and_certificate_is_base64(self):
        self.assertEqual(validate_credentials(DUMMY), b"dummy certificate")
        for name in CREDENTIAL_NAMES:
            with self.subTest(name=name), self.assertRaisesRegex(ReleaseError, name):
                validate_credentials(dict(DUMMY, **{name: ""}))
        for key, value in (
            ("APPLE_TEAM_ID", "bad-team"),
            ("BUILD_CERTIFICATE_BASE64", "!invalid!"),
        ):
            with self.assertRaises(ReleaseError):
                validate_credentials(dict(DUMMY, **{key: value}))

    def test_local_file_is_explicit_private_and_never_shell_evaluated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env.macos-release"
            text = "\n".join(f'{key}="{value}"' for key, value in DUMMY.items())
            path.write_text(text)
            path.chmod(0o600)
            with patch.dict(os.environ, {"P12_PASSWORD": "different"}):
                self.assertEqual(credentials.load_credentials(path), DUMMY)
            path.write_text("P12_PASSWORD=$(do-not-execute)\n")
            self.assertEqual(
                credentials.load_credentials(path)["P12_PASSWORD"], "$(do-not-execute)"
            )
            path.chmod(0o644)
            with self.assertRaisesRegex(ReleaseError, "0600"):
                credentials.load_credentials(path)
            path.chmod(0o600)
            for invalid in (
                "UNKNOWN=value",
                "P12_PASSWORD=a\nP12_PASSWORD=b",
                "P12_PASSWORD='unclosed",
            ):
                path.write_text(invalid)
                with self.assertRaises(ReleaseError):
                    credentials.load_credentials(path)

    def test_identity_must_be_valid_unique_developer_id_and_matching_team(self):
        valid = (
            f'  1) {IDENTITY} "Developer ID Application: Test '
            f'({DUMMY["APPLE_TEAM_ID"]})"\n'
        )
        self.assertEqual(
            credentials.select_identity(valid, DUMMY["APPLE_TEAM_ID"]), IDENTITY
        )
        for invalid in (
            "0 valid identities found",
            valid.replace("ABCDEFGHIJ", "WRONGTEAM1"),
            valid.replace("Developer ID Application", "Apple Development"),
            valid.strip() + " (CSSMERR_TP_CERT_EXPIRED)\n",
            valid + valid.replace(IDENTITY, "B" * 40),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ReleaseError):
                credentials.select_identity(invalid, DUMMY["APPLE_TEAM_ID"])

    def test_child_environment_and_diagnostics_are_sanitized(self):
        output = " ".join(DUMMY.values())
        with (
            patch.dict(os.environ, DUMMY),
            patch(
                "macos.common.subprocess.run", return_value=result(output, returncode=1)
            ) as run,
        ):
            runner = Runner(DUMMY)
            with self.assertRaises(ReleaseError) as caught:
                runner.run(
                    "Import certificate", "security", "-p", DUMMY["P12_PASSWORD"]
                )
            for value in DUMMY.values():
                self.assertNotIn(value, str(caught.exception))
            self.assertIn("Import certificate", str(caught.exception))
            self.assertTrue(
                set(CREDENTIAL_NAMES).isdisjoint(run.call_args.kwargs["env"])
            )
            run.side_effect = subprocess.TimeoutExpired(
                ["secret argv", *DUMMY.values()], 1, output=output.encode()
            )
            with self.assertRaises(ReleaseError) as caught:
                runner.run("Wait for Apple", "xcrun")
            self.assertNotIn("secret argv", str(caught.exception))
            for value in DUMMY.values():
                self.assertNotIn(value, str(caught.exception))

    def test_redaction_includes_local_and_inherited_values(self):
        inherited = "inherited-other-apple-password"
        with patch.dict(os.environ, {"APPLE_APP_SPECIFIC_PASSWORD": inherited}):
            runner = Runner(DUMMY)
        text = runner.redact(inherited + " " + DUMMY["APPLE_APP_SPECIFIC_PASSWORD"])
        self.assertEqual(text, "[REDACTED] [REDACTED]")

    def test_missing_ci_credentials_fail_before_build_or_apple_tools(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("macos.release.sys.platform", "darwin"),
            patch("macos.release.platform.machine", return_value="arm64"),
            patch("macos.release.signal.signal"),
            patch("macos.release.prepare") as prepare,
            patch("macos.release.release") as pipeline,
            patch("sys.stderr", new_callable=io.StringIO) as error,
            self.assertRaises(SystemExit) as caught,
        ):
            release.main(["--ci"])
        self.assertEqual(caught.exception.code, 1)
        self.assertIn("Missing release credentials", error.getvalue())
        prepare.assert_not_called()
        pipeline.assert_not_called()


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.runner = Mock()
        self.original = [
            "/Users/test/Library/Keychains/login.keychain-db",
            "/Library/Keychains/System.keychain",
        ]
        self.current = self.original.copy()
        self.session = credentials.Session(self.folder / "state.json", self.runner)
        self.runner.run.side_effect = self.tool
        self.session.begin()

    def tool(self, operation, *args, **kwargs):
        if operation in (
            "Read keychain search list",
            "Verify restored keychain search list",
        ):
            return result("\n".join(json.dumps(path) for path in self.current))
        if operation == "Create temporary keychain":
            Path(args[-1]).touch()
        if operation in ("Add temporary keychain", "Restore keychain search list"):
            self.current = [str(path) for path in args[args.index("-s") + 1 :]]
        if operation == "Delete temporary keychain":
            Path(args[-1]).unlink()
        if operation == "Select signing identity":
            return result(
                f'1) {IDENTITY} "Developer ID Application: Test (ABCDEFGHIJ)"\n'
            )
        return result()

    def test_keychain_import_partition_list_and_cleanup(self):
        self.assertEqual(self.session.setup(DUMMY), IDENTITY)
        private = Path(self.session.state["directory"])
        self.assertEqual(private.stat().st_mode & 0o777, 0o700)
        self.assertFalse((private / "certificate.p12").exists())
        self.assertEqual(self.session.path.stat().st_mode & 0o777, 0o600)
        state = self.session.path.read_text()
        self.assertTrue(all(value not in state for value in DUMMY.values()))
        calls = self.runner.run.call_args_list
        partition = next(
            call for call in calls if call.args[0] == "Allow unattended codesign"
        )
        self.assertIn("apple-tool:,apple:,codesign:", partition.args)
        self.session.cleanup()
        self.assertEqual(self.current, self.original)
        self.assertFalse(private.exists())
        self.assertFalse(self.session.path.exists())
        credentials.cleanup(self.session.path, self.runner)  # idempotent always() step

    def test_setup_failure_at_each_operation_is_cleaned(self):
        operations = (
            "Create temporary keychain",
            "Unlock temporary keychain",
            "Set keychain timeout",
            "Add temporary keychain",
            "Import Developer ID certificate",
            "Allow unattended codesign",
            "Select signing identity",
            "Store notarization credentials",
        )
        self.session.cleanup()
        for failure in operations:
            with self.subTest(failure=failure):
                self.session.begin()

                def fail(operation, *args, failure=failure, **kwargs):
                    response = self.tool(operation, *args, **kwargs)
                    if operation == failure:
                        raise ReleaseError(operation)
                    return response

                self.runner.run.side_effect = fail
                with self.assertRaises(ReleaseError):
                    self.session.setup(DUMMY)
                private = Path(self.session.state["directory"])
                self.runner.run.side_effect = self.tool
                # Recover from the on-disk journal, as an always() CI step does.
                credentials.cleanup(self.session.path, self.runner)
                self.assertEqual(self.current, self.original)
                self.assertFalse(private.exists())
                self.session = credentials.Session(
                    self.folder / "state.json", self.runner
                )

    def test_cleanup_continues_on_restore_failure_and_retains_journal(self):
        self.session.setup(DUMMY)

        def fail(operation, *args, **kwargs):
            if operation == "Restore keychain search list":
                raise ReleaseError("restore")
            return self.tool(operation, *args, **kwargs)

        self.runner.run.side_effect = fail
        with self.assertRaisesRegex(ReleaseError, "restore_search_list"):
            self.session.cleanup()
        self.assertTrue(self.session.path.exists())
        self.assertIsNone(self.session.state["keychain"])
        self.runner.run.side_effect = self.tool
        credentials.cleanup(self.session.path, self.runner)
        self.assertFalse(self.session.path.exists())

    def test_concurrent_session_is_rejected(self):
        with self.assertRaisesRegex(ReleaseError, "already exists"):
            credentials.Session(self.session.path, self.runner).begin()
        self.session.cleanup()

    def test_mount_recovery_and_failed_detach_preserve_recovery_path(self):
        mount = self.folder / "mount"
        mount.mkdir()
        self.session.state["mount"] = str(mount)
        self.session.save()
        mounted = {"images": [{"system-entities": [{"mount-point": str(mount)}]}]}
        self.runner.run.side_effect = [
            result(plistlib.dumps(mounted).decode()),
            ReleaseError("busy"),
        ]
        with self.assertRaisesRegex(ReleaseError, "busy"):
            self.session.detach()
        self.assertTrue(mount.exists())
        self.assertEqual(self.session.state["mount"], str(mount))
        self.runner.run.side_effect = [
            result(plistlib.dumps(mounted).decode()),
            result(),
        ]
        self.session.detach()
        self.assertFalse(mount.exists())
        self.assertIsNone(self.session.state["mount"])
        self.session.cleanup()


class SigningTests(unittest.TestCase):
    def verification_requirement(self, *, app, runtime):
        runner = Mock()
        runner.run.side_effect = [
            result(),
            result(
                stderr="TeamIdentifier=ABCDEFGHIJ\nTimestamp=Sep 16, 2026\n"
                "flags=0x10000(runtime)\n"
            ),
            result(),
        ]
        signing.verify_code(
            runner, Path("code"), "ABCDEFGHIJ", app=app, runtime=runtime
        )
        command = runner.run.call_args_list[0].args
        return command[command.index("-R") + 1]

    def test_verification_uses_inline_requirements_for_native_code_app_and_dmg(self):
        for app, runtime in ((False, True), (True, True), (False, False)):
            with self.subTest(app=app, runtime=runtime):
                argument = self.verification_requirement(app=app, runtime=runtime)
                self.assertTrue(argument.startswith("=anchor apple generic"))
                self.assertIn(
                    "certificate leaf[field.1.2.840.113635.100.6.1.13]", argument
                )
                self.assertIn('certificate leaf[subject.OU] = "ABCDEFGHIJ"', argument)
                self.assertEqual('identifier "com.lnbits.desktop"' in argument, app)

    @unittest.skipUnless(
        sys.platform == "darwin", "Requires Apple's requirement parser"
    )
    def test_actual_verification_arguments_compile_with_apple_requirement_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "requirement.bin"
            for app, runtime in ((False, True), (True, True), (False, False)):
                with self.subTest(app=app, runtime=runtime):
                    argument = self.verification_requirement(app=app, runtime=runtime)
                    Runner(DUMMY).run(
                        "Compile verification requirement",
                        "/usr/bin/csreq",
                        "-r",
                        argument,
                        "-b",
                        output,
                    )
                    self.assertGreater(output.stat().st_size, 0)

    def test_native_data_is_signed_inside_out_with_scoped_entitlements(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "LNbits.app"
            paths = [
                "Contents/MacOS/LNbits",
                "Contents/Frameworks/Python.framework/Versions/3.12/Python",
                "Contents/Frameworks/sidecars/node",
                "Contents/Frameworks/sidecars/phoenixd",
                "Contents/Resources/sidecars/spark/node_modules/native.node",
                "Contents/Frameworks/_tkinter.so",
            ]
            for name in paths:
                path = app / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"\xcf\xfa\xed\xfe" + b"dummy Mach-O")
            (app / "Contents/Frameworks/alias").symlink_to("_tkinter.so")
            runner = Mock()
            signing.sign_app(
                runner, app, IDENTITY, "/private/temp.keychain-db", "arm64"
            )
            calls = runner.run.call_args_list
            signed = [call.args[-1] for call in calls]
            self.assertEqual(signed[-1], app)
            self.assertEqual(len(signed), len(paths) + 2)  # framework and outer app
            self.assertLess(
                signed.index(app / paths[1]),
                signed.index(app / "Contents/Frameworks/Python.framework"),
            )
            for call in calls:
                self.assertNotIn("--deep", call.args)
                self.assertIn("--timestamp", call.args)
                self.assertIn("--keychain", call.args)
                self.assertIn(IDENTITY, call.args)
                has_entitlements = call.args[-1] in (
                    app,
                    app / paths[0],
                    app / paths[2],
                )
                self.assertEqual("--entitlements" in call.args, has_entitlements)

    def test_team_timestamp_runtime_and_entitlements_are_required(self):
        details = (
            "TeamIdentifier=ABCDEFGHIJ\nTimestamp=Sep 16, 2026\n"
            "flags=0x10000(runtime)\n"
        )
        runner = Mock()
        for bad in (None, "TeamIdentifier=WRONGTEAM1", "Timestamp=", "flags=0x0"):
            display = details
            if bad:
                key = bad.split("=", 1)[0]
                display = (
                    "\n".join(
                        bad if line.startswith(key + "=") else line
                        for line in details.splitlines()
                    )
                    + "\n"
                )
            runner.run.side_effect = [result(), result(stderr=display), result()]
            if bad:
                with self.assertRaises(ReleaseError):
                    signing.verify_code(runner, Path("code"), "ABCDEFGHIJ")
            else:
                signing.verify_code(runner, Path("code"), "ABCDEFGHIJ")
        runner.run.side_effect = [
            result(),
            result(stderr=details),
            result(
                plistlib.dumps({"com.apple.security.get-task-allow": True}).decode()
            ),
        ]
        with self.assertRaisesRegex(ReleaseError, "entitlements"):
            signing.verify_code(runner, Path("code"), "ABCDEFGHIJ")

    def test_notarization_accepts_only_exact_accepted_and_reports_id(self):
        for status in ("Accepted", "Invalid", "In Progress", "accepted", None):
            with self.subTest(status=status):
                runner = Runner(DUMMY)
                runner.run = Mock(
                    side_effect=[
                        result(json.dumps({"id": SUBMISSION})),
                        result(json.dumps({"status": status})),
                        result("diagnostic " + DUMMY["APPLE_APP_SPECIFIC_PASSWORD"]),
                    ]
                )
                with patch("sys.stdout", new_callable=io.StringIO) as output:
                    if status == "Accepted":
                        signing.notarize(runner, Path("app.zip"), "temp.keychain-db")
                        self.assertEqual(runner.run.call_count, 2)
                    else:
                        with self.assertRaises(ReleaseError) as caught:
                            signing.notarize(
                                runner, Path("app.zip"), "temp.keychain-db"
                            )
                        self.assertIn(SUBMISSION, str(caught.exception))
                        self.assertNotIn(
                            DUMMY["APPLE_APP_SPECIFIC_PASSWORD"], str(caught.exception)
                        )
                    self.assertIn(SUBMISSION, output.getvalue())
                wait = runner.run.call_args_list[1]
                self.assertIn("--timeout", wait.args)
                self.assertLessEqual(wait.kwargs["timeout"], 1860)

    def test_malformed_notary_json_and_nonzero_accepted_fail(self):
        for submit in ("not json", "{}", '{"id": "bad id"}'):
            runner = Mock()
            runner.run.return_value = result(submit)
            with self.assertRaises(ReleaseError):
                signing.notarize(runner, Path("app.zip"), "temp.keychain-db")
            self.assertEqual(runner.run.call_count, 1)
        runner = Runner(DUMMY)
        runner.run = Mock(
            side_effect=[
                result(json.dumps({"id": SUBMISSION})),
                result('{"status":"Accepted"}', returncode=1),
                result(),
            ]
        )
        with self.assertRaises(ReleaseError):
            signing.notarize(runner, Path("app.zip"), "temp.keychain-db")

    def test_notarization_wait_timeout_keeps_submission_id(self):
        runner = Runner(DUMMY)
        runner.run = Mock(
            side_effect=[
                result(json.dumps({"id": SUBMISSION})),
                ReleaseError("Wait timed out"),
            ]
        )
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            with self.assertRaisesRegex(ReleaseError, "timed out"):
                signing.notarize(runner, Path("app.zip"), "temp.keychain-db")
        self.assertIn(SUBMISSION, output.getvalue())
        self.assertEqual(runner.run.call_count, 2)

    def test_entitlement_override_cannot_broaden_release_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            entitlements = Path(directory) / "override.plist"
            entitlements.write_bytes(
                plistlib.dumps(
                    {"com.apple.security.cs.disable-library-validation": True}
                )
            )
            with patch.dict(os.environ, {"MACOS_ENTITLEMENTS_FILE": str(entitlements)}):
                with self.assertRaises(ReleaseError):
                    signing.entitlement_file(
                        Path("LNbits.app"), Path("LNbits.app"), "arm64"
                    )


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(contextlib.chdir(self.folder))
        Path("pyproject.toml").write_text('[project]\nversion="1.6.2-rc1"\n')
        self.app = Path("dist/LNbits.app").resolve()
        (self.app / "Contents").mkdir(parents=True)
        (self.app / "Contents/Info.plist").write_bytes(plistlib.dumps({}))
        self.enterContext(patch("macos.dmg.platform.machine", return_value="arm64"))
        self.output = dmg.output_path()
        self.events = []
        self.session = Mock(
            state={"keychain": "temp.keychain-db", "directory": str(self.folder)}
        )
        self.session.setup.return_value = IDENTITY
        self.session.cleanup.side_effect = lambda: self.events.append("cleanup")
        self.runner = Runner(DUMMY)

        def run(operation, *args, **kwargs):
            self.events.append(operation)
            if operation == "Archive signed app":
                Path(args[-1]).write_bytes(b"zip")
            return result()

        self.runner.run = Mock(side_effect=run)
        for name in ("sign_app", "verify_app", "verify_image"):
            self.enterContext(
                patch(
                    "macos.release." + name,
                    side_effect=lambda *a, _name=name, **k: self.events.append(_name),
                )
            )
        self.enterContext(
            patch(
                "macos.release.sign",
                side_effect=lambda *a, **k: self.events.append("sign_dmg"),
            )
        )

        def notarize(runner, artifact, keychain):
            self.events.append(
                "notarize_app" if artifact.suffix == ".zip" else "notarize_dmg"
            )

        self.notarize = self.enterContext(
            patch("macos.release.notarize", side_effect=notarize)
        )

        def staple(runner, artifact):
            self.events.append(
                "staple_app" if artifact.suffix == ".app" else "staple_dmg"
            )
            if artifact.suffix == ".dmg":
                artifact.write_bytes(artifact.read_bytes() + b" stapled")

        self.enterContext(patch("macos.release.staple", side_effect=staple))

        def create(*args, **kwargs):
            self.events.append("create_dmg")
            self.output.write_bytes(b"final dmg")

        self.enterContext(patch("macos.dmg.create", side_effect=create))
        self.enterContext(patch.dict(os.environ, {}, clear=True))

    def test_order_checksum_and_no_app_mutation_after_stapling(self):
        release.release(
            self.runner,
            self.session,
            signed=True,
            credentials=DUMMY,
            arch="arm64",
            skip_build=True,
        )
        self.assertEqual(
            self.events,
            [
                "sign_app",
                "verify_app",
                "Archive signed app",
                "notarize_app",
                "staple_app",
                "create_dmg",
                "sign_dmg",
                "notarize_dmg",
                "staple_dmg",
                "verify_image",
                "cleanup",
            ],
        )
        self.assertEqual(self.notarize.call_count, 2)
        checksum = self.output.with_suffix(".dmg.sha256").read_text()
        self.assertEqual(
            checksum,
            f'{hashlib.sha256(b"final dmg stapled").hexdigest()}  {self.output.name}\n',
        )
        metadata = plistlib.loads((self.app / "Contents/Info.plist").read_bytes())
        self.assertEqual(metadata["CFBundleVersion"], "1.6.2")
        self.assertEqual(metadata["LSMinimumSystemVersion"], "15.0")

    def test_failure_at_every_gate_cleans_and_removes_artifacts(self):
        for target in (
            "sign_app",
            "verify_app",
            "notarize",
            "staple",
            "dmg.create",
            "sign",
            "verify_image",
            "session.cleanup",
        ):
            with self.subTest(target=target):
                self.output.write_bytes(b"stale dmg")
                self.output.with_suffix(".dmg.sha256").write_text("stale checksum")
                if target == "session.cleanup":
                    manager = patch.object(
                        self.session, "cleanup", side_effect=ReleaseError(target)
                    )
                else:
                    manager = patch(
                        "macos.release." + target, side_effect=ReleaseError(target)
                    )
                with manager, self.assertRaises(ReleaseError):
                    release.release(
                        self.runner,
                        self.session,
                        signed=True,
                        credentials=DUMMY,
                        arch="arm64",
                        skip_build=True,
                    )
                self.assertFalse(self.output.exists())
                self.assertFalse(self.output.with_suffix(".dmg.sha256").exists())
                self.session.cleanup.assert_called()

    def test_unsigned_never_imports_credentials_or_notarizes(self):
        release.release(
            self.runner,
            self.session,
            signed=False,
            credentials={},
            arch="arm64",
            skip_build=True,
        )
        self.session.setup.assert_not_called()
        self.notarize.assert_not_called()
        self.assertTrue(self.output.with_suffix(".dmg.sha256").exists())

    def test_image_creation_copies_without_metadata_changes_or_resigning(self):
        original = self.app / "Contents/Info.plist"
        before = original.read_bytes()
        actual_create = CREATE_DMG

        def run(operation, *args, **kwargs):
            self.assertNotIn("codesign", " ".join(str(arg) for arg in args))
            if operation == "Copy finalized app":
                shutil.copytree(args[-2], args[-1])
            if operation == "Create DMG":
                staging = Path(args[args.index("-srcfolder") + 1])
                self.assertEqual(
                    (staging / "LNbits.app/Contents/Info.plist").read_bytes(), before
                )
                self.assertEqual(
                    (staging / "Applications").readlink(), Path("/Applications")
                )
                self.assertNotIn("Open Anyway", (staging / "Read me.txt").read_text())

        self.runner.run.side_effect = run
        actual_create(self.app, self.output, self.runner, signed=True)
        self.assertEqual(original.read_bytes(), before)

    def test_second_submission_failure_never_staples_or_checksums_dmg(self):
        original = self.notarize.side_effect

        def fail_dmg(runner, artifact, keychain):
            original(runner, artifact, keychain)
            if artifact.suffix == ".dmg":
                raise ReleaseError("DMG not Accepted")

        self.notarize.side_effect = fail_dmg
        with self.assertRaisesRegex(ReleaseError, "DMG not Accepted"):
            release.release(
                self.runner,
                self.session,
                signed=True,
                credentials=DUMMY,
                arch="arm64",
                skip_build=True,
            )
        self.assertIn("staple_app", self.events)
        self.assertNotIn("staple_dmg", self.events)
        self.assertEqual(self.notarize.call_count, 2)
        self.assertFalse(self.output.with_suffix(".dmg.sha256").exists())
        self.assertEqual(self.events[-1], "cleanup")

    def test_checksum_recheck_detects_changed_final_bytes(self):
        self.output.write_bytes(b"completed image")
        with patch("macos.dmg.checksum", side_effect=["old bytes", "changed bytes"]):
            with self.assertRaisesRegex(RuntimeError, "checksum verification failed"):
                dmg.write_checksum(self.output)
        self.assertFalse(self.output.with_suffix(".dmg.sha256").exists())


class DeliverableTests(unittest.TestCase):
    def test_mount_is_read_only_and_always_detached_on_smoke_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            mount = Path(directory) / "mount"
            mount.mkdir()
            (mount / "Applications").symlink_to("/Applications")
            session = Mock(state={})
            runner = Mock()

            def run(operation, *args, **kwargs):
                if operation == "Smoke packaged server and shutdown":
                    raise ReleaseError("smoke failed")
                return result()

            runner.run.side_effect = run
            with (
                patch("macos.verify.tempfile.mkdtemp", return_value=str(mount)),
                patch("macos.verify.verify_code"),
                patch("macos.verify.verify_app"),
                patch("macos.verify.bundled_data"),
                self.assertRaisesRegex(ReleaseError, "smoke failed"),
            ):
                verify.verify_image(
                    runner, session, Path("final.dmg"), "arm64", "ABCDEFGHIJ"
                )
            session.detach.assert_called_once()
            calls = runner.run.call_args_list
            attach = next(
                call for call in calls if call.args[0] == "Mount final DMG read-only"
            )
            self.assertIn("-readonly", attach.args)
            self.assertIn(Path("final.dmg"), attach.args)
            for operation in (
                "Verify DMG integrity",
                "Validate DMG ticket",
                "Assess DMG Gatekeeper",
                "Assess app Gatekeeper",
                "Validate app ticket",
                "Smoke bundled sidecars",
            ):
                self.assertIn(operation, [call.args[0] for call in calls])

    def test_native_architecture_in_data_is_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "LNbits.app"
            native = app / "Contents/Resources/spark/dependencies/native.node"
            native.parent.mkdir(parents=True)
            native.write_bytes(b"\xcf\xfa\xed\xfe" + b"dummy Mach-O")
            runner = Mock()
            runner.run.return_value = result("x86_64")
            with self.assertRaisesRegex(ReleaseError, "Wrong native architecture"):
                verify.verify_architecture(runner, app, "arm64")
            runner.run.return_value = result("arm64 x86_64")
            verify.verify_architecture(runner, app, "arm64")
            runner.run.assert_called_with(
                "Verify native architecture", "/usr/bin/lipo", "-archs", native
            )


if __name__ == "__main__":
    unittest.main()
