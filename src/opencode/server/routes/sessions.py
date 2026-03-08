"""Session routes — CRUD, messages, fork, abort, summarize."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opencode.bus import EventBus
    from opencode.tui.state import AppState


def session_routes(bus: EventBus, state: AppState) -> list[Any]:
    """Session management routes."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def list_sessions(request: Request) -> JSONResponse:
        sessions = state.store.list_sessions()
        return JSONResponse([
            {
                "id": s.id,
                "title": s.title,
                "model": s.model,
                "updated_at": s.updated_at.isoformat(),
                "created_at": s.created_at.isoformat(),
            }
            for s in sessions
        ])

    async def create_session(request: Request) -> JSONResponse:
        session_id = await state.create_session()
        return JSONResponse({"id": session_id})

    async def get_session(request: Request) -> JSONResponse:
        session_id = request.path_params["session_id"]
        session = state.store.get_session(session_id)
        if not session:
            return JSONResponse({"error": "session not found"}, status_code=404)
        return JSONResponse({
            "id": session.id,
            "title": session.title,
            "model": session.model,
            "working_dir": session.working_dir,
            "updated_at": session.updated_at.isoformat(),
            "created_at": session.created_at.isoformat(),
        })

    async def delete_session(request: Request) -> JSONResponse:
        session_id = request.path_params["session_id"]
        state.store.delete_session(session_id)
        return JSONResponse({"status": "deleted"})

    async def update_session(request: Request) -> JSONResponse:
        session_id = request.path_params["session_id"]
        body = await request.json()
        allowed = {"title", "model"}
        updates = {k: v for k, v in body.items() if k in allowed}
        if updates:
            state.store.update_session(session_id, **updates)
        return JSONResponse({"status": "updated"})

    async def get_messages(request: Request) -> JSONResponse:
        session_id = request.path_params["session_id"]
        messages = state.store.get_messages(session_id)
        result = []
        for m in messages:
            msg: dict[str, Any] = {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            if m.tool_calls:
                msg["tool_calls"] = json.loads(m.tool_calls)
            if m.tool_results:
                msg["tool_results"] = m.tool_results
            if m.model:
                msg["model"] = m.model
            if m.tokens_in:
                msg["tokens_in"] = m.tokens_in
            if m.tokens_out:
                msg["tokens_out"] = m.tokens_out
            result.append(msg)
        return JSONResponse(result)

    async def get_message(request: Request) -> JSONResponse:
        session_id = request.path_params["session_id"]
        message_id = request.path_params["message_id"]
        messages = state.store.get_messages(session_id)
        for m in messages:
            if m.id == message_id:
                msg: dict[str, Any] = {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat(),
                }
                if m.tool_calls:
                    msg["tool_calls"] = json.loads(m.tool_calls)
                if m.tool_results:
                    msg["tool_results"] = m.tool_results
                # Include parts if available
                parts = state.store.get_message_parts(m.id)
                if parts:
                    msg["parts"] = [
                        {
                            "id": p.id,
                            "type": p.type,
                            "content": p.content,
                            "tool_name": p.tool_name,
                            "status": p.status,
                        }
                        for p in parts
                    ]
                return JSONResponse(msg)
        return JSONResponse({"error": "message not found"}, status_code=404)

    async def delete_message(request: Request) -> JSONResponse:
        session_id = request.path_params["session_id"]
        message_id = request.path_params["message_id"]
        # Verify message belongs to this session
        messages = state.store.get_messages(session_id)
        if not any(m.id == message_id for m in messages):
            return JSONResponse({"error": "message not found in session"}, status_code=404)
        state.store.delete_message(message_id)
        return JSONResponse({"status": "deleted"})

    async def post_message(request: Request) -> JSONResponse:
        body = await request.json()
        text = body.get("text", "")
        if not text:
            return JSONResponse({"error": "text is required"}, status_code=400)

        session_id = request.path_params.get("session_id")
        if session_id:
            # Ensure we're on the right session
            current = state.current_session_id()
            if current != session_id:
                await state.switch_session(session_id)

        await state.send_message(text)
        return JSONResponse({"status": "ok"})

    async def abort_session(request: Request) -> JSONResponse:
        # Signal abort — sets streaming to false
        def _abort() -> None:
            state.is_streaming.set(False)
            state.status_text.set("Aborted")
        state.bridge.schedule_update(_abort)
        return JSONResponse({"status": "aborted"})

    async def get_file_changes(request: Request) -> JSONResponse:
        session_id = request.path_params["session_id"]
        changes = state.store.get_file_changes(session_id)
        return JSONResponse([
            {
                "id": c.id,
                "path": c.path,
                "action": c.action,
                "diff": c.diff,
                "created_at": c.created_at.isoformat(),
            }
            for c in changes
        ])

    return [
        Route("/session", list_sessions, methods=["GET"]),
        Route("/session", create_session, methods=["POST"]),
        Route("/session/{session_id}", get_session, methods=["GET"]),
        Route("/session/{session_id}", delete_session, methods=["DELETE"]),
        Route("/session/{session_id}", update_session, methods=["PATCH"]),
        Route("/session/{session_id}/message", get_messages, methods=["GET"]),
        Route("/session/{session_id}/message", post_message, methods=["POST"]),
        Route("/session/{session_id}/message/{message_id}", get_message, methods=["GET"]),
        Route("/session/{session_id}/message/{message_id}", delete_message, methods=["DELETE"]),
        Route("/session/{session_id}/abort", abort_session, methods=["POST"]),
        Route("/session/{session_id}/diff", get_file_changes, methods=["GET"]),
        # Legacy compat
        Route("/sessions", list_sessions, methods=["GET"]),
        Route("/sessions", create_session, methods=["POST"]),
        Route("/sessions/{session_id}/messages", get_messages, methods=["GET"]),
        Route("/messages", post_message, methods=["POST"]),
    ]
