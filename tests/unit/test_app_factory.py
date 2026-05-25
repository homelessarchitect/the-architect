from typing import Any

from architect.runtime.app import create_app


class TestAppFactory:
    def test_creates_app(self):
        app = create_app()
        assert app is not None
        assert app.title == "The Architect"

    def test_health_endpoint_exists(self):
        app = create_app()
        routes = [r.path for r in app.routes]
        assert "/health" in routes

    def test_app_with_no_workflows(self):
        app = create_app(workflow_modules=[])
        routes = [r.path for r in app.routes]
        assert "/health" in routes

    def test_app_with_workflow_module(self):
        def mock_register(mcp: Any) -> None:
            @mcp.tool()
            async def hello() -> str:
                """Say hello."""
                return "hello"

        app = create_app(
            workflow_modules=[{"slug": "test", "register_fn": mock_register}]
        )
        # Check that the MCP sub-app was mounted
        assert any("/mcp/test" in str(r.path) for r in app.routes)

    def test_app_with_multiple_workflows(self):
        def reg1(mcp: Any) -> None:
            pass

        def reg2(mcp: Any) -> None:
            pass

        app = create_app(
            workflow_modules=[
                {"slug": "crm", "register_fn": reg1},
                {"slug": "content", "register_fn": reg2},
            ]
        )
        assert app is not None
