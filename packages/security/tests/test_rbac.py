"""Tests for RBAC permissions."""

import pytest
from packages.security.src.rbac import Permission, Role, has_permission, require_permission


def test_admin_has_all():
    for perm in Permission:
        assert has_permission("admin", perm)


def test_viewer_read_only():
    assert has_permission("viewer", Permission.PROCESS_READ)
    assert has_permission("viewer", Permission.EXECUTION_READ)
    assert not has_permission("viewer", Permission.PROCESS_CREATE)
    assert not has_permission("viewer", Permission.EXECUTION_START)


def test_operator_can_execute():
    assert has_permission("operator", Permission.EXECUTION_START)
    assert has_permission("operator", Permission.EXECUTION_CONTROL)
    assert not has_permission("operator", Permission.PROCESS_CREATE)


def test_developer_full_process():
    assert has_permission("developer", Permission.PROCESS_CREATE)
    assert has_permission("developer", Permission.PROCESS_DELETE)
    assert has_permission("developer", Permission.AI_EXECUTE)
    assert not has_permission("developer", Permission.USER_MANAGE)


def test_unknown_role():
    assert not has_permission("unknown", Permission.PROCESS_READ)


def test_require_permission_ok():
    require_permission("admin", Permission.USER_MANAGE)


def test_require_permission_denied():
    with pytest.raises(PermissionError, match="lacks permission"):
        require_permission("viewer", Permission.PROCESS_CREATE)
