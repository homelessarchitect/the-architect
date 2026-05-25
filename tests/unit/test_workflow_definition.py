import pytest

from factory.primitives import (
    AgentDefinition,
    DispatcherDefinition,
    EntityDefinition,
    FieldDef,
    PipelineDefinition,
    ToolDefinition,
    Transition,
    WorkflowDefinition,
)
from factory.providers.instagram import InstagramProvider


class TestWorkflowDefinition:
    def _minimal_workflow(self) -> WorkflowDefinition:
        lead = EntityDefinition(
            name="lead",
            fields=[FieldDef("name", str, required=True)],
        )
        return WorkflowDefinition(
            name="Test CRM",
            slug="crm",
            entities=[lead],
        )

    def test_basic_creation(self):
        wf = self._minimal_workflow()
        assert wf.name == "Test CRM"
        assert wf.slug == "crm"
        assert len(wf.entities) == 1

    def test_sets_slug_on_entities(self):
        wf = self._minimal_workflow()
        assert wf.entities[0].slug == "crm"
        assert wf.entities[0].table_name == "crm_leads"

    def test_invalid_slug_uppercase(self):
        with pytest.raises(ValueError, match="lowercase"):
            WorkflowDefinition(name="Bad", slug="MySlug", entities=[])

    def test_invalid_slug_too_short(self):
        with pytest.raises(ValueError, match="2-50"):
            WorkflowDefinition(name="Bad", slug="x", entities=[])

    def test_invalid_slug_too_long(self):
        with pytest.raises(ValueError, match="2-50"):
            WorkflowDefinition(name="Bad", slug="a" * 51, entities=[])

    def test_slug_with_hyphens(self):
        wf = WorkflowDefinition(name="Content Ops", slug="content-ops", entities=[])
        assert wf.slug == "content-ops"

    def test_duplicate_entities_raises(self):
        e1 = EntityDefinition(name="lead", fields=[FieldDef("name", str)])
        e2 = EntityDefinition(name="lead", fields=[FieldDef("email", str)])
        with pytest.raises(ValueError, match="Duplicate entity"):
            WorkflowDefinition(name="Bad", slug="crm", entities=[e1, e2])

    def test_with_tools(self):
        lead = EntityDefinition(name="lead", fields=[FieldDef("name", str)])
        wf = WorkflowDefinition(
            name="CRM",
            slug="crm",
            entities=[lead],
            tools=[
                ToolDefinition.crud("lead"),
                ToolDefinition.custom("my.module.enrich", description="Enrich lead data"),
            ],
        )
        assert len(wf.tools) == 2
        assert wf.tools[0].kind == "crud"
        assert wf.tools[1].kind == "custom"

    def test_with_pipeline(self):
        wf = WorkflowDefinition(
            name="CRM",
            slug="crm",
            entities=[EntityDefinition(name="lead", fields=[FieldDef("name", str)])],
            pipelines=[
                PipelineDefinition(
                    entity_name="lead",
                    statuses=["new", "contacted", "converted"],
                    transitions=[
                        Transition("new", "contacted"),
                        Transition(
                            "contacted",
                            "converted",
                            approval_required=True,
                            approval_action_type="convert_lead",
                        ),
                    ],
                )
            ],
        )
        assert len(wf.pipelines) == 1

    def test_with_dispatchers(self):
        wf = WorkflowDefinition(
            name="CRM",
            slug="crm",
            entities=[],
            dispatchers=[
                DispatcherDefinition(
                    action_type="send_email", handler="my.handlers.send_email"
                ),
                DispatcherDefinition(
                    action_type="publish", provider="instagram", provider_action="publish"
                ),
            ],
        )
        assert len(wf.dispatchers) == 2

    def test_with_agent(self):
        wf = WorkflowDefinition(
            name="CRM",
            slug="crm",
            entities=[],
            agent=AgentDefinition(
                memory=True,
                experience_capture=["decision", "outcome"],
            ),
        )
        assert wf.agent is not None
        assert wf.agent.memory is True

    def test_with_providers(self):
        wf = WorkflowDefinition(
            name="Content",
            slug="content",
            entities=[],
            providers=[InstagramProvider],
        )
        assert len(wf.providers) == 1


class TestToolDefinition:
    def test_crud(self):
        t = ToolDefinition.crud("lead")
        assert t.kind == "crud"
        assert t.entity_name == "lead"

    def test_custom(self):
        t = ToolDefinition.custom("my.module.func", description="Do thing")
        assert t.kind == "custom"
        assert t.dotpath == "my.module.func"

    def test_crud_requires_entity(self):
        with pytest.raises(ValueError, match="entity_name"):
            ToolDefinition(kind="crud")

    def test_custom_requires_dotpath(self):
        with pytest.raises(ValueError, match="dotpath"):
            ToolDefinition(kind="custom")

    def test_invalid_kind(self):
        with pytest.raises(ValueError, match="crud.*custom"):
            ToolDefinition(kind="magic", entity_name="x")


class TestPipelineDefinition:
    def test_basic(self):
        p = PipelineDefinition(
            entity_name="lead",
            statuses=["new", "contacted", "converted"],
        )
        assert p.initial_status == "new"

    def test_custom_initial(self):
        p = PipelineDefinition(
            entity_name="lead",
            statuses=["draft", "active", "done"],
            initial_status="draft",
        )
        assert p.initial_status == "draft"

    def test_invalid_initial(self):
        with pytest.raises(ValueError, match="not in statuses"):
            PipelineDefinition(
                entity_name="lead",
                statuses=["new", "done"],
                initial_status="invalid",
            )

    def test_empty_statuses(self):
        with pytest.raises(ValueError, match="at least one"):
            PipelineDefinition(entity_name="lead", statuses=[])

    def test_invalid_transition_from(self):
        with pytest.raises(ValueError, match="from_status"):
            PipelineDefinition(
                entity_name="lead",
                statuses=["new", "done"],
                transitions=[Transition("invalid", "done")],
            )

    def test_approval_without_action_type(self):
        with pytest.raises(ValueError, match="approval_action_type"):
            PipelineDefinition(
                entity_name="lead",
                statuses=["new", "done"],
                transitions=[Transition("new", "done", approval_required=True)],
            )

    def test_valid_approval_transition(self):
        p = PipelineDefinition(
            entity_name="lead",
            statuses=["new", "done"],
            transitions=[
                Transition(
                    "new", "done", approval_required=True, approval_action_type="finish_lead"
                ),
            ],
        )
        assert p.transitions[0].approval_required is True


class TestDispatcherDefinition:
    def test_with_handler(self):
        d = DispatcherDefinition(action_type="send_email", handler="my.mod.send")
        assert d.handler == "my.mod.send"

    def test_with_provider(self):
        d = DispatcherDefinition(
            action_type="publish", provider="instagram", provider_action="publish"
        )
        assert d.provider == "instagram"

    def test_requires_handler_or_provider(self):
        with pytest.raises(ValueError, match="handler.*provider"):
            DispatcherDefinition(action_type="noop")

    def test_provider_without_action_raises(self):
        with pytest.raises(ValueError, match="provider_action"):
            DispatcherDefinition(action_type="pub", provider="instagram")


class TestAgentDefinition:
    def test_basic(self):
        a = AgentDefinition(memory=True, experience_capture=["decision", "outcome"])
        assert a.memory is True

    def test_invalid_capture_type(self):
        with pytest.raises(ValueError, match="Invalid experience capture"):
            AgentDefinition(experience_capture=["invalid_type"])

    def test_valid_capture_types(self):
        a = AgentDefinition(
            experience_capture=["observation", "decision", "outcome", "pattern", "correction"]
        )
        assert len(a.experience_capture) == 5


class TestInstagramProvider:
    def test_name(self):
        p = InstagramProvider()
        assert p.name == "instagram"

    def test_config_fields(self):
        p = InstagramProvider()
        assert len(p.config_fields) == 2
        names = [f.name for f in p.config_fields]
        assert "access_token" in names
        assert "business_account_id" in names

    @pytest.mark.asyncio
    async def test_execute_publish_stub(self):
        p = InstagramProvider()
        result = await p.execute("publish", {"content": "Hello world"})
        assert result["status"] == "stub"
        assert result["action"] == "publish"

    @pytest.mark.asyncio
    async def test_execute_unknown_action(self):
        p = InstagramProvider()
        result = await p.execute("unknown", {})
        assert "error" in result

    def test_validate_config_missing(self):
        p = InstagramProvider()
        errors = p.validate_config({})
        assert len(errors) == 2

    def test_validate_config_complete(self):
        p = InstagramProvider()
        errors = p.validate_config({"access_token": "tok", "business_account_id": "123"})
        assert len(errors) == 0
