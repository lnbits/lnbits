"""One local/CI build, signing, notarization and verification pipeline. No upload."""

import argparse
import os
import platform
import signal
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from macos import dmg
from macos.common import ReleaseError, Runner, validate_credentials
from macos.credentials import Session, cleanup, load_credentials
from macos.signing import notarize, sign, sign_app, staple, verify_app
from macos.verify import verify_image


def check_python_tk(runner, *python):
    result = runner.run(
        "Check Python/Tk",
        *python,
        "-c",
        "import tkinter; import tomllib; tkinter.Tcl().eval('info patchlevel')",
        check=False,
    )
    if result.returncode:
        raise ReleaseError(
            "Check Python/Tk: the selected Python needs working Tk support. "
            "For Homebrew Python 3.12, run `brew install python-tk@3.12`, "
            "then retry the build using that Python."
        )


def prepare(runner):
    check_python_tk(runner, sys.executable)
    runner.run("Install locked frontend dependencies", "npm", "ci", timeout=900)
    runner.run("Build frontend assets", "npm", "run", "bundle", timeout=300)
    runner.run(
        "Format frontend manifest",
        "./node_modules/.bin/prettier",
        "-w",
        "./lnbits/static/vendor.json",
    )
    runner.run(
        "Verify frontend assets", "git", "diff", "--exit-code", "--", "lnbits/static"
    )
    runner.run("Clear cryptography cache", "uv", "cache", "clean", "cryptography")
    openssl = runner.run(
        "Locate static OpenSSL", "brew", "--prefix", "openssl@3"
    ).stdout.strip()
    runner.run(
        "Install locked Python dependencies",
        "uv",
        "sync",
        "--python",
        sys.executable,
        "--locked",
        "--no-dev",
        "--no-editable",
        "--reinstall-package",
        "cryptography",
        env={"OPENSSL_STATIC": "1", "OPENSSL_DIR": openssl},
        timeout=1800,
    )
    check_python_tk(runner, "uv", "run", "--no-sync", "python")
    runner.run(
        "Install existing PyInstaller pin",
        "uv",
        "pip",
        "install",
        "pyinstaller==6.22.2",
        timeout=300,
    )


def build_application(runner):
    result = runner.run(
        "Build PyInstaller application",
        "uv",
        "run",
        "--no-sync",
        "python",
        ".github/packaging/build.py",
        timeout=1800,
    )
    # PyInstaller may warn about native data it did not sign. No release is
    # accepted until our independent recursive signing and verification passes.
    warnings = [
        line
        for line in (result.stdout + result.stderr).splitlines()
        if "sign" in line.lower() and "warn" in line.lower()
    ]
    if warnings:
        print(
            runner.redact(
                "PyInstaller signing warnings require explicit verification:\n"
                + "\n".join(warnings)
            )
        )


def release(runner, session, *, signed, credentials, arch, skip_build=False):
    output = None
    session.begin()
    try:
        try:
            output = dmg.output_path()
            output.unlink(missing_ok=True)
            output.with_suffix(".dmg.sha256").unlink(missing_ok=True)
            if not skip_build:
                build_application(runner)
            app = Path("dist/LNbits.app").resolve()
            dmg.finalize_app(app)
            if signed:
                identity = session.setup(credentials)
                configured = os.environ.get("MACOS_CODESIGN_IDENTITY")
                if configured and configured != identity:
                    raise ReleaseError(
                        "MACOS_CODESIGN_IDENTITY must match the selected "
                        "certificate fingerprint"
                    )
                keychain = session.state["keychain"]
                sign_app(runner, app, identity, keychain, arch)
                verify_app(runner, app, credentials["APPLE_TEAM_ID"], arch)
                archive = Path(session.state["directory"]) / "LNbits.zip"
                runner.run(
                    "Archive signed app",
                    "/usr/bin/ditto",
                    "-c",
                    "-k",
                    "--sequesterRsrc",
                    "--keepParent",
                    app,
                    archive,
                    timeout=600,
                )
                notarize(runner, archive, keychain)
                archive.unlink()
                staple(runner, app)
            else:
                sign_app(runner, app, "-", None, arch)
            # This only copies the finalized app, preserving its ticket.
            dmg.create(app, output, runner, signed=signed)
            if signed:
                sign(runner, output, identity, keychain, runtime=False)
                notarize(runner, output, keychain)
                staple(runner, output)
            verify_image(
                runner,
                session,
                output,
                arch,
                credentials["APPLE_TEAM_ID"] if signed else None,
            )
        finally:
            session.cleanup()
        # Cleanup is a publication gate too; never leave a successful checksum
        # beside a failed release. Re-read the completed image to verify it.
        dmg.write_checksum(output)
    except BaseException:
        if output:
            output.with_suffix(".dmg.sha256").unlink(missing_ok=True)
            output.unlink(missing_ok=True)
        raise
    print(
        f"Verified {'signed and notarized' if signed else 'ad-hoc'} artifact: {output}"
    )


def interrupted(signum, _frame):
    raise ReleaseError(f"Release interrupted by signal {signum}; cleaning up")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--unsigned", action="store_true", help="Ad-hoc development build"
    )
    mode.add_argument(
        "--ci", action="store_true", help="Read the six credentials from CI environment"
    )
    parser.add_argument("--env-file", default=".env.macos-release")
    parser.add_argument(
        "--prepared", action="store_true", help="Dependencies/frontend already prepared"
    )
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument(
        "--skip-build", action="store_true", help="Package an existing dist/LNbits.app"
    )
    parser.add_argument(
        "--cleanup", action="store_true", help="Recover an interrupted release session"
    )
    parser.add_argument(
        "--state",
        default=os.environ.get("MACOS_RELEASE_STATE", "build/macos-release-state.json"),
    )
    args = parser.parse_args(argv)
    runner = Runner()
    try:
        if sys.platform != "darwin" or platform.machine() not in ("arm64", "x86_64"):
            raise ReleaseError("Build on a native arm64 or x86_64 Mac")
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, interrupted)
        if args.cleanup:
            cleanup(args.state, runner)
            return
        credentials = {}
        if not args.unsigned and not args.prepare_only:
            credentials = load_credentials(None if args.ci else args.env_file)
            runner = Runner(credentials)
            validate_credentials(credentials)
        translated = runner.run(
            "Check native architecture",
            "/usr/sbin/sysctl",
            "-in",
            "sysctl.proc_translated",
            check=False,
        )
        if translated.stdout.strip() == "1":
            raise ReleaseError(
                "Rosetta is not supported; use native Python and a native terminal"
            )
        if not args.prepared and not args.skip_build:
            prepare(runner)
        if args.prepare_only:
            return
        release(
            runner,
            Session(args.state, runner),
            signed=not args.unsigned,
            credentials=credentials,
            arch=platform.machine(),
            skip_build=args.skip_build,
        )
    except Exception as exc:
        # No unredacted exception repr, traceback or credential-bearing argv.
        message = (
            str(exc)
            if isinstance(exc, ReleaseError)
            else f"Release operation failed ({type(exc).__name__})"
        )
        print(runner.redact(message), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
