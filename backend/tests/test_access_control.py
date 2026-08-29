"""Access-control gate logic — pure, no network/DB.

Covers utils.helpers.secret_ok, shared by the registration gate
(REGISTRATION_SECRET / invite_code) and the admin gate (ADMIN_TOKEN / X-Admin-Token).
"""

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
