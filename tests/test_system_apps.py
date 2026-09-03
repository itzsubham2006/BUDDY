from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from app.tools.applications import OpenApplicationTool, _resolve_executable


def test_resolve_system_apps():
    # Test resolving Windows system utilities and URI schemes
    assert _resolve_executable("settings", {}) == "ms-settings:"
    assert "taskmgr" in _resolve_executable("task manager", {}).lower()
    assert "control" in _resolve_executable("control panel", {}).lower()
    assert "mspaint" in _resolve_executable("paint", {}).lower()
    assert "calc" in _resolve_executable("calculator", {}).lower()
    assert _resolve_executable("camera", {}) == "microsoft.windows.camera:"


@pytest.mark.asyncio
async def test_open_system_app_simulated():
    tool = OpenApplicationTool()

    with patch("os.startfile", MagicMock()) as mock_startfile, patch("subprocess.Popen", MagicMock()) as mock_popen:
        # Test settings (URI scheme)
        result = await tool.execute({"application": "settings"})
        assert result.success is True
        assert result.data.get("executable") == "ms-settings:"
        mock_startfile.assert_called_with("ms-settings:")

        # Test task manager
        result = await tool.execute({"application": "task manager"})
        assert result.success is True
        assert "taskmgr" in result.data.get("executable", "").lower()


def test_open_application_accepts_any_name():
    tool = OpenApplicationTool()
    # Should not raise validation error on custom application name
    error = tool.validate_arguments({"application": "custom_game_or_app"})
    assert error is None
