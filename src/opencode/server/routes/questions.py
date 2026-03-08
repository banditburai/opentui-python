"""Question routes — agent question/answer flow."""

from __future__ import annotations

from typing import Any

_MAX_PENDING = 100


def question_routes() -> list[Any]:
    """Question management routes."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    # Scoped to closure — no module-level mutable state
    pending: list[dict[str, Any]] = []

    async def list_questions(request: Request) -> JSONResponse:
        """List pending questions from the agent."""
        return JSONResponse(pending)

    async def reply_question(request: Request) -> JSONResponse:
        """Reply to a pending question."""
        request_id = request.path_params["request_id"]
        body = await request.json()
        answer = body.get("answer", "")

        for i, q in enumerate(pending):
            if q.get("id") == request_id:
                pending.pop(i)
                return JSONResponse({
                    "status": "answered",
                    "request_id": request_id,
                    "answer": answer,
                })

        return JSONResponse({"error": "question not found"}, status_code=404)

    async def reject_question(request: Request) -> JSONResponse:
        """Reject a pending question."""
        request_id = request.path_params["request_id"]

        for i, q in enumerate(pending):
            if q.get("id") == request_id:
                pending.pop(i)
                return JSONResponse({
                    "status": "rejected",
                    "request_id": request_id,
                })

        return JSONResponse({"error": "question not found"}, status_code=404)

    return [
        Route("/question", list_questions, methods=["GET"]),
        Route("/question/{request_id}/reply", reply_question, methods=["POST"]),
        Route("/question/{request_id}/reject", reject_question, methods=["POST"]),
    ]
