"""CLI entry point: ``python -m opencode``."""

from __future__ import annotations

import argparse
import asyncio
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenCode — AI coding assistant")
    parser.add_argument("--model", type=str, default="", help="Model override (e.g. minimax/MiniMax-M2.1)")
    parser.add_argument("--serve", action="store_true", help="Start SSE web server on :3000")
    parser.add_argument("--port", type=int, default=3000, help="Web server port (default: 3000)")
    args = parser.parse_args()

    asyncio.run(_run(serve=args.serve, port=args.port, model=args.model))


async def _run(*, serve: bool = False, port: int = 3000, model: str = "") -> None:
    from opencode.ai.provider import LLMProvider
    from opencode.ai.tools import ToolRegistry
    from opencode.ai.tools.file import read_file_tool, search_files_tool, write_file_tool
    from opencode.ai.tools.shell import shell_tool
    from opencode.bus import EventBus
    from opencode.config import load_config
    from opencode.db.store import Store
    from opencode.tui.app import create_app
    from opencode.tui.bridge import AsyncBridge
    from opencode.tui.components.input import InputState
    from opencode.tui.keybindings import default_keybindings, dispatch_key
    from opencode.tui.state import AppState
    from opentui import render, use_keyboard

    # Load configuration
    config = load_config()

    # Initialize theme system
    from opencode.tui.themes import init_theme

    init_theme(name=config.theme, mode=config.theme_mode)

    # Initialize services
    store = Store()
    provider = LLMProvider.from_config(config, model_override=model)

    tool_registry = ToolRegistry()
    for tool_fn in [read_file_tool, write_file_tool, search_files_tool, shell_tool]:
        tool_registry.register(tool_fn())

    # Connect MCP servers from config
    mcp_clients: list = []
    if config.mcp:
        from opencode.mcp.client import MCPClient

        for server_name, server_cfg in config.mcp.items():
            if isinstance(server_cfg, dict) and "command" in server_cfg:
                try:
                    client = MCPClient(
                        command=server_cfg["command"],
                        args=server_cfg.get("args", []),
                        env=server_cfg.get("env"),
                    )
                    await client.connect()
                    for tool in client.to_registry_tools():
                        tool_registry.register(tool)
                    mcp_clients.append(client)
                except Exception:
                    import logging

                    logging.getLogger(__name__).warning(
                        "Failed to connect MCP server %s", server_name, exc_info=True
                    )

    bus = EventBus()
    bridge = AsyncBridge()
    state = AppState(
        store=store,
        provider=provider,
        tool_registry=tool_registry,
        bridge=bridge,
        bus=bus,
    )

    # Start async backend
    bridge.start()

    # Load existing sessions
    bridge.submit(state.load_sessions())

    # Optionally start SSE server
    if serve:
        _start_server(bus, state, bridge, port)

    # Set up input handling
    input_state = InputState()

    def on_submit(text: str) -> None:
        if text.strip():
            bridge.submit(state.send_message(text))

    input_state.on_submit = on_submit

    # Set up keybindings
    kb_registry = default_keybindings()

    def on_key(event: object) -> None:
        if not dispatch_key(event, state, kb_registry):
            input_state.handle_key(event)

    use_keyboard(on_key)

    # Build and render
    app_fn = create_app(state, input_state)

    try:
        await render(app_fn)
    finally:
        for client in mcp_clients:
            try:
                await client.disconnect()
            except Exception:
                pass
        bridge.stop()
        store.close()


def _start_server(bus: object, state: object, bridge: object, port: int) -> None:
    """Start the SSE server on the bridge's asyncio loop."""
    try:
        from opencode.server.app import create_app as create_server_app

        app = create_server_app(bus, state)

        import uvicorn

        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        server = uvicorn.Server(config)
        bridge.submit(server.serve())
    except ImportError:
        print("Warning: starlette/uvicorn not installed, --serve unavailable", file=sys.stderr)


if __name__ == "__main__":
    main()
