"""Tests for JSON configuration loading."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from opencode.config import AppConfig, ProviderConfig, ProviderOptions, _resolve_value, load_config


class TestAppConfig:
    def test_defaults(self):
        cfg = AppConfig()
        assert cfg.model == ""
        assert cfg.small_model == ""
        assert cfg.provider == {}
        assert cfg.agent == {}
        assert cfg.theme == "opencode"
        assert cfg.theme_mode == "dark"
        assert cfg.mcp == {}
        assert cfg.disabled_providers == []
        assert cfg.enabled_providers == []

    def test_fields_settable(self):
        cfg = AppConfig(
            model="anthropic/claude-sonnet-4-0",
            small_model="anthropic/claude-haiku-3-5",
        )
        assert cfg.model == "anthropic/claude-sonnet-4-0"
        assert cfg.small_model == "anthropic/claude-haiku-3-5"


class TestResolveValue:
    def test_literal_passthrough(self):
        assert _resolve_value("hello") == "hello"

    def test_env_substitution(self, monkeypatch):
        monkeypatch.setenv("TEST_SECRET", "my-secret")
        assert _resolve_value("{env:TEST_SECRET}") == "my-secret"

    def test_env_missing_returns_empty(self, monkeypatch):
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)
        assert _resolve_value("{env:NONEXISTENT_VAR}") == ""

    def test_file_substitution(self, tmp_path):
        secret_file = tmp_path / "key.txt"
        secret_file.write_text("  sk-secret-123  \n")
        assert _resolve_value(f"{{file:{secret_file}}}") == "sk-secret-123"

    def test_file_missing_returns_empty(self, tmp_path):
        result = _resolve_value(f"{{file:{tmp_path / 'missing.txt'}}}")
        assert result == ""

    def test_non_string_passthrough(self):
        assert _resolve_value(42) == 42  # type: ignore[arg-type]


class TestLoadConfig:
    def test_no_file_returns_defaults(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        monkeypatch.delenv("OPENCODE_CONFIG_CONTENT", raising=False)
        monkeypatch.delenv("OPENCODE_MODEL", raising=False)
        cfg = load_config()
        assert cfg.model == ""

    def test_reads_json_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        monkeypatch.delenv("OPENCODE_CONFIG_CONTENT", raising=False)
        monkeypatch.delenv("OPENCODE_MODEL", raising=False)
        config_file = tmp_path / "opencode.json"
        config_file.write_text(json.dumps({
            "model": "minimax/MiniMax-M2.1",
            "smallModel": "minimax/MiniMax-M2.5",
        }))
        cfg = load_config()
        assert cfg.model == "minimax/MiniMax-M2.1"
        assert cfg.small_model == "minimax/MiniMax-M2.5"

    def test_reads_dotdir_json(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        monkeypatch.delenv("OPENCODE_CONFIG_CONTENT", raising=False)
        monkeypatch.delenv("OPENCODE_MODEL", raising=False)
        dotdir = tmp_path / ".opencode"
        dotdir.mkdir()
        config_file = dotdir / "opencode.json"
        config_file.write_text(json.dumps({"model": "openai/gpt-5"}))
        cfg = load_config()
        assert cfg.model == "openai/gpt-5"

    def test_opencode_config_env_path(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPENCODE_CONFIG_CONTENT", raising=False)
        monkeypatch.delenv("OPENCODE_MODEL", raising=False)
        config_file = tmp_path / "custom-config.json"
        config_file.write_text(json.dumps({"model": "deepseek/deepseek-chat"}))
        monkeypatch.setenv("OPENCODE_CONFIG", str(config_file))
        # chdir somewhere with no opencode.json
        monkeypatch.chdir(tmp_path / "subdir" if (tmp_path / "subdir").exists() else tmp_path)
        cfg = load_config()
        assert cfg.model == "deepseek/deepseek-chat"

    def test_opencode_config_content_env(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        monkeypatch.delenv("OPENCODE_MODEL", raising=False)
        inline = json.dumps({"model": "groq/llama-3.3-70b-versatile"})
        monkeypatch.setenv("OPENCODE_CONFIG_CONTENT", inline)
        cfg = load_config()
        assert cfg.model == "groq/llama-3.3-70b-versatile"

    def test_env_model_override(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        monkeypatch.delenv("OPENCODE_CONFIG_CONTENT", raising=False)
        config_file = tmp_path / "opencode.json"
        config_file.write_text(json.dumps({"model": "from-file"}))
        monkeypatch.setenv("OPENCODE_MODEL", "from-env")
        cfg = load_config()
        assert cfg.model == "from-env"

    def test_per_provider_options(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        monkeypatch.delenv("OPENCODE_CONFIG_CONTENT", raising=False)
        monkeypatch.delenv("OPENCODE_MODEL", raising=False)
        config_file = tmp_path / "opencode.json"
        config_file.write_text(json.dumps({
            "model": "minimax/MiniMax-M2.1",
            "provider": {
                "minimax": {
                    "options": {
                        "apiKey": "test-key-123",
                        "baseUrl": "https://custom.api/v1",
                    }
                }
            },
        }))
        cfg = load_config()
        assert "minimax" in cfg.provider
        assert cfg.provider["minimax"].options.api_key == "test-key-123"
        assert cfg.provider["minimax"].options.base_url == "https://custom.api/v1"

    def test_agent_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        monkeypatch.delenv("OPENCODE_CONFIG_CONTENT", raising=False)
        monkeypatch.delenv("OPENCODE_MODEL", raising=False)
        config_file = tmp_path / "opencode.json"
        config_file.write_text(json.dumps({
            "agent": {
                "title": {
                    "model": "openai/gpt-4.1-mini",
                    "temperature": 0.3,
                }
            },
        }))
        cfg = load_config()
        assert "title" in cfg.agent
        assert cfg.agent["title"].model == "openai/gpt-4.1-mini"
        assert cfg.agent["title"].temperature == 0.3

    def test_disabled_providers(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        monkeypatch.delenv("OPENCODE_CONFIG_CONTENT", raising=False)
        monkeypatch.delenv("OPENCODE_MODEL", raising=False)
        config_file = tmp_path / "opencode.json"
        config_file.write_text(json.dumps({
            "disabledProviders": ["ollama", "groq"],
        }))
        cfg = load_config()
        assert cfg.disabled_providers == ["ollama", "groq"]

    def test_malformed_json_returns_defaults(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        monkeypatch.delenv("OPENCODE_CONFIG_CONTENT", raising=False)
        monkeypatch.delenv("OPENCODE_MODEL", raising=False)
        config_file = tmp_path / "opencode.json"
        config_file.write_text("this is not valid json {{{")
        cfg = load_config()
        assert cfg.model == ""

    def test_mcp_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        monkeypatch.delenv("OPENCODE_CONFIG_CONTENT", raising=False)
        monkeypatch.delenv("OPENCODE_MODEL", raising=False)
        config_file = tmp_path / "opencode.json"
        config_file.write_text(json.dumps({
            "mcp": {
                "myserver": {"command": "server", "args": ["--port", "8080"]}
            },
        }))
        cfg = load_config()
        assert "myserver" in cfg.mcp
        assert cfg.mcp["myserver"]["command"] == "server"

    def test_theme_config_string(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        monkeypatch.delenv("OPENCODE_CONFIG_CONTENT", raising=False)
        monkeypatch.delenv("OPENCODE_MODEL", raising=False)
        config_file = tmp_path / "opencode.json"
        config_file.write_text(json.dumps({"theme": "dracula"}))
        cfg = load_config()
        assert cfg.theme == "dracula"

    def test_theme_config_dict(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        monkeypatch.delenv("OPENCODE_CONFIG_CONTENT", raising=False)
        monkeypatch.delenv("OPENCODE_MODEL", raising=False)
        config_file = tmp_path / "opencode.json"
        config_file.write_text(json.dumps({"theme": {"name": "nord", "mode": "light"}}))
        cfg = load_config()
        assert cfg.theme == "nord"
        assert cfg.theme_mode == "light"

    def test_snake_case_keys_accepted(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        monkeypatch.delenv("OPENCODE_CONFIG_CONTENT", raising=False)
        monkeypatch.delenv("OPENCODE_MODEL", raising=False)
        config_file = tmp_path / "opencode.json"
        config_file.write_text(json.dumps({
            "small_model": "openai/gpt-4.1-mini",
            "disabled_providers": ["ollama"],
            "provider": {
                "custom": {
                    "options": {
                        "api_key": "sk-test",
                        "base_url": "https://api.example.com",
                    }
                }
            },
        }))
        cfg = load_config()
        assert cfg.small_model == "openai/gpt-4.1-mini"
        assert cfg.disabled_providers == ["ollama"]
        assert cfg.provider["custom"].options.api_key == "sk-test"
        assert cfg.provider["custom"].options.base_url == "https://api.example.com"
