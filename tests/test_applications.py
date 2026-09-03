from __future__ import annotations

import pytest

from app.config import ApplicationEntry
from app.tools.applications import OpenApplicationTool


@pytest.mark.asyncio
async def test_open_application_not_found_returns_failure():
    tool = OpenApplicationTool(applications={})
    result = await tool.execute({"application": "totally_fake_app_xyz"})
    assert result.success is False
    assert result.error == "application_not_found"


@pytest.mark.asyncio
async def test_open_application_resolves_absolute_path(tmp_path):
    from unittest.mock import patch

    fake_exe = tmp_path / "fake_chrome.exe"
    fake_exe.write_text("not a real binary")

    apps = {
        "chrome": ApplicationEntry(
            key="chrome", display_name="Google Chrome", executable=str(fake_exe)
        )
    }
    tool = OpenApplicationTool(applications=apps)
    with patch("subprocess.Popen"):
        result = await tool.execute({"application": "chrome"})

    assert result.success is True
    assert result.data.get("executable") == str(fake_exe)


def test_validate_arguments_requires_application_key():
    tool = OpenApplicationTool(applications={})
    error = tool.validate_arguments({})
    assert error is not None
    assert "application" in error
