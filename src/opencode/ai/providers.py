"""Provider registry — known providers, models, and resolution helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderInfo:
    """A known LLM provider."""

    id: str  # "minimax", "anthropic", "openai"
    name: str  # "MiniMax", "Anthropic"
    env: tuple[str, ...]  # ("MINIMAX_API_KEY",)
    api_url: str = ""  # default base URL (litellm knows most)


@dataclass(frozen=True)
class ModelInfo:
    """A known model."""

    id: str  # "minimax/MiniMax-M2.1"
    name: str  # "MiniMax M2.1"
    provider_id: str  # "minimax"
    context: int = 0  # context window (tokens)
    recommended: bool = False


@dataclass(frozen=True)
class ResolvedModel:
    """Result of resolving a provider/model ID against config."""

    litellm_model: str  # model string for litellm
    api_key: str | None = None
    api_base: str | None = None
    provider_id: str = ""


# ---------------------------------------------------------------------------
# Known providers
# ---------------------------------------------------------------------------

PROVIDERS: dict[str, ProviderInfo] = {
    p.id: p
    for p in [
        ProviderInfo("anthropic", "Anthropic", ("ANTHROPIC_API_KEY",)),
        ProviderInfo("openai", "OpenAI", ("OPENAI_API_KEY",)),
        ProviderInfo("google", "Google", ("GEMINI_API_KEY", "GOOGLE_API_KEY")),
        ProviderInfo("minimax", "MiniMax", ("MINIMAX_API_KEY",)),
        ProviderInfo("deepseek", "DeepSeek", ("DEEPSEEK_API_KEY",)),
        ProviderInfo("groq", "Groq", ("GROQ_API_KEY",)),
        ProviderInfo("openrouter", "OpenRouter", ("OPENROUTER_API_KEY",)),
        ProviderInfo("xai", "xAI", ("XAI_API_KEY",)),
        ProviderInfo("mistral", "Mistral", ("MISTRAL_API_KEY",)),
        ProviderInfo("together", "Together", ("TOGETHER_API_KEY", "TOGETHERAI_API_KEY")),
        ProviderInfo("fireworks", "Fireworks", ("FIREWORKS_API_KEY", "FIREWORKS_AI_API_KEY")),
        ProviderInfo("cerebras", "Cerebras", ("CEREBRAS_API_KEY",)),
        ProviderInfo("cohere", "Cohere", ("COHERE_API_KEY",)),
        ProviderInfo("perplexity", "Perplexity", ("PERPLEXITY_API_KEY",)),
        ProviderInfo("ollama", "Ollama", (), "http://localhost:11434"),
        ProviderInfo("amazon-bedrock", "Amazon Bedrock", ("AWS_ACCESS_KEY_ID",)),
        ProviderInfo("azure", "Azure OpenAI", ("AZURE_API_KEY",)),
        ProviderInfo("google-vertex", "Google Vertex", ("GOOGLE_APPLICATION_CREDENTIALS",)),
        ProviderInfo("github-copilot", "GitHub Copilot", ("GITHUB_TOKEN",)),
        ProviderInfo("custom", "Custom", ()),
    ]
}

# ---------------------------------------------------------------------------
# Recommended models (merged from OpenCode + hermes-agent)
# ---------------------------------------------------------------------------

MODELS: dict[str, ModelInfo] = {
    m.id: m
    for m in [
        # Anthropic
        ModelInfo("anthropic/claude-opus-4-0", "Claude Opus 4", "anthropic", 200_000, recommended=True),
        ModelInfo("anthropic/claude-sonnet-4-0", "Claude Sonnet 4", "anthropic", 200_000, recommended=True),
        ModelInfo("anthropic/claude-haiku-3-5", "Claude Haiku 3.5", "anthropic", 200_000),
        # OpenAI
        ModelInfo("openai/gpt-5", "GPT-5", "openai", 200_000, recommended=True),
        ModelInfo("openai/gpt-4.1", "GPT-4.1", "openai", 1_047_576),
        ModelInfo("openai/gpt-4.1-mini", "GPT-4.1 Mini", "openai", 1_047_576),
        ModelInfo("openai/o3", "o3", "openai", 200_000),
        ModelInfo("openai/o4-mini", "o4 Mini", "openai", 200_000),
        # Google
        ModelInfo("google/gemini-2.5-pro", "Gemini 2.5 Pro", "google", 1_048_576, recommended=True),
        ModelInfo("google/gemini-2.5-flash", "Gemini 2.5 Flash", "google", 1_048_576),
        # MiniMax
        ModelInfo("minimax/MiniMax-M2.1", "MiniMax M2.1", "minimax", 1_000_000, recommended=True),
        ModelInfo("minimax/MiniMax-M2.5", "MiniMax M2.5", "minimax", 1_000_000),
        # DeepSeek
        ModelInfo("deepseek/deepseek-chat", "DeepSeek V3", "deepseek", 64_000, recommended=True),
        ModelInfo("deepseek/deepseek-reasoner", "DeepSeek R1", "deepseek", 64_000),
        # Groq
        ModelInfo("groq/llama-3.3-70b-versatile", "Llama 3.3 70B", "groq", 128_000),
        # xAI
        ModelInfo("xai/grok-3", "Grok 3", "xai", 131_072),
        ModelInfo("xai/grok-3-mini", "Grok 3 Mini", "xai", 131_072),
        # Mistral
        ModelInfo("mistral/mistral-large-latest", "Mistral Large", "mistral", 128_000),
    ]
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_provider(provider_id: str) -> ProviderInfo | None:
    """Look up a provider by ID."""
    return PROVIDERS.get(provider_id)


def detect_available() -> list[ProviderInfo]:
    """Return providers whose env vars are set (i.e. likely configured)."""
    available = []
    for provider in PROVIDERS.values():
        if not provider.env:
            # Providers like ollama/custom are always "available"
            available.append(provider)
            continue
        if any(os.environ.get(var) for var in provider.env):
            available.append(provider)
    return available


def resolve_api_key(provider_id: str, config: object) -> str | None:
    """Resolve API key for a provider: config → env vars → None.

    *config* is expected to be an AppConfig (imported lazily to avoid cycles).
    """
    from opencode.config import AppConfig, _resolve_value

    if isinstance(config, AppConfig) and provider_id in config.provider:
        key = config.provider[provider_id].options.api_key
        if key:
            return _resolve_value(key)

    # Global OPENCODE_API_KEY
    if isinstance(config, AppConfig):
        global_key = os.environ.get("OPENCODE_API_KEY", "")
        if global_key:
            return global_key

    # Provider-specific env vars
    provider = PROVIDERS.get(provider_id)
    if provider:
        for var in provider.env:
            val = os.environ.get(var)
            if val:
                return val
    return None


def resolve_model(model_id: str, config: object) -> ResolvedModel:
    """Parse ``provider/model`` and resolve key + base URL.

    Falls back to passing *model_id* straight to litellm if no ``/`` found.
    """
    from opencode.config import AppConfig, _resolve_value

    provider_id = ""
    litellm_model = model_id

    if "/" in model_id:
        provider_id, _ = model_id.split("/", 1)
        litellm_model = model_id  # litellm uses provider/model natively

    # Resolve base URL from config or provider defaults
    api_base: str | None = None
    if isinstance(config, AppConfig) and provider_id and provider_id in config.provider:
        raw_url = config.provider[provider_id].options.base_url
        if raw_url:
            api_base = _resolve_value(raw_url)

    if api_base is None and provider_id:
        provider = PROVIDERS.get(provider_id)
        if provider and provider.api_url:
            api_base = provider.api_url

    api_key = resolve_api_key(provider_id, config) if provider_id else None

    # If no provider prefix but we have a global OPENCODE_API_KEY, use it
    if not provider_id:
        if isinstance(config, AppConfig):
            api_key = os.environ.get("OPENCODE_API_KEY") or None

    return ResolvedModel(
        litellm_model=litellm_model,
        api_key=api_key,
        api_base=api_base or None,
        provider_id=provider_id,
    )
