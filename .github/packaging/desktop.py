"""Shared desktop entry point; deliberately imports LNbits only in the worker."""

import argparse
import asyncio
import contextlib
import importlib.util
import multiprocessing as mp
import os
import signal
import socket
import sys
import time
import traceback
import webbrowser
from pathlib import Path


def default_folder():
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "LNbits"
    return (
        Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        / "lnbits-desktop"
    )


def configuration(host, port, folder, https_only, admin_ui):
    host = host.strip()
    if not host or "://" in host or "/" in host:
        raise ValueError("Enter a host name or IP address, without http:// or a path.")
    try:
        port = int(port)
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise ValueError("Port must be a number between 1 and 65535.") from None
    if not folder.strip():
        raise ValueError("Choose a data folder.")
    root = Path(folder).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return {
        "HOST": host,
        "PORT": str(port),
        "LNBITS_DATA_FOLDER": str(root),
        "LNBITS_EXTENSIONS_PATH": os.environ.get("LNBITS_EXTENSIONS_PATH", str(root)),
        "AUTH_HTTPS_ONLY": str(https_only).lower(),
        "LNBITS_ADMIN_UI": str(admin_ui).lower(),
    }


def browser_host(host):
    return {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(host, host)  # noqa: S104


def worker(environment, stop, ready):
    os.environ.update(environment)
    os.environ.setdefault("DEBUG", "false")
    # Core templates and static files are resolved relative to the package root.
    package = importlib.util.find_spec("lnbits")
    if package is None or package.origin is None:
        raise RuntimeError("LNbits package is missing")
    os.chdir(Path(package.origin).parent.parent)
    log_dir = Path(environment["LNBITS_DATA_FOLDER"], "logs")
    log_dir.mkdir(exist_ok=True)
    with (
        (log_dir / "desktop.log").open("a", encoding="utf-8", buffering=1) as log,
        contextlib.redirect_stdout(log),
        contextlib.redirect_stderr(log),
    ):
        try:
            run_server(environment, stop, ready)
        except KeyboardInterrupt:
            # Uvicorn re-raises Ctrl+C after completing its shutdown handlers.
            pass
        except Exception:
            traceback.print_exc(file=log)
            sys.exit(1)


def run_server(environment, stop, ready):
    import uvicorn

    from lnbits.server import server_restart
    from lnbits.settings import settings

    Path(settings.lnbits_extensions_path, "extensions").mkdir(
        parents=True, exist_ok=True
    )
    settings.wasm_extensions_dir.mkdir(parents=True, exist_ok=True)
    server = uvicorn.Server(
        uvicorn.Config(
            "lnbits.__main__:app",
            host=environment["HOST"],
            port=int(environment["PORT"]),
            loop="asyncio",
            log_config=None,
        )
    )

    async def serve():
        async def monitor():
            while not server.should_exit:
                if server.started:
                    ready.set()
                if stop.is_set() or server_restart.is_set():
                    server.should_exit = True
                await asyncio.sleep(0.1)

        task = asyncio.create_task(monitor())
        try:
            await server.serve()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(serve())
    if not ready.is_set() and not stop.is_set():
        sys.exit(1)
    if server_restart.is_set() and not stop.is_set():
        sys.exit(75)


class Server:
    def __init__(self, environment):
        self.environment = environment
        self.context = mp.get_context("spawn")
        self.stop_event = self.context.Event()
        self.ready = self.context.Event()
        self.process = None
        self.stopping_at = None
        self.started_at = None

    def start(self):
        # Fail before launching if another service is using the requested address.
        with socket.create_server(
            (self.environment["HOST"], int(self.environment["PORT"])),
            family=(
                socket.AF_INET6 if ":" in self.environment["HOST"] else socket.AF_INET
            ),
        ):
            pass
        self.ready.clear()
        self.process = self.context.Process(
            target=worker, args=(self.environment, self.stop_event, self.ready)
        )
        self.process.start()
        self.started_at = time.monotonic()

    def stop(self):
        if self.stopping_at is None:
            self.stopping_at = time.monotonic()
            self.stop_event.set()

    def poll(self):
        if self.process is None:
            return 0
        if self.process.is_alive():
            if (
                not self.ready.is_set()
                and self.started_at is not None
                and time.monotonic() - self.started_at > 120
            ):
                self.stop()
            if (
                self.stopping_at is not None
                and time.monotonic() - self.stopping_at > 30
            ):
                self.process.kill()
            return None
        self.process.join()
        code = self.process.exitcode
        if code == 75 and self.stopping_at is None:
            self.start()
            return None
        return code


def gui():  # noqa: C901 - UI callbacks share the window and server lifecycle.
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("LNbits")
    frame = ttk.Frame(root, padding=24)
    frame.grid(sticky="nsew")
    root.columnconfigure(0, weight=1)
    frame.columnconfigure(1, weight=1)
    ttk.Label(frame, text="Launch LNbits", font=("", 20, "bold")).grid(
        row=0, columnspan=3, sticky="w", pady=(0, 16)
    )
    fields = {}
    defaults = [
        (
            "HOST",
            "Host",
            "127.0.0.1",
            "127.0.0.1 allows this computer only; 0.0.0.0 allows network connections.",
        ),
        ("PORT", "Port", "5000", "Choose an unused port between 1 and 65535."),
        (
            "LNBITS_DATA_FOLDER",
            "Data folder",
            str(default_folder()),
            "Stores wallets, settings, logs and extensions. "
            "Keep this folder backed up.",
        ),
    ]
    for index, (key, label, default, tip) in enumerate(defaults):
        row = index * 2 + 1
        fields[key] = tk.StringVar(value=os.environ.get(key, default))
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12))
        ttk.Entry(frame, textvariable=fields[key], width=48).grid(
            row=row, column=1, sticky="ew"
        )
        ttk.Label(frame, text=tip, wraplength=480).grid(
            row=row + 1, column=1, columnspan=2, sticky="w", pady=(4, 12)
        )

    def browse():
        folder = filedialog.askdirectory(parent=root)
        if folder:
            fields["LNBITS_DATA_FOLDER"].set(folder)

    ttk.Button(frame, text="Browse…", command=browse).grid(row=5, column=2, padx=(8, 0))
    https = tk.BooleanVar(
        value=os.environ.get("AUTH_HTTPS_ONLY", "false").lower() in ("true", "1", "yes")
    )
    admin = tk.BooleanVar(
        value=os.environ.get("LNBITS_ADMIN_UI", "true").lower() in ("true", "1", "yes")
    )
    ttk.Checkbutton(frame, text="AUTH_HTTPS_ONLY", variable=https).grid(
        row=7, columnspan=3, sticky="w"
    )
    ttk.Label(
        frame,
        text=(
            "Require HTTPS for login cookies. Leave off for local HTTP; "
            "enable behind HTTPS.\nThis does not enable TLS on the server."
        ),
        wraplength=560,
    ).grid(row=8, columnspan=3, sticky="w", pady=(4, 12))
    ttk.Checkbutton(frame, text="LNBITS_ADMIN_UI", variable=admin).grid(
        row=9, columnspan=3, sticky="w"
    )
    ttk.Label(
        frame, text="Allow the administrator to configure LNbits in the browser."
    ).grid(row=10, columnspan=3, sticky="w", pady=(4, 16))
    status = tk.StringVar(value="Choose your settings, then launch.")
    ttk.Label(frame, textvariable=status, wraplength=560).grid(
        row=11, columnspan=3, sticky="w", pady=8
    )
    server = None
    closing = False

    def close():
        nonlocal closing
        if server is None:
            root.destroy()
        else:
            closing = True
            server.stop()
            status.set("Stopping LNbits…")
            launch.configure(state="disabled")
            open_browser.configure(state="disabled")

    def poll():
        if server is None:
            return
        try:
            code = server.poll()
        except OSError:
            code = 1
        if code is not None:
            if closing:
                root.destroy()
                return
            status.set(
                f"LNbits stopped (exit {code}). "
                "See logs/desktop.log in your data folder."
            )
            launch.configure(text="Close", command=close)
            open_browser.configure(state="disabled")
            return
        if not closing and server.ready.is_set():
            status.set("LNbits is running. Close this window to stop the server.")
            open_browser.configure(state="normal")
        elif not closing:
            open_browser.configure(state="disabled")
            status.set(
                "Starting LNbits…"
                if server.stopping_at is None
                else "Startup timed out; stopping LNbits…"
            )
        root.after(200, poll)

    def start():
        nonlocal server
        try:
            env = configuration(
                *(fields[key].get() for key in ("HOST", "PORT", "LNBITS_DATA_FOLDER")),
                https.get(),
                admin.get(),
            )
            server = Server(env)
            server.start()
        except (ValueError, OSError):
            server = None
            messagebox.showerror(
                "Cannot launch LNbits",
                "Check the host, port and folder. The address may already be in use "
                "or the folder may not be writable.",
                parent=root,
            )
            return
        for child in frame.winfo_children():
            if isinstance(child, (ttk.Entry, ttk.Checkbutton, ttk.Button)):
                child.configure(state="disabled")
        launch.configure(text="Stop LNbits", command=close, state="normal")
        status.set("Starting LNbits…")
        poll()

    def open_url():
        if server:
            host = browser_host(server.environment["HOST"])
            if ":" in host:
                host = f"[{host}]"
            webbrowser.open(f"http://{host}:{server.environment['PORT']}")

    launch = ttk.Button(frame, text="Launch LNbits", command=start)
    launch.grid(row=12, column=0, columnspan=2, sticky="w", pady=(12, 0))
    open_browser = ttk.Button(
        frame, text="Open in browser", command=open_url, state="disabled"
    )
    open_browser.grid(row=12, column=2, pady=(12, 0))
    root.protocol("WM_DELETE_WINDOW", close)
    try:
        root.mainloop()
    finally:
        if server and server.process:
            server.stop()
            while server.poll() is None:
                time.sleep(0.1)


def windows_terminal():
    import ctypes
    from ctypes import wintypes

    # A onefile build has both a bootloader parent and a Python child. A console
    # containing only those processes was created by double-clicking the app.
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_processes = kernel32.GetConsoleProcessList
    get_processes.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]
    get_processes.restype = wintypes.DWORD
    processes = (wintypes.DWORD * 1)()
    count = get_processes(processes, 1)
    if not count:
        return False
    processes = (wintypes.DWORD * count)()
    count = get_processes(processes, len(processes))
    if count > len(processes):
        return True
    own = {os.getpid()}
    if getattr(sys, "frozen", False):
        own.add(os.getppid())
    return any(pid not in own for pid in processes[:count])


def launched_from_terminal():
    if sys.platform == "win32":
        return windows_terminal()
    if any(
        stream is not None and stream.isatty()
        for stream in (sys.stdin, sys.stdout, sys.stderr)
    ):
        return True
    # Keep redirected/piped terminal launches headless too.
    try:
        descriptor = os.open("/dev/tty", os.O_RDONLY | os.O_NOCTTY)
    except OSError:
        return False
    os.close(descriptor)
    return True


def should_show_gui():
    if len(sys.argv) != 1 or launched_from_terminal():
        return False
    return sys.platform == "win32" or bool(
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    )


def main():
    mp.freeze_support()
    parser = argparse.ArgumentParser(description="LNbits desktop launcher")
    parser.add_argument(
        "--headless", action="store_true", help="Run without the desktop window"
    )
    parser.add_argument("--stop-file", help="Headless mode: stop when this file exists")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", default=os.environ.get("PORT", "5000"))
    args = parser.parse_args()
    if not args.headless and should_show_gui():
        gui()
        return
    env = configuration(
        args.host,
        args.port,
        os.environ.get("LNBITS_DATA_FOLDER", str(default_folder())),
        os.environ.get("AUTH_HTTPS_ONLY", "false").lower() == "true",
        os.environ.get("LNBITS_ADMIN_UI", "true").lower() == "true",
    )
    server = Server(env)
    signal.signal(signal.SIGTERM, lambda *_: server.stop())
    signal.signal(signal.SIGINT, lambda *_: server.stop())
    server.start()
    while (code := server.poll()) is None:
        if args.stop_file and Path(args.stop_file).exists():
            server.stop()
        time.sleep(0.1)
    sys.exit(code)


if __name__ == "__main__":
    main()
