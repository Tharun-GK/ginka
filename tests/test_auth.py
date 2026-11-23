from api import SESSION_MAX_AGE, _session_token, _valid_session


def test_admin_session_signature_and_expiry():
    issued = 1_800_000_000
    token = _session_token("test-only-secret", issued)
    assert _valid_session(token, "test-only-secret", issued + 60)
    assert not _valid_session(token, "other-secret", issued + 60)
    assert not _valid_session(token, "test-only-secret", issued + SESSION_MAX_AGE + 1)
    assert not _valid_session(f"{issued}.tampered", "test-only-secret", issued + 60)


def test_admin_session_rejects_future_timestamp():
    issued = 1_800_000_000
    token = _session_token("test-only-secret", issued)
    assert not _valid_session(token, "test-only-secret", issued - 61)


def test_admin_actions_require_strong_configured_secrets():
    import api

    assert not api._admin_enabled("too-short", "test-secret")
    assert api._admin_enabled("strong-test-password", "s" * 32)
