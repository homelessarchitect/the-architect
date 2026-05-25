from __future__ import annotations

import importlib
from typing import Any

from architect.primitives.dispatcher import DispatcherDefinition
from architect.runtime.provider_registry import ProviderRegistry


class Dispatcher:
    """Resolves and executes approved actions via handlers or providers."""

    def __init__(
        self,
        definitions: list[DispatcherDefinition],
        provider_registry: ProviderRegistry | None = None,
    ) -> None:
        self._definitions = {d.action_type: d for d in definitions}
        self._provider_registry = provider_registry

    async def execute(
        self, action_type: str, payload: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        if action_type not in self._definitions:
            available = ", ".join(self._definitions.keys()) or "(none)"
            raise ValueError(
                f"No dispatcher for action_type '{action_type}'. Available: {available}"
            )

        defn = self._definitions[action_type]

        if defn.provider:
            if self._provider_registry is None:
                raise RuntimeError(
                    f"Dispatcher '{action_type}' requires provider '{defn.provider}' "
                    f"but no provider registry was configured"
                )
            provider = self._provider_registry.get(defn.provider)
            return await provider.execute(defn.provider_action, payload, **kwargs)

        if defn.handler:
            module_path, func_name = defn.handler.rsplit(".", 1)
            module = importlib.import_module(module_path)
            handler_fn = getattr(module, func_name)
            return await handler_fn(payload, **kwargs)

        raise RuntimeError(f"Dispatcher '{action_type}' has no handler or provider")

    def list_action_types(self) -> list[str]:
        return list(self._definitions.keys())
