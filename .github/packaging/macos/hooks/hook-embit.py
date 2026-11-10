"""Collect embit's native Mac library without its other platform prebuilds."""

import platform
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all("embit")
library = f"libsecp256k1_darwin_{platform.machine()}.dylib"
native = {
    (source, destination)
    for source, destination in [*datas, *binaries]
    if Path(source).name == library
}
if not native:
    raise RuntimeError(f"Missing native embit prebuild: {library}")

# Include the selected library as code, even if collect_all classified it as data.
datas = [
    entry for entry in datas if not Path(entry[0]).name.startswith("libsecp256k1_")
]
binaries = [
    entry for entry in binaries if not Path(entry[0]).name.startswith("libsecp256k1_")
] + sorted(native)
print(f"macOS: Selected embit native library: {library}", flush=True)
