from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from architect.primitives.entity import FieldDef


class Provider(ABC):
    """Abstract base for integration providers (Instagram, Resend, etc.)."""

    name: ClassVar[str] = ""
    config_fields: ClassVar[list[FieldDef]] = []

    @abstractmethod
    async def execute(
        self, action: str, payload: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]: ...

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        errors = []
        for f in self.config_fields:
            if f.required and f.name not in config:
                errors.append(f"Missing required config field: {f.name}")
        return errors
