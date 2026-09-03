from __future__ import annotations

import pytest

from app.security.permissions import PermissionChecker, PermissionLevel


def test_permission_level_ordering():
    assert PermissionLevel.LOW < PermissionLevel.MEDIUM < PermissionLevel.HIGH < PermissionLevel.CRITICAL


def test_from_string():
    assert PermissionLevel.from_string("high") == PermissionLevel.HIGH
    with pytest.raises(ValueError):
        PermissionLevel.from_string("nonsense")


def test_low_and_medium_never_require_confirmation():
    checker = PermissionChecker()
    assert checker.requires_confirmation("t", PermissionLevel.LOW) is False
    assert checker.requires_confirmation("t", PermissionLevel.MEDIUM) is False


def test_high_requires_confirmation_by_default():
    checker = PermissionChecker()
    assert checker.requires_confirmation("t", PermissionLevel.HIGH) is True


def test_critical_requires_confirmation_by_default():
    checker = PermissionChecker()
    assert checker.requires_confirmation("t", PermissionLevel.CRITICAL) is True


def test_confirmation_can_be_disabled_via_config():
    checker = PermissionChecker(require_confirmation_high=False)
    assert checker.requires_confirmation("t", PermissionLevel.HIGH) is False


def test_override_changes_effective_level():
    checker = PermissionChecker(overrides={"send_email": "CRITICAL"})
    assert checker.effective_level("send_email", PermissionLevel.HIGH) == PermissionLevel.CRITICAL
    assert checker.requires_confirmation("send_email", PermissionLevel.HIGH) is True
