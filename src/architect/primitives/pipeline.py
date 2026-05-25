from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Transition:
    """A state transition, optionally gated by an approval."""

    from_status: str
    to_status: str
    approval_required: bool = False
    approval_action_type: str = ""


@dataclass
class PipelineDefinition:
    """Defines status transitions and approval gates for an entity."""

    entity_name: str
    statuses: list[str]
    transitions: list[Transition] = field(default_factory=list)
    initial_status: str = ""

    def __post_init__(self) -> None:
        if not self.statuses:
            raise ValueError(f"Pipeline for '{self.entity_name}' must have at least one status")
        if not self.initial_status:
            self.initial_status = self.statuses[0]
        if self.initial_status not in self.statuses:
            raise ValueError(
                f"Initial status '{self.initial_status}' not in statuses: {self.statuses}"
            )
        for t in self.transitions:
            if t.from_status not in self.statuses:
                raise ValueError(
                    f"Transition from_status '{t.from_status}' not in statuses"
                )
            if t.to_status not in self.statuses:
                raise ValueError(
                    f"Transition to_status '{t.to_status}' not in statuses"
                )
            if t.approval_required and not t.approval_action_type:
                raise ValueError(
                    f"Transition {t.from_status} -> {t.to_status} requires approval "
                    f"but no approval_action_type specified"
                )
