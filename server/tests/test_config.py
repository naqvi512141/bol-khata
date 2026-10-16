"""Tests for server/app/config.py.

Contract:
- app/config.py resolves .env deterministically based on the file's absolute path:
  Path(__file__).resolve().parents[2] / ".env"
- Settings load properly regardless of working directory.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.config import Settings, _ENV_FILE, get_settings


def test_deterministic_env_file_path() -> None:
    """Verify _ENV_FILE is anchored to repository root via parents[2]."""
    expected = Path(__file__).resolve().parents[2] / ".env"
    assert _ENV_FILE == expected


def test_settings_load_regardless_of_cwd(tmp_path: Path) -> None:
    """Verify Settings loads properly even when the current working directory is elsewhere."""
    original_cwd = os.getcwd()
    try:
        # Change working directory to an arbitrary temporary directory
        os.chdir(tmp_path)
        assert os.getcwd() == str(tmp_path)

        # Instantiate Settings from the new working directory
        settings = Settings()

        # It should still resolve the same .env file from the repo root
        assert settings.model_config.get("env_file") == _ENV_FILE

        # If repo .env exists, verify that values match
        if _ENV_FILE.exists():
            # Should have loaded settings without errors
            assert settings.SHOP_ID == "demo_shop_01"
            assert isinstance(settings.GROQ_API_KEY, str)
    finally:
        os.chdir(original_cwd)


def test_get_settings_function() -> None:
    """Verify get_settings returns a valid Settings instance."""
    settings = get_settings()
    assert isinstance(settings, Settings)
    assert settings.SHOP_ID == "demo_shop_01"
