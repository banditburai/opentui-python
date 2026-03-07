"""Tests for configuration loading."""

import os
from pathlib import Path

from opencode.config import AppConfig, load_config


class TestAppConfig:
    def test_defaults(self):
        cfg = AppConfig()
        assert cfg.model == "gpt-4o"
        assert cfg.api_key == ""
        assert cfg.api_base_url == ""
        assert cfg.theme == {}
        assert cfg.mcp_servers == {}

    def test_fields_settable(self):
        cfg = AppConfig(model="claude-3-opus", api_key="sk-test")
        assert cfg.model == "claude-3-opus"
        assert cfg.api_key == "sk-test"


class TestLoadConfig:
    def test_no_file_returns_defaults(self, tmp_path):
        cfg = load_config(config_dir=tmp_path)
        assert cfg.model == "gpt-4o"

    def test_reads_toml(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[opencode]\nmodel = "claude-3-opus"\napi_key = "sk-abc"\n'
        )
        cfg = load_config(config_dir=tmp_path)
        assert cfg.model == "claude-3-opus"
        assert cfg.api_key == "sk-abc"

    def test_env_var_overrides_file(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.toml"
        config_file.write_text('[opencode]\nmodel = "from-file"\n')
        monkeypatch.setenv("OPENCODE_MODEL", "from-env")
        cfg = load_config(config_dir=tmp_path)
        assert cfg.model == "from-env"

    def test_env_api_key(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENCODE_API_KEY", "sk-env")
        cfg = load_config(config_dir=tmp_path)
        assert cfg.api_key == "sk-env"

    def test_env_api_base_url(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENCODE_API_BASE_URL", "https://my.api")
        cfg = load_config(config_dir=tmp_path)
        assert cfg.api_base_url == "https://my.api"

    def test_mcp_servers(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[opencode.mcp_servers.myserver]\n'
            'command = "server"\n'
            'args = ["--port", "8080"]\n'
        )
        cfg = load_config(config_dir=tmp_path)
        assert "myserver" in cfg.mcp_servers
        assert cfg.mcp_servers["myserver"]["command"] == "server"

    def test_theme_overrides(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[opencode.theme]\nbg = "#000000"\n'
        )
        cfg = load_config(config_dir=tmp_path)
        assert cfg.theme["bg"] == "#000000"

    def test_malformed_toml_returns_defaults(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("this is not valid toml [[[")
        cfg = load_config(config_dir=tmp_path)
        assert cfg.model == "gpt-4o"  # falls back to defaults
