from __future__ import annotations

import pytest

from app.security.permissions import PermissionLevel
from app.tools.base import Tool, ToolResult
from app.tools.registry import ToolRegistry


class DummyTool(Tool):
    name = "dummy"
    description = "A dummy tool for testing."
    permission_level = PermissionLevel.LOW
    parameters = []

    async def execute(self, arguments):
        return ToolResult.ok(message="dummy ran")


def test_register_and_get():
    registry = ToolRegistry()
    tool = DummyTool()
    registry.register(tool)
    assert registry.get("dummy") is tool
    assert "dummy" in registry
    assert len(registry) == 1


def test_register_duplicate_raises():
    registry = ToolRegistry()
    registry.register(DummyTool())
    with pytest.raises(ValueError):
        registry.register(DummyTool())


def test_require_missing_raises_keyerror():
    registry = ToolRegistry()
    with pytest.raises(KeyError):
        registry.require("does_not_exist")


def test_schemas_shape():
    registry = ToolRegistry()
    registry.register(DummyTool())
    schemas = registry.schemas()
    assert len(schemas) == 1
    assert schemas[0]["name"] == "dummy"
    assert "input_schema" in schemas[0]
