"""WebSocket endpoint for live execution updates."""

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.execution_service import ExecutionService

router = APIRouter()

_execution_service = ExecutionService()


@router.websocket("/ws/executions/{execution_id}")
async def execution_ws(websocket: WebSocket, execution_id: str) -> None:
    await websocket.accept()

    try:
        last_state: dict = {}
        while True:
            try:
                state = await _execution_service.get_execution_state(execution_id)
            except Exception:
                await websocket.send_json({"error": "Workflow not found or completed"})
                break

            if state != last_state:
                await websocket.send_json(state)
                last_state = state

                if state.get("status") in ("succeeded", "failed", "cancelled"):
                    break

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        pass
