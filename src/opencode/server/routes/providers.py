"""Provider routes — list providers and auth info."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opencode.tui.state import AppState


def provider_routes(state: AppState) -> list[Any]:
    """Provider information routes."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def list_providers(request: Request) -> JSONResponse:
        """List available providers."""
        return JSONResponse([
            {"id": "anthropic", "name": "Anthropic", "models": ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"]},
            {"id": "openai", "name": "OpenAI", "models": ["gpt-4o", "gpt-4o-mini", "o3-mini"]},
            {"id": "google", "name": "Google", "models": ["gemini-2.0-flash"]},
            {"id": "deepseek", "name": "DeepSeek", "models": ["deepseek-chat", "deepseek-reasoner"]},
            {"id": "openrouter", "name": "OpenRouter", "models": []},
            {"id": "ollama", "name": "Ollama", "models": []},
        ])

    async def get_provider_auth(request: Request) -> JSONResponse:
        """Get provider authentication status."""
        import os

        providers = {
            "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "openai": bool(os.environ.get("OPENAI_API_KEY")),
            "google": bool(os.environ.get("GOOGLE_API_KEY")),
            "deepseek": bool(os.environ.get("DEEPSEEK_API_KEY")),
            "openrouter": bool(os.environ.get("OPENROUTER_API_KEY")),
        }
        return JSONResponse(providers)

    return [
        Route("/provider", list_providers, methods=["GET"]),
        Route("/provider/auth", get_provider_auth, methods=["GET"]),
    ]
