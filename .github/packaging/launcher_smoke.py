"""Automate the packaged Tk window and exercise Wasmtime under hardened runtime."""

import time


def schedule(root):
    from tkinter import ttk

    import wasmtime

    # This executes generated code, rather than merely importing the library.
    store = wasmtime.Store()
    module = wasmtime.Module(
        store.engine, '(module (func (export "answer") (result i32) i32.const 42))'
    )
    instance = wasmtime.Instance(store, module, [])
    if instance.exports(store)["answer"](store) != 42:
        raise RuntimeError("Packaged Wasmtime execution failed")
    state = {"launched": False, "ready": False, "timeout": False}
    deadline = time.monotonic() + 120

    def interact():
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
            button for button in buttons if button.cget("text") == "Open in browser"
        )
        if not state["launched"]:
            launch.invoke()
            state["launched"] = True
        elif str(browser.cget("state")) == "normal":
            state["ready"] = True
            root.tk.call("tk::mac::Quit")
            return
        elif time.monotonic() > deadline:
            state["timeout"] = True
            root.tk.call("tk::mac::Quit")
            return
        root.after(100, interact)

    root.after(100, interact)
    return state
