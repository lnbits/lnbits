"""Wally's generated Python wrappers replace SWIG output-buffer signatures."""

from typing import Any

import wallycore  # type: ignore[import-untyped]

# Native calls return allocated Python bytes; the SWIG source signatures are not
# their runtime signatures. Deterministic descriptor/signing vectors cover them.
wally: Any = wallycore
