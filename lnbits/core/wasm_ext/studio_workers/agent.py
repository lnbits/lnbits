"""Pydantic 2 worker, isolated from LNbits' Pydantic 1 environment.

The only agent tools are four JSON RPCs serviced by LNbits' bound file API.
No eval, native draft imports, shell, built-in tools or provider-native tools.
"""

import asyncio
import importlib
import inspect
import json
import sys


def emit(value: dict) -> None:
    print(json.dumps(value), flush=True)


async def file_tool(operation: str, path: str = "", content: str = "") -> str:
    emit({"tool": operation, "path": path, "content": content})
    response = json.loads(await asyncio.to_thread(sys.stdin.readline))
    if "error" in response:
        raise importlib.import_module("pydantic_ai").ModelRetry(response["error"])
    return response["result"]


async def list_files() -> str:
    """List editable files in this extension's draft."""
    return await file_tool("list")


async def read_file(path: str) -> str:
    """Read a UTF-8 source file using its draft-relative path."""
    return await file_tool("read", path)


async def write_file(path: str, content: str) -> str:
    """Create or replace a UTF-8 draft source file with its complete contents."""
    return await file_tool("write", path, content)


async def delete_file(path: str) -> str:
    """Delete one draft source file. Cannot delete directories or build artifacts."""
    return await file_tool("delete", path)


def configured_model(config: dict):
    models = importlib.import_module("pydantic_ai.models")
    providers = importlib.import_module("pydantic_ai.providers")
    provider = config["provider"]
    if provider == "openai-compatible":
        provider = "openai-chat"
    if provider == "openai-codex":
        raise ValueError(
            "This provider requires authentication settings not supported by Studio."
            " Configure its OpenAI-compatible endpoint instead."
        )

    def factory(name: str):
        if name.startswith("gateway/"):
            gateway = importlib.import_module("pydantic_ai.providers.gateway")
            return gateway.gateway_provider(
                name.removeprefix("gateway/"),
                api_key=config["api_key"],
                base_url=config.get("base_url") or None,
            )
        cls = providers.infer_provider_class(name)
        arguments = {}
        parameters = inspect.signature(cls).parameters
        if name == "azure":
            return cls(
                azure_endpoint=config["base_url"],
                api_key=config["api_key"],
                api_version="2024-10-21",
            )
        for key in ("api_key", "base_url"):
            if config.get(key):
                if key not in parameters:
                    raise ValueError("The provider does not accept " + key + ".")
                arguments[key] = config[key]
        return cls(**arguments)

    if provider == "gateway":
        provider = "gateway/" + config["model"].split(":", 1)[0]
        config = {**config, "model": config["model"].split(":", 1)[1]}
    return models.infer_model(
        provider + ":" + config["model"], provider_factory=factory
    )


async def main() -> None:
    request = json.loads(sys.stdin.readline())
    ai = importlib.import_module("pydantic_ai")
    messages = importlib.import_module("pydantic_ai.messages")
    usage = importlib.import_module("pydantic_ai.usage")
    agent = ai.Agent(
        configured_model(request["model"]),
        instructions=request["instructions"],
        tools=[
            ai.Tool(tool, sequential=True)
            for tool in (list_files, read_file, write_file, delete_file)
        ],
        model_settings={
            "parallel_tool_calls": False,
            "timeout": 60,
            "max_tokens": 8192,
        },
        retries=2,
    )
    history = messages.ModelMessagesTypeAdapter.validate_python(request["history"])
    # Sequential tool execution keeps the single stdin RPC channel unambiguous.
    async with agent.run_stream_events(
        request["prompt"],
        message_history=history,
        usage_limits=usage.UsageLimits(
            request_limit=30, tool_calls_limit=60, total_tokens_limit=200000
        ),
    ) as events:
        async for event in events:
            if isinstance(event, messages.PartStartEvent) and isinstance(
                event.part, messages.TextPart
            ):
                emit({"text": event.part.content})
            elif isinstance(event, messages.PartDeltaEvent) and isinstance(
                event.delta, messages.TextPartDelta
            ):
                emit({"text": event.delta.content_delta})
            elif isinstance(event, ai.AgentRunResultEvent):
                history = json.loads(event.result.all_messages_json())
                for message in history:
                    # Guides are loaded afresh every run, not replayed from history.
                    message.pop("instructions", None)
                emit({"history": history})


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        # Provider exception bodies/URLs can include credentials; never relay them.
        emit(
            {
                "error": (
                    "Agent request failed ("
                    + type(exc).__name__
                    + "). Check the selected provider, model and credentials."
                )
            }
        )
        sys.exit(1)
