"""Access-control gate logic — pure, no network/DB.

Covers utils.helpers.secret_ok, shared by the registration gate
(REGISTRATION_SECRET / invite_code) and the admin gate (ADMIN_TOKEN / X-Admin-Token).
"""

import pytest
from fastapi import HTTPException

from api import deps
from utils.helpers import secret_ok


def test_gate_disabled_when_expected_unset():
    # No secret configured → gate is open regardless of what's provided.
    assert secret_ok(None, None) is True
    assert secret_ok("", None) is True
    assert secret_ok(None, "anything") is True


def test_gate_requires_match_when_expected_set():
    assert secret_ok("s3cret", "s3cret") is True
    assert secret_ok("s3cret", "wrong") is False
    assert secret_ok("s3cret", None) is False
    assert secret_ok("s3cret", "") is False


class _Settings:
    def __init__(self, admin_token):
        self.admin_token = admin_token


def test_require_admin_enforces_token_when_set(monkeypatch):
    monkeypatch.setattr(deps, "get_settings", lambda: _Settings("adm1n"))
    with pytest.raises(HTTPException) as exc:
        deps.require_admin(x_admin_token="wrong")
    assert exc.value.status_code == 403
    # Correct token → no exception.
    deps.require_admin(x_admin_token="adm1n")


def test_require_admin_open_when_token_unset(monkeypatch):
    monkeypatch.setattr(deps, "get_settings", lambda: _Settings(None))
    deps.require_admin(x_admin_token=None)  # no raise
