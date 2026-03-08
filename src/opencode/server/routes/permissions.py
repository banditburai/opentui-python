"""Permission routes — pending permission requests."""

from __future__ import annotations

from typing import Any

_MAX_PENDING = 100


def permission_routes() -> list[Any]:
    """Permission management routes."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    # Scoped to closure — no module-level mutable state
    pending: list[dict[str, Any]] = []

    async def list_permissions(request: Request) -> JSONResponse:
        """List pending permission requests."""
        return JSONResponse(pending)

    async def respond_permission(request: Request) -> JSONResponse:
        """Respond to a permission request."""
        request_id = request.path_params["request_id"]
        body = await request.json()
        approved = body.get("approved", False)

        for i, p in enumerate(pending):
            if p.get("id") == request_id:
                pending.pop(i)
                return JSONResponse({
                    "status": "approved" if approved else "denied",
                    "request_id": request_id,
                })

        return JSONResponse({"error": "request not found"}, status_code=404)

    async def submit_permission(request: Request) -> JSONResponse:
        """Submit a new permission request (used by agent loop)."""
        body = await request.json()
        if len(pending) >= _MAX_PENDING:
            return JSONResponse({"error": "too many pending requests"}, status_code=429)
        pending.append(body)
        return JSONResponse({"status": "submitted"})

    return [
        Route("/permission", list_permissions, methods=["GET"]),
        Route("/permission", submit_permission, methods=["POST"]),
        Route("/permission/{request_id}/reply", respond_permission, methods=["POST"]),
    ]
