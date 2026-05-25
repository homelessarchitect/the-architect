from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentDefinition:
    """Configuration for an agent operating within a workflow."""

    memory: bool = False
    experience_capture: list[str] = field(default_factory=list)
    description: str = ""

    def __post_init__(self) -> None:
        valid_capture_types = {"observation", "decision", "outcome", "pattern", "correction"}
        invalid = set(self.experience_capture) - valid_capture_types
        if invalid:
            raise ValueError(
                f"Invalid experience capture types: {invalid}. "
                f"Valid: {valid_capture_types}"
            )
