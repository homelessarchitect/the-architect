from __future__ import annotations

from factory.primitives.provider import Provider


class ProviderRegistry:
    """Registry of instantiated providers, keyed by name."""

    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}

    def register(self, provider: Provider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> Provider:
        if name not in self._providers:
            available = ", ".join(self._providers.keys()) or "(none)"
            raise KeyError(
                f"Provider '{name}' not found. Available: {available}"
            )
        return self._providers[name]

    def list(self) -> list[str]:
        return list(self._providers.keys())

    @classmethod
    def from_workflow(cls, provider_classes: list[type]) -> ProviderRegistry:
        registry = cls()
        for provider_cls in provider_classes:
            instance = provider_cls()
            registry.register(instance)
        return registry
