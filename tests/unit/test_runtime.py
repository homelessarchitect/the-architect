import pytest
from typing import Any

from architect.runtime.provider_registry import ProviderRegistry
from architect.runtime.dispatcher import Dispatcher
from architect.primitives import DispatcherDefinition, Provider, FieldDef
from architect.providers.instagram import InstagramProvider


class MockProvider(Provider):
    name = "mock"
    config_fields = []

    async def execute(self, action: str, payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return {"provider": self.name, "action": action, "payload": payload}


class TestProviderRegistry:
    def test_register_and_get(self):
        registry = ProviderRegistry()
        provider = MockProvider()
        registry.register(provider)
        assert registry.get("mock") is provider

    def test_get_missing_raises(self):
        registry = ProviderRegistry()
        with pytest.raises(KeyError, match="not found"):
            registry.get("missing")

    def test_list(self):
        registry = ProviderRegistry()
        registry.register(MockProvider())
        registry.register(InstagramProvider())
        assert set(registry.list()) == {"mock", "instagram"}

    def test_from_workflow(self):
        registry = ProviderRegistry.from_workflow([MockProvider, InstagramProvider])
        assert "mock" in registry.list()
        assert "instagram" in registry.list()

    def test_empty_registry_list(self):
        registry = ProviderRegistry()
        assert registry.list() == []


class TestDispatcher:
    async def test_execute_via_provider(self):
        registry = ProviderRegistry()
        registry.register(MockProvider())
        dispatcher = Dispatcher(
            definitions=[
                DispatcherDefinition(
                    action_type="test_action",
                    provider="mock",
                    provider_action="do_thing",
                )
            ],
            provider_registry=registry,
        )
        result = await dispatcher.execute("test_action", {"key": "value"})
        assert result["provider"] == "mock"
        assert result["action"] == "do_thing"

    async def test_execute_unknown_action_raises(self):
        dispatcher = Dispatcher(definitions=[])
        with pytest.raises(ValueError, match="No dispatcher"):
            await dispatcher.execute("nonexistent", {})

    async def test_execute_provider_not_configured_raises(self):
        dispatcher = Dispatcher(
            definitions=[
                DispatcherDefinition(
                    action_type="pub",
                    provider="instagram",
                    provider_action="publish",
                )
            ],
            provider_registry=None,
        )
        with pytest.raises(RuntimeError, match="no provider registry"):
            await dispatcher.execute("pub", {})

    async def test_execute_provider_not_found_raises(self):
        registry = ProviderRegistry()
        dispatcher = Dispatcher(
            definitions=[
                DispatcherDefinition(
                    action_type="pub",
                    provider="missing_provider",
                    provider_action="publish",
                )
            ],
            provider_registry=registry,
        )
        with pytest.raises(KeyError, match="not found"):
            await dispatcher.execute("pub", {})

    async def test_execute_via_instagram_stub(self):
        registry = ProviderRegistry.from_workflow([InstagramProvider])
        dispatcher = Dispatcher(
            definitions=[
                DispatcherDefinition(
                    action_type="publish_piece",
                    provider="instagram",
                    provider_action="publish",
                )
            ],
            provider_registry=registry,
        )
        result = await dispatcher.execute("publish_piece", {"content": "Hello!"})
        assert result["status"] == "stub"
        assert result["action"] == "publish"

    def test_list_action_types(self):
        dispatcher = Dispatcher(
            definitions=[
                DispatcherDefinition(action_type="send_email", handler="my.mod.send"),
                DispatcherDefinition(action_type="pub", provider="ig", provider_action="publish"),
            ]
        )
        assert set(dispatcher.list_action_types()) == {"send_email", "pub"}

    def test_empty_dispatcher(self):
        dispatcher = Dispatcher(definitions=[])
        assert dispatcher.list_action_types() == []
