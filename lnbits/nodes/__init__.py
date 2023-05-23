from typing import Optional

from .base import Node


def get_node_class() -> Optional[Node]:
    return NODE


def set_node_class(node: Node):
    global NODE
    NODE = node


NODE: Optional[Node] = None
