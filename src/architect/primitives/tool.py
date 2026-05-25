from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolDefinition:
    """Defines an MCP tool -- either auto-generated CRUD or custom imported."""

    kind: str  # "crud" or "custom"
    entity_name: str = ""
    dotpath: str = ""
    description: str = ""

    @classmethod
    def crud(cls, entity_name: str) -> ToolDefinition:
        return cls(kind="crud", entity_name=entity_name)

    @classmethod
    def custom(cls, dotpath: str, description: str = "") -> ToolDefinition:
        return cls(kind="custom", dotpath=dotpath, description=description)

    def __post_init__(self) -> None:
        if self.kind == "crud" and not self.entity_name:
            raise ValueError("CRUD tool requires entity_name")
        if self.kind == "custom" and not self.dotpath:
            raise ValueError("Custom tool requires dotpath")
        if self.kind not in ("crud", "custom"):
            raise ValueError(f"Tool kind must be 'crud' or 'custom', got '{self.kind}'")
