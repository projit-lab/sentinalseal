from fastapi import APIRouter

from app.routers import approvers, demo, metrics, payments, health, session, auth, ws

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(session.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(auth.router, prefix="/auth", tags=["seal"])
api_router.include_router(approvers.router, tags=["approvers"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(metrics.router, tags=["metrics"])
api_router.include_router(demo.router, prefix="/demo", tags=["demo"])

# WebSocket routes are included without a prefix since they use
# the full path /ws/{session_id} directly
api_router.include_router(ws.router, tags=["websocket"])
