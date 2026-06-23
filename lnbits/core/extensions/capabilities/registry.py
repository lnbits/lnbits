from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


@dataclass(frozen=True)
class CapabilityDefinition:
    id: str
    namespace: str
    name: str
    host_name: str
    sdk_name: str
    description: str
    request_model: type[BaseModel]
    response_model: type[BaseModel]
    required_permission: str | None = None
    public_context: bool = False

    @property
    def sdk_qualified_name(self) -> str:
        return f"{self.namespace}.{self.sdk_name}"

    def request_schema(self) -> dict[str, Any]:
        return self.request_model.schema(ref_template="#/definitions/{model}")

    def response_schema(self) -> dict[str, Any]:
        return self.response_model.schema(ref_template="#/definitions/{model}")

    def to_codegen_contract(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "namespace": self.namespace,
            "name": self.name,
            "host_name": self.host_name,
            "sdk_name": self.sdk_name,
            "sdk_qualified_name": self.sdk_qualified_name,
            "description": self.description,
            "required_permission": self.required_permission,
            "public_context": self.public_context,
            "request_schema": self.request_schema(),
            "response_schema": self.response_schema(),
        }


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilityDefinition] = {}

    def register(self, capability: CapabilityDefinition) -> None:
        if capability.id in self._capabilities:
            raise ValueError(f"Capability '{capability.id}' already registered.")
        self._capabilities[capability.id] = capability

    def get(self, capability_id: str) -> CapabilityDefinition | None:
        return self._capabilities.get(capability_id)

    def require(self, capability_id: str) -> CapabilityDefinition:
        capability = self.get(capability_id)
        if not capability:
            raise KeyError(f"Unknown capability '{capability_id}'.")
        return capability

    def all(self) -> list[CapabilityDefinition]:
        return sorted(self._capabilities.values(), key=lambda c: c.id)

    def by_permission(self, permission_id: str) -> list[CapabilityDefinition]:
        return [c for c in self.all() if c.required_permission == permission_id]

    def to_codegen_contract(self) -> dict[str, Any]:
        return {
            "version": 1,
            "capabilities": [c.to_codegen_contract() for c in self.all()],
        }
