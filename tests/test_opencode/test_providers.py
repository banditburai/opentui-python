"""Tests for provider registry and model resolution."""

from __future__ import annotations

import os

import pytest

from opencode.ai.providers import (
    MODELS,
    PROVIDERS,
    ResolvedModel,
    detect_available,
    get_provider,
    resolve_api_key,
    resolve_model,
)
from opencode.config import AppConfig, ProviderConfig, ProviderOptions


class TestProviderRegistry:
    def test_known_providers_exist(self):
        assert "anthropic" in PROVIDERS
        assert "openai" in PROVIDERS
        assert "minimax" in PROVIDERS
        assert "deepseek" in PROVIDERS

    def test_get_provider_found(self):
        p = get_provider("anthropic")
        assert p is not None
        assert p.name == "Anthropic"
        assert "ANTHROPIC_API_KEY" in p.env

    def test_get_provider_missing(self):
        assert get_provider("nonexistent") is None

    def test_provider_env_vars(self):
        p = get_provider("minimax")
        assert p is not None
        assert p.env == ("MINIMAX_API_KEY",)

    def test_ollama_has_default_url(self):
        p = get_provider("ollama")
        assert p is not None
        assert p.api_url == "http://localhost:11434"


class TestModelRegistry:
    def test_recommended_models_exist(self):
        recommended = [m for m in MODELS.values() if m.recommended]
        assert len(recommended) >= 5

    def test_model_id_format(self):
        for mid, model in MODELS.items():
            assert "/" in mid, f"Model {mid} should use provider/model format"
            assert model.provider_id in PROVIDERS


class TestDetectAvailable:
    def test_empty_env(self, monkeypatch):
        # Clear all provider env vars
        for p in PROVIDERS.values():
            for var in p.env:
                monkeypatch.delenv(var, raising=False)
        available = detect_available()
        # Should still include env-less providers like ollama, custom
        ids = [p.id for p in available]
        assert "ollama" in ids
        assert "custom" in ids

    def test_with_minimax_key(self, monkeypatch):
        for p in PROVIDERS.values():
            for var in p.env:
                monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        available = detect_available()
        ids = [p.id for p in available]
        assert "minimax" in ids

    def test_with_multiple_keys(self, monkeypatch):
        for p in PROVIDERS.values():
            for var in p.env:
                monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-oai")
        available = detect_available()
        ids = [p.id for p in available]
        assert "anthropic" in ids
        assert "openai" in ids


class TestResolveApiKey:
    def test_from_config(self):
        cfg = AppConfig(
            provider={
                "minimax": ProviderConfig(
                    options=ProviderOptions(api_key="cfg-key-123")
                )
            }
        )
        key = resolve_api_key("minimax", cfg)
        assert key == "cfg-key-123"

    def test_from_env_var(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "env-key-456")
        cfg = AppConfig()
        key = resolve_api_key("minimax", cfg)
        assert key == "env-key-456"

    def test_config_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "env-key")
        cfg = AppConfig(
            provider={
                "minimax": ProviderConfig(
                    options=ProviderOptions(api_key="cfg-key")
                )
            }
        )
        key = resolve_api_key("minimax", cfg)
        assert key == "cfg-key"

    def test_env_substitution_in_config(self, monkeypatch):
        monkeypatch.setenv("MY_SECRET", "resolved-secret")
        cfg = AppConfig(
            provider={
                "minimax": ProviderConfig(
                    options=ProviderOptions(api_key="{env:MY_SECRET}")
                )
            }
        )
        key = resolve_api_key("minimax", cfg)
        assert key == "resolved-secret"

    def test_unknown_provider_returns_none(self):
        cfg = AppConfig()
        key = resolve_api_key("unknown-provider", cfg)
        assert key is None

    def test_global_opencode_api_key(self, monkeypatch):
        monkeypatch.setenv("OPENCODE_API_KEY", "global-key")
        cfg = AppConfig()
        key = resolve_api_key("minimax", cfg)
        assert key == "global-key"


class TestResolveModel:
    def test_provider_model_format(self):
        cfg = AppConfig()
        resolved = resolve_model("minimax/MiniMax-M2.1", cfg)
        assert resolved.litellm_model == "minimax/MiniMax-M2.1"
        assert resolved.provider_id == "minimax"

    def test_plain_model_id(self):
        cfg = AppConfig()
        resolved = resolve_model("gpt-4", cfg)
        assert resolved.litellm_model == "gpt-4"
        assert resolved.provider_id == ""

    def test_resolves_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        cfg = AppConfig()
        resolved = resolve_model("anthropic/claude-sonnet-4-0", cfg)
        assert resolved.api_key == "sk-ant-test"

    def test_resolves_base_url_from_config(self):
        cfg = AppConfig(
            provider={
                "custom": ProviderConfig(
                    options=ProviderOptions(
                        api_key="my-key",
                        base_url="https://my.api/v1",
                    )
                )
            }
        )
        resolved = resolve_model("custom/my-model", cfg)
        assert resolved.api_base == "https://my.api/v1"
        assert resolved.api_key == "my-key"

    def test_ollama_gets_default_url(self):
        cfg = AppConfig()
        resolved = resolve_model("ollama/llama3", cfg)
        assert resolved.api_base == "http://localhost:11434"

    def test_file_substitution_in_base_url(self, tmp_path):
        secret_file = tmp_path / "url.txt"
        secret_file.write_text("  https://secret.api/v1  \n")
        cfg = AppConfig(
            provider={
                "custom": ProviderConfig(
                    options=ProviderOptions(
                        base_url=f"{{file:{secret_file}}}",
                    )
                )
            }
        )
        resolved = resolve_model("custom/my-model", cfg)
        assert resolved.api_base == "https://secret.api/v1"
