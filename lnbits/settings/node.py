from __future__ import annotations

from pydantic import Field

from .lnbits import LNbitsSettings


class NodeUISettings(LNbitsSettings):
    # on-off switch for node ui
    lnbits_node_ui: bool = Field(default=False)
    # whether to display the public node ui (only if lnbits_node_ui is True)
    lnbits_public_node_ui: bool = Field(default=False)
    # can be used to disable the transactions tab in the node ui
    # (recommended for large cln nodes)
    lnbits_node_ui_transactions: bool = Field(default=False)
