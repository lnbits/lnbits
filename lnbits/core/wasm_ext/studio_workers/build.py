"""Trusted compiler entry point; invoked with -I and an empty host environment.

No extension Python is imported natively. Only input/src is exposed to the
compiler's WASI guest. The output and original snapshot are outside that preopen.
"""

import importlib
import json
import resource
import sys
from pathlib import Path


def main() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
    request = json.loads(sys.stdin.readline())
    root = Path(request["scratch"])
    compiler = importlib.import_module("componentize_py")
    print(json.dumps({"log": "Compiling Python inside the WASM sandbox…"}), flush=True)
    compiler.componentize(
        wit_path=[str(root / "input/wasm/lnbits-extension.wit")],
        worlds=[request["world"]],
        features=[],
        all_features=False,
        world_module="wit_world",
        python_path=[str(root / "input/src")],
        module_worlds=[],
        app_name="app",
        output_path=str(root / "module.wasm"),
        stub_wasi=True,
        import_interface_names=[],
        export_interface_names=[],
        full_names=False,
        intersect_world=None,
    )
    print(
        json.dumps({"log": "Compilation finished. Validating the component…"}),
        flush=True,
    )
    validate(root / "module.wasm", request)
    print(
        json.dumps({"log": "Component imports, exports and runtime limits validated."}),
        flush=True,
    )


def validate(path: Path, request: dict) -> None:
    wasm = importlib.import_module("wasmtime")
    component = importlib.import_module("wasmtime.component")
    config = wasm.Config()
    config.wasm_component_model = True
    config.consume_fuel = True
    config.max_wasm_stack = request["limits"]["wasm_runtime_max_wasm_stack_bytes"]
    engine = wasm.Engine(config)
    store = wasm.Store(engine)
    limits = request["limits"]
    store.set_limits(
        memory_size=limits["wasm_runtime_max_memory_bytes"],
        instances=limits["wasm_runtime_max_instances"],
        tables=limits["wasm_runtime_max_tables"],
        memories=limits["wasm_runtime_max_memories"],
        table_elements=limits["wasm_runtime_max_table_elements"],
    )
    store.set_fuel(limits["wasm_runtime_max_fuel"])
    store.set_wasi(wasm.WasiConfig())
    linker = component.Linker(engine)
    linker.add_wasip2()
    with linker.root() as imports:
        for interface, methods in request["host"].items():
            with imports.add_instance("lnbits:extension/" + interface) as instance:
                for method in methods:
                    instance.add_func(method, deny_host_call)
    loaded = component.Component.from_file(engine, str(path))
    instance = linker.instantiate(store, loaded)
    for export in request["exports"]:
        function = instance.get_func(store, export)
        if not function:
            raise ValueError("Missing declared export: " + export)
        signature = function.type(store)
        if (
            len(signature.params) != 1
            or not isinstance(signature.params[0][1], component.String)
            or not isinstance(signature.result, component.String)
        ):
            raise ValueError(
                "Exports must accept one JSON string and return a JSON string: "
                + export
            )
        # Host methods are deliberately never callable during validation.


def deny_host_call(*_args: object) -> None:
    raise ValueError("Host calls during component initialization are forbidden.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Compiler errors contain source diagnostics, never host environment/keys.
        print(json.dumps({"error": str(exc)[:12000]}), flush=True)
        sys.exit(1)
