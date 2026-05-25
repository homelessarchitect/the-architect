from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DispatcherDefinition:
    """Maps an approval action type to a handler -- optionally via a provider."""

    action_type: str
    handler: str = ""  # dotpath to handler function
    provider: str = ""  # provider name (resolved at runtime)
    provider_action: str = ""  # method on the provider to call

    def __post_init__(self) -> None:
        if not self.action_type:
            raise ValueError("DispatcherDefinition requires action_type")
        has_handler = bool(self.handler)
        has_provider = bool(self.provider)
        if not has_handler and not has_provider:
            raise ValueError(
                f"Dispatcher '{self.action_type}' needs either handler (dotpath) "
                f"or provider+provider_action"
            )
        if has_provider and not self.provider_action:
            raise ValueError(
                f"Dispatcher '{self.action_type}' has provider but no provider_action"
            )
