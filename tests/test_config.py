from __future__ import annotations

from pathlib import Path

from app.config import load_settings


def test_load_settings_uses_example_config_and_env(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LLM_PROVIDER=echo\nLLM_MODEL=test-model\nLLM_API_KEY=\nWAKE_WORD=Hey Test\n"
        "DATA_DIR=" + str(tmp_path / "data") + "\n"
    )
    settings = load_settings(env_file=env_file)

    assert settings.llm.provider == "echo"
    assert settings.llm.model == "test-model"
    assert settings.wake_word == "Hey Test"
    assert settings.agent_name  # falls back to example config's "Jarvis"
    assert isinstance(settings.applications, dict)
    assert "chrome" in settings.applications


def test_settings_never_expose_missing_key_as_string(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_PROVIDER=echo\nLLM_API_KEY=\n")
    settings = load_settings(env_file=env_file)
    assert settings.llm.api_key is None
