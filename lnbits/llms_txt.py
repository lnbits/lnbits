"""Generate llms.txt markdown from FastAPI OpenAPI schema for AI agents."""

from typing import Any
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.routing import APIRoute


def generate_llms_txt(app: FastAPI) -> str:
    """Convert an OpenAPI schema to llms.txt markdown format."""
    openapi_schema = app.openapi()
    lines: list[str] = []

    # H1: API Title
    info = openapi_schema.get("info", {})
    title = info.get("title", "API")
    lines.append(f"# {title}")
    lines.append("")

    # Blockquote: Description
    description = info.get("description")
    if description:
        for line in description.strip().split("\n"):
            lines.append(f"> {line}")
        lines.append("")

    # Group endpoints by tag
    paths = openapi_schema.get("paths", {})
    endpoints_by_tag: dict[str, list[dict[str, Any]]] = {}

    for path, path_item in paths.items():
        for method in ["get", "post", "put", "patch", "delete", "head", "options"]:
            if method not in path_item:
                continue
            operation = path_item[method]
            tags = operation.get("tags", ["Endpoints"])
            tag = tags[0] if tags else "Endpoints"
            if tag not in endpoints_by_tag:
                endpoints_by_tag[tag] = []
            endpoints_by_tag[tag].append({
                "path": path,
                "method": method.upper(),
                "operation": operation,
            })

    # Generate sections by tag
    for tag, endpoints in endpoints_by_tag.items():
        lines.append(f"## {tag}")
        lines.append("")
        for endpoint in endpoints:
            method = endpoint["method"]
            path = endpoint["path"]
            operation = endpoint["operation"]
            summary = operation.get("summary", "")
            if summary:
                lines.append(f"### `{method} {path}` - {summary}")
            else:
                lines.append(f"### `{method} {path}`")
            lines.append("")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def create_llms_txt_route(app: FastAPI) -> None:
    """Add a /llms.txt endpoint to the app."""
    @app.get(
        "/docs/llms.txt",
        response_class=PlainTextResponse,
        include_in_schema=False,
        summary="Get LLM-friendly API documentation",
    )
    async def get_llms_txt() -> str:
        """Return the API documentation in llms.txt markdown format."""
        return generate_llms_txt(app)
