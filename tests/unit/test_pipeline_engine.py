import pytest

from factory.primitives import PipelineDefinition, Transition
from factory.runtime.pipeline_engine import PipelineEngine


@pytest.fixture
def lead_pipeline() -> PipelineDefinition:
    return PipelineDefinition(
        entity_name="lead",
        statuses=["new", "contacted", "qualified", "converted", "rejected"],
        transitions=[
            Transition("new", "contacted"),
            Transition("contacted", "qualified"),
            Transition(
                "qualified",
                "converted",
                approval_required=True,
                approval_action_type="convert_lead",
            ),
            Transition("qualified", "rejected"),
            Transition("new", "rejected"),
        ],
    )


@pytest.fixture
def engine(lead_pipeline: PipelineDefinition) -> PipelineEngine:
    return PipelineEngine([lead_pipeline])


class TestPipelineEngine:
    def test_get_pipeline(self, engine: PipelineEngine) -> None:
        p = engine.get_pipeline("lead")
        assert p is not None
        assert p.entity_name == "lead"

    def test_get_pipeline_missing(self, engine: PipelineEngine) -> None:
        assert engine.get_pipeline("nonexistent") is None

    def test_get_initial_status(self, engine: PipelineEngine) -> None:
        assert engine.get_initial_status("lead") == "new"

    def test_get_initial_status_missing(self, engine: PipelineEngine) -> None:
        assert engine.get_initial_status("nonexistent") is None

    def test_valid_transition(self, engine: PipelineEngine) -> None:
        result = engine.validate_transition("lead", "new", "contacted")
        assert result.allowed is True
        assert result.approval_required is False

    def test_invalid_transition(self, engine: PipelineEngine) -> None:
        result = engine.validate_transition("lead", "new", "converted")
        assert result.allowed is False
        assert "contacted" in (result.allowed_transitions or [])

    def test_transition_with_approval(self, engine: PipelineEngine) -> None:
        result = engine.validate_transition("lead", "qualified", "converted")
        assert result.allowed is True
        assert result.approval_required is True
        assert result.approval_action_type == "convert_lead"

    def test_invalid_from_status(self, engine: PipelineEngine) -> None:
        result = engine.validate_transition("lead", "nonexistent", "contacted")
        assert result.allowed is False

    def test_invalid_to_status(self, engine: PipelineEngine) -> None:
        result = engine.validate_transition("lead", "new", "nonexistent")
        assert result.allowed is False

    def test_no_transitions_from_status(self, engine: PipelineEngine) -> None:
        result = engine.validate_transition("lead", "converted", "new")
        assert result.allowed is False
        assert result.allowed_transitions == []

    def test_entity_without_pipeline_allows_all(self, engine: PipelineEngine) -> None:
        result = engine.validate_transition("unknown_entity", "any", "thing")
        assert result.allowed is True

    def test_multiple_allowed_targets(self, engine: PipelineEngine) -> None:
        result = engine.validate_transition("lead", "qualified", "rejected")
        assert result.allowed is True

    def test_list_entities(self, engine: PipelineEngine) -> None:
        assert engine.list_entities() == ["lead"]

    def test_empty_engine(self) -> None:
        engine = PipelineEngine([])
        assert engine.list_entities() == []
        result = engine.validate_transition("anything", "a", "b")
        assert result.allowed is True

    def test_multiple_pipelines(self, lead_pipeline: PipelineDefinition) -> None:
        piece_pipeline = PipelineDefinition(
            entity_name="piece",
            statuses=["draft", "review", "published"],
            transitions=[
                Transition("draft", "review"),
                Transition("review", "published"),
            ],
        )
        engine = PipelineEngine([lead_pipeline, piece_pipeline])
        assert len(engine.list_entities()) == 2

        r1 = engine.validate_transition("lead", "new", "contacted")
        assert r1.allowed is True

        r2 = engine.validate_transition("piece", "draft", "review")
        assert r2.allowed is True

        r3 = engine.validate_transition("piece", "draft", "published")
        assert r3.allowed is False
