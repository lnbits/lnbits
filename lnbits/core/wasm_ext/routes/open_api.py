from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from loguru import logger

from ..wasm.config import WasmAPIRouteConfig
from ..wasm.loader import WasmExtension


@dataclass(frozen=True)
class WasmOpenAPIMetadata:
    summary: str
    description: str | None
    operation_id: str
    openapi_extra: dict[str, Any] | None


_MISSING_OPENAPI_EXAMPLE = object()


def wasm_extension_api_tag(extension: WasmExtension) -> str:
    return extension.name.strip() or extension.id


def wasm_extension_api_openapi_metadata(
    extension: WasmExtension,
    route_config: WasmAPIRouteConfig,
    method: str,
) -> WasmOpenAPIMetadata:
    operation = _load_wasm_extension_openapi_operation(
        extension,
        route_config,
    )
    summary = _openapi_string(operation.pop("summary", None)) or (
        f"{method} {route_config.path}"
    )
    description = _openapi_string(operation.pop("description", None))
    operation_id = (
        _openapi_string(operation.pop("operationId", None))
        or _openapi_string(operation.pop("operation_id", None))
        or _wasm_extension_default_operation_id(extension, route_config, method)
    )
    operation.pop("tags", None)
    _add_wasm_openapi_success_examples(operation)
    return WasmOpenAPIMetadata(
        summary=summary,
        description=description,
        operation_id=operation_id,
        openapi_extra=operation or None,
    )


def _load_wasm_extension_openapi_operation(
    extension: WasmExtension,
    route_config: WasmAPIRouteConfig,
) -> dict[str, Any]:
    try:
        openapi_refs = _wasm_extension_openapi_refs(extension, route_config)
    except Exception as exc:
        logger.warning(
            f"Ignoring OpenAPI metadata for WASM extension '{extension.id}' "
            f"route '{route_config.path}': {exc}"
        )
        return {}
    if not openapi_refs:
        return {}

    errors: list[Exception] = []
    for openapi_ref in openapi_refs:
        try:
            document_path, pointer = _wasm_openapi_ref_parts(openapi_ref)
            document = _load_wasm_openapi_document(extension, document_path)
            operation = _resolve_json_pointer(document, pointer)
            if not isinstance(operation, dict):
                raise TypeError("OpenAPI route fragment must resolve to an object.")
            return _inline_wasm_openapi_refs(deepcopy(operation), document)
        except Exception as exc:
            errors.append(exc)

    logger.warning(
        f"Ignoring OpenAPI metadata for WASM extension '{extension.id}' "
        f"route '{route_config.path}': {errors[-1]}"
    )
    return {}


def _wasm_extension_openapi_refs(
    extension: WasmExtension,
    route_config: WasmAPIRouteConfig,
) -> list[str]:
    if route_config.openapi:
        return [
            _wasm_openapi_resolved_ref(
                extension.config.openapi,
                route_config.openapi,
            )
        ]

    document_path = extension.config.openapi
    if not document_path:
        return []

    document_path = _wasm_openapi_document_path(document_path)
    route_keys = [route_config.export, _wasm_openapi_route_key(route_config.export)]
    return [
        f"{document_path}#/routes/{_json_pointer_token(route_key)}"
        for route_key in dict.fromkeys(route_keys)
    ]


def _wasm_openapi_resolved_ref(
    base_ref: str | None,
    route_ref: str,
) -> str:
    if not route_ref.startswith("#"):
        return route_ref
    if not base_ref:
        raise ValueError("OpenAPI metadata reference must include a JSON file path.")
    return f"{_wasm_openapi_document_path(base_ref)}{route_ref}"


def _wasm_openapi_document_path(openapi_ref: str) -> str:
    document_path, _, _ = openapi_ref.partition("#")
    if not document_path:
        raise ValueError("OpenAPI metadata reference must include a JSON file path.")
    return document_path


def _wasm_openapi_route_key(export_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", export_name).strip("_").lower()


def _json_pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _wasm_openapi_ref_parts(openapi_ref: str) -> tuple[str, str]:
    document_path, _, pointer = openapi_ref.partition("#")
    if not document_path:
        raise ValueError("OpenAPI metadata reference must include a JSON file path.")
    return document_path, pointer


def _load_wasm_openapi_document(
    extension: WasmExtension,
    document_path: str,
) -> dict[str, Any]:
    if "://" in document_path or document_path.startswith(("/", "\\")):
        raise ValueError("OpenAPI metadata reference must be a local relative path.")
    if not document_path.lower().endswith(".json"):
        raise ValueError("OpenAPI metadata reference must point to a JSON file.")

    extension_root = extension.root_path.resolve()
    path = (extension_root / document_path).resolve()
    if not path.is_relative_to(extension_root):
        raise ValueError("OpenAPI metadata reference escapes the extension root.")
    if not path.is_file():
        raise FileNotFoundError(f"OpenAPI metadata file not found: {document_path}")

    with path.open("r", encoding="utf-8") as openapi_file:
        document = json.load(openapi_file)
    if not isinstance(document, dict):
        raise TypeError("OpenAPI metadata file must contain a JSON object.")
    return document


def _resolve_json_pointer(document: Any, pointer: str) -> Any:
    if not pointer:
        return document
    if not pointer.startswith("/"):
        raise ValueError("OpenAPI metadata reference must use a JSON pointer.")

    value = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            value = value[token]
        elif isinstance(value, list):
            value = value[int(token)]
        else:
            raise KeyError(token)
    return value


def _inline_wasm_openapi_refs(
    value: Any,
    document: dict[str, Any],
    seen_refs: tuple[str, ...] = (),
) -> Any:
    if isinstance(value, list):
        return [_inline_wasm_openapi_refs(item, document, seen_refs) for item in value]
    if not isinstance(value, dict):
        return value

    ref = value.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/") and ref not in seen_refs:
        try:
            resolved = _inline_wasm_openapi_refs(
                deepcopy(_resolve_json_pointer(document, ref[1:])),
                document,
                (*seen_refs, ref),
            )
        except Exception:
            resolved = None

        if resolved is not None:
            overrides = {
                key: _inline_wasm_openapi_refs(item, document, seen_refs)
                for key, item in value.items()
                if key != "$ref"
            }
            if isinstance(resolved, dict):
                return {**resolved, **overrides}
            if not overrides:
                return resolved

    return {
        key: _inline_wasm_openapi_refs(item, document, seen_refs)
        for key, item in value.items()
    }


def _add_wasm_openapi_success_examples(operation: dict[str, Any]) -> None:
    responses = operation.get("responses")
    if not isinstance(responses, dict):
        return

    for response in responses.values():
        if not isinstance(response, dict):
            continue
        content = response.get("content")
        if not isinstance(content, dict):
            continue
        json_content = content.get("application/json")
        if not isinstance(json_content, dict):
            continue
        if "example" in json_content or "examples" in json_content:
            continue

        schema = json_content.get("schema")
        example = _wasm_openapi_success_example(schema)
        if example is not None:
            json_content["example"] = example


def _wasm_openapi_success_example(schema: Any) -> Any | None:
    if not isinstance(schema, dict):
        return None

    for keyword in ("oneOf", "anyOf"):
        variants = schema.get(keyword)
        if not isinstance(variants, list):
            continue
        for variant in variants:
            if _wasm_openapi_schema_has_ok_value(variant, True):
                return _wasm_openapi_schema_example(variant)
    return None


def _wasm_openapi_schema_has_ok_value(schema: Any, ok_value: bool) -> bool:
    if not isinstance(schema, dict):
        return False
    properties = schema.get("properties")
    if isinstance(properties, dict):
        ok_schema = properties.get("ok")
        if isinstance(ok_schema, dict):
            enum = ok_schema.get("enum")
            return isinstance(enum, list) and ok_value in enum
    all_of = schema.get("allOf")
    return isinstance(all_of, list) and any(
        _wasm_openapi_schema_has_ok_value(item, ok_value) for item in all_of
    )


def _wasm_openapi_schema_example(schema: Any) -> Any:
    if not isinstance(schema, dict):
        return None

    explicit_example = _wasm_openapi_explicit_schema_example(schema)
    if explicit_example is not _MISSING_OPENAPI_EXAMPLE:
        return explicit_example

    composed_example = _wasm_openapi_composed_schema_example(schema)
    if composed_example is not _MISSING_OPENAPI_EXAMPLE:
        return composed_example

    return _wasm_openapi_type_schema_example(schema)


def _wasm_openapi_explicit_schema_example(schema: dict[str, Any]) -> Any:
    if "example" in schema:
        return schema["example"]
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    return _MISSING_OPENAPI_EXAMPLE


def _wasm_openapi_composed_schema_example(schema: dict[str, Any]) -> Any:
    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        example: dict[str, Any] = {}
        for item in all_of:
            item_example = _wasm_openapi_schema_example(item)
            if isinstance(item_example, dict):
                example.update(item_example)
        return example

    for keyword in ("oneOf", "anyOf"):
        variants = schema.get(keyword)
        if isinstance(variants, list) and variants:
            return _wasm_openapi_schema_example(variants[0])
    return _MISSING_OPENAPI_EXAMPLE


def _wasm_openapi_type_schema_example(schema: dict[str, Any]) -> Any:
    schema_type = schema.get("type")
    if schema_type == "object" or isinstance(schema.get("properties"), dict):
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            return {}
        return {
            name: _wasm_openapi_schema_example(property_schema)
            for name, property_schema in properties.items()
        }
    if schema_type == "array":
        return [_wasm_openapi_schema_example(schema.get("items"))]
    if schema_type == "integer":
        return 0
    if schema_type == "number":
        return 0
    if schema_type == "boolean":
        return True
    return "string"


def _openapi_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _wasm_extension_default_operation_id(
    extension: WasmExtension,
    route_config: WasmAPIRouteConfig,
    method: str,
) -> str:
    value = f"{extension.id}_{method}_{route_config.path}"
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return value or f"{extension.id}_{method.lower()}"
