"""Role-based access control — permissions per role."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel


class Role(str, Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    OPERATOR = "operator"
    VIEWER = "viewer"


class Permission(str, Enum):
    PROCESS_CREATE = "process:create"
    PROCESS_READ = "process:read"
    PROCESS_UPDATE = "process:update"
    PROCESS_DELETE = "process:delete"
    EXECUTION_START = "execution:start"
    EXECUTION_CONTROL = "execution:control"
    EXECUTION_READ = "execution:read"
    ROBOT_MANAGE = "robot:manage"
    ROBOT_READ = "robot:read"
    SECRET_MANAGE = "secret:manage"
    SECRET_READ = "secret:read"
    USER_MANAGE = "user:manage"
    AI_EXECUTE = "ai:execute"
    DATA_READ = "data:read"
    DATA_WRITE = "data:write"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: set(Permission),
    Role.DEVELOPER: {
        Permission.PROCESS_CREATE, Permission.PROCESS_READ, Permission.PROCESS_UPDATE,
        Permission.PROCESS_DELETE, Permission.EXECUTION_START, Permission.EXECUTION_CONTROL,
        Permission.EXECUTION_READ, Permission.ROBOT_READ, Permission.SECRET_READ,
        Permission.AI_EXECUTE, Permission.DATA_READ, Permission.DATA_WRITE,
    },
    Role.OPERATOR: {
        Permission.PROCESS_READ, Permission.EXECUTION_START, Permission.EXECUTION_CONTROL,
        Permission.EXECUTION_READ, Permission.ROBOT_READ, Permission.DATA_READ,
    },
    Role.VIEWER: {
        Permission.PROCESS_READ, Permission.EXECUTION_READ, Permission.ROBOT_READ,
    },
}


def has_permission(role: str, permission: Permission) -> bool:
    try:
        r = Role(role)
    except ValueError:
        return False
    return permission in ROLE_PERMISSIONS.get(r, set())


def require_permission(role: str, permission: Permission) -> None:
    if not has_permission(role, permission):
        raise PermissionError(f"Role '{role}' lacks permission '{permission.value}'")
