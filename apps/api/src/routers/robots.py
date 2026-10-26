"""Robot management routes — registration, heartbeat, pool status."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from packages.security.src.rbac import Permission
from services.resource_manager.src.pool import RobotPool

from ..core.auth import require_role

router = APIRouter(prefix="/robots", tags=["robots"])

_pool = RobotPool()


class RegisterRobotRequest(BaseModel):
    robot_id: str
    name: str
    capabilities: list[str] = []
    max_concurrent: int = 1


@router.post("/register")
async def register_robot(req: RegisterRobotRequest):
    slot = _pool.register(req.robot_id, req.name, set(req.capabilities), req.max_concurrent)
    return {"robot_id": slot.robot_id, "state": slot.state.value}


@router.post("/{robot_id}/heartbeat")
async def heartbeat(robot_id: str):
    _pool.heartbeat(robot_id)
    return {"status": "ok"}


@router.post("/{robot_id}/unregister")
async def unregister_robot(robot_id: str):
    _pool.unregister(robot_id)
    return {"status": "removed"}


@router.get("/")
async def list_robots():
    robots = _pool.list_robots()
    return [
        {
            "robot_id": r.robot_id,
            "name": r.name,
            "state": r.state.value,
            "capabilities": list(r.capabilities),
            "active_count": r.active_count,
        }
        for r in robots
    ]


@router.get("/stats")
async def pool_stats():
    return _pool.get_stats()


@router.post("/acquire")
async def acquire_robot(capabilities: list[str] | None = None):
    slot = _pool.acquire(set(capabilities) if capabilities else None)
    if not slot:
        raise HTTPException(status_code=503, detail="No available robot")
    return {"robot_id": slot.robot_id, "name": slot.name}


@router.post("/{robot_id}/release")
async def release_robot(robot_id: str):
    _pool.release(robot_id)
    return {"status": "released"}
