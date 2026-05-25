from __future__ import annotations

from dataclasses import dataclass

from architect.primitives.pipeline import PipelineDefinition, Transition


@dataclass
class TransitionResult:
    allowed: bool
    approval_required: bool = False
    approval_action_type: str = ""
    error: str = ""
    allowed_transitions: list[str] | None = None


class PipelineEngine:
    """Enforces status transitions and approval gates for entities."""

    def __init__(self, pipelines: list[PipelineDefinition]) -> None:
        self._pipelines: dict[str, PipelineDefinition] = {
            p.entity_name: p for p in pipelines
        }

    def get_pipeline(self, entity_name: str) -> PipelineDefinition | None:
        return self._pipelines.get(entity_name)

    def get_initial_status(self, entity_name: str) -> str | None:
        pipeline = self.get_pipeline(entity_name)
        if pipeline is None:
            return None
        return pipeline.initial_status

    def validate_transition(
        self, entity_name: str, from_status: str, to_status: str
    ) -> TransitionResult:
        pipeline = self.get_pipeline(entity_name)
        if pipeline is None:
            return TransitionResult(allowed=True)

        if from_status not in pipeline.statuses:
            return TransitionResult(
                allowed=False,
                error=f"Current status '{from_status}' is not valid for entity '{entity_name}'",
            )

        if to_status not in pipeline.statuses:
            return TransitionResult(
                allowed=False,
                error=f"Target status '{to_status}' is not valid for entity '{entity_name}'",
            )

        allowed_targets: list[str] = []
        matching_transition: Transition | None = None

        for t in pipeline.transitions:
            if t.from_status == from_status:
                allowed_targets.append(t.to_status)
                if t.to_status == to_status:
                    matching_transition = t

        if matching_transition is None:
            if not allowed_targets:
                return TransitionResult(
                    allowed=False,
                    error=f"No transitions defined from '{from_status}'",
                    allowed_transitions=[],
                )
            return TransitionResult(
                allowed=False,
                error=f"Cannot transition from '{from_status}' to '{to_status}'",
                allowed_transitions=allowed_targets,
            )

        if matching_transition.approval_required:
            return TransitionResult(
                allowed=True,
                approval_required=True,
                approval_action_type=matching_transition.approval_action_type,
            )

        return TransitionResult(allowed=True)

    def list_entities(self) -> list[str]:
        return list(self._pipelines.keys())
