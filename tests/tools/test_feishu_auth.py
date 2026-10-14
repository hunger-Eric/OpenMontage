from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
import requests

from tools.feishu_auth import CredentialVault, FeishuAuth, FeishuAuthError


class Vault:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def put(self, key, value):
        self.values[key] = value.copy()


class Session:
    def __init__(self, *values):
        self.values = list(values)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return SimpleNamespace(status_code=200, json=lambda: value)


def configured(tmp_path, *responses):
    vault, session = Vault(), Session(*responses)
    clock = [1000]
    auth = FeishuAuth(tmp_path / "auth.json", vault, session, lambda: clock[0])
    auth.configure("cli_same", "app-secret", "ou_same")
    return auth, vault, session, clock


def device():
    return {"device_code": "private-device-code", "verification_uri_complete": "https://accounts.feishu.cn/verify?opaque=abc%2Fdef",
            "expires_in": 240, "interval": 5}


def token():
    return {"access_token": "private-access", "refresh_token": "private-refresh", "expires_in": 7200, "token_type": "Bearer"}


def test_begin_keeps_secrets_in_vault_and_returns_original_url(tmp_path):
    auth, vault, session, _ = configured(tmp_path, device())
    result = auth.begin()
    assert result["verification_url"] == device()["verification_uri_complete"]
    assert "private-device-code" not in json.dumps(result)
    assert "secret" not in auth.path.read_text()
    assert session.calls[0][2]["auth"] == ("cli_same", "app-secret")
    assert session.calls[0][2]["allow_redirects"] is False
    assert vault.get("pending:cli_same")["device_code"] == "private-device-code"
    assert auth.begin() == result
    assert len(session.calls) == 1


def test_finish_verifies_exact_original_user_before_activation(tmp_path):
    auth, vault, session, clock = configured(tmp_path, device(), token(), {"code": 0, "data": {"open_id": "ou_same"}})
    auth.begin()
    assert auth.finish()["status"] == "authorization_pending"
    assert len(session.calls) == 1
    clock[0] += 5
    assert auth.finish() == {"status": "authorized", "app_id": "cli_same", "user_open_id": "ou_same"}
    credentials = auth.credentials("user")
    assert credentials.app_id == "cli_same" and credentials.access_token == "private-access"
    assert "private-access" not in repr(credentials)
    assert vault.get("pending:cli_same") == {}


def test_wrong_user_never_replaces_original_identity(tmp_path):
    auth, vault, _, clock = configured(tmp_path, device(), token(), {"code": 0, "data": {"open_id": "ou_someone_else"}})
    auth.begin()
    clock[0] += 5
    with pytest.raises(FeishuAuthError, match="differs from the locked user"):
        auth.finish()
    assert vault.get("user:cli_same:ou_same") is None


def test_userinfo_failure_resumes_without_exchanging_consumed_device_code(tmp_path):
    auth, vault, session, clock = configured(tmp_path, device(), token(), requests.Timeout("userinfo offline"),
        {"code": 0, "data": {"open_id": "ou_same"}})
    auth.begin()
    clock[0] += 5
    with pytest.raises(FeishuAuthError, match="outcome is unknown"):
        auth.finish()
    assert auth.begin()["status"] == "ready_to_finish"
    assert auth.finish()["status"] == "authorized"
    assert len([call for call in session.calls if call[1].endswith("/oauth/v3/token")]) == 1
    assert vault.get("user:cli_same:ou_same")["access_token"] == "private-access"


def test_candidate_save_failure_never_reexchanges_consumed_device_code(tmp_path):
    auth, vault, session, clock = configured(tmp_path, device(), token())
    auth.begin()
    original_put = vault.put

    def fail_candidate(key, value):
        if value.get("candidate"):
            raise FeishuAuthError("simulated candidate save failure")
        original_put(key, value)

    vault.put = fail_candidate
    clock[0] += 5
    with pytest.raises(FeishuAuthError, match="candidate save failure"):
        auth.finish()
    vault.put = original_put
    clock[0] += 6
    with pytest.raises(FeishuAuthError, match="must not be exchanged again"):
        auth.finish()
    assert len([call for call in session.calls if call[1].endswith("/oauth/v3/token")]) == 1


def test_token_exchange_transport_failure_blocks_replay(tmp_path):
    auth, _, session, clock = configured(tmp_path, device(), requests.Timeout("unknown exchange"))
    auth.begin()
    clock[0] += 5
    with pytest.raises(FeishuAuthError, match="outcome is unknown"):
        auth.finish()
    clock[0] += 6
    with pytest.raises(FeishuAuthError, match="must not be exchanged again"):
        auth.finish()
    assert len(session.calls) == 2


def test_begin_after_unknown_exchange_starts_a_new_code_without_replaying_old_one(tmp_path):
    fresh = {**device(), "device_code": "fresh-device-code", "verification_uri_complete": "https://accounts.feishu.cn/new-link"}
    auth, vault, session, clock = configured(tmp_path, device(), requests.Timeout("unknown exchange"), fresh)
    auth.begin()
    clock[0] += 5
    with pytest.raises(FeishuAuthError, match="outcome is unknown"):
        auth.finish()
    assert auth.begin()["verification_url"] == fresh["verification_uri_complete"]
    assert vault.get("abandoned-exchange:cli_same")["device_code"] == "private-device-code"
    assert vault.get("pending:cli_same")["device_code"] == "fresh-device-code"
    assert len([call for call in session.calls if call[1].endswith("/oauth/v3/token")]) == 1


def test_completion_lock_prevents_concurrent_exchange(tmp_path):
    auth, _, session, clock = configured(tmp_path, device())
    auth.begin()
    clock[0] += 5
    lock = auth.path.with_suffix(".finish.lock")
    lock.write_text("active", encoding="utf-8")
    with pytest.raises(FeishuAuthError, match="completion is active"):
        auth.finish()
    assert len(session.calls) == 1
    assert lock.exists()


def test_pending_and_slow_down_are_bounded_single_polls(tmp_path):
    auth, _, session, clock = configured(tmp_path, device(), {"error": "authorization_pending"}, {"error": "slow_down"})
    auth.begin()
    clock[0] += 5
    assert auth.finish() == {"status": "authorization_pending", "retry_after": 5}
    clock[0] += 5
    assert auth.finish() == {"status": "authorization_pending", "retry_after": 10}
    assert len(session.calls) == 3


def test_expired_authorization_does_not_poll_or_reauthorize(tmp_path):
    auth, _, session, clock = configured(tmp_path, device())
    auth.begin()
    clock[0] += 241
    with pytest.raises(FeishuAuthError, match="expired"):
        auth.finish()
    assert len(session.calls) == 1


def test_refresh_rotates_token_in_vault_without_output(tmp_path):
    auth, vault, session, _ = configured(tmp_path, token(), {"code": 0, "data": {"open_id": "ou_same"}})
    vault.put("user:cli_same:ou_same", {"access_token": "old", "refresh_token": "old-refresh", "expires_at": 1001})
    assert auth.credentials("user").access_token == "private-access"
    assert vault.get("user:cli_same:ou_same")["refresh_token"] == "private-refresh"
    assert session.calls[0][2]["data"]["grant_type"] == "refresh_token"
    assert not auth.path.with_suffix(".refresh.lock").exists()


def test_refreshed_token_for_another_user_is_never_activated(tmp_path):
    auth, vault, session, _ = configured(tmp_path, token(), {"code": 0, "data": {"open_id": "ou_wrong"}})
    previous = {"access_token": "old", "refresh_token": "old-refresh", "expires_at": 1001}
    vault.put("user:cli_same:ou_same", previous)
    with pytest.raises(FeishuAuthError, match="differs from the locked user"):
        auth.credentials("user")
    assert vault.get("user:cli_same:ou_same") == previous
    assert auth.path.with_suffix(".refresh.lock").exists()
    assert len(session.calls) == 2


def test_unknown_refresh_outcome_blocks_replay(tmp_path):
    auth, vault, session, _ = configured(tmp_path, requests.Timeout("private-token"))
    vault.put("user:cli_same:ou_same", {"access_token": "old", "refresh_token": "old-refresh", "expires_at": 1001})
    with pytest.raises(FeishuAuthError, match="outcome is unknown"):
        auth.credentials("user")
    with pytest.raises(FeishuAuthError, match="active or has an unknown outcome"):
        auth.credentials("user")
    assert len(session.calls) == 1


def test_configuration_cannot_change_application_or_user(tmp_path):
    auth, _, session, _ = configured(tmp_path)
    with pytest.raises(FeishuAuthError, match="must not be replaced"):
        auth.configure("different_app", "other-secret", "ou_same")
    assert session.calls == []


def test_user_authorization_never_falls_back_to_bot(tmp_path):
    auth, _, session, _ = configured(tmp_path)
    with pytest.raises(FeishuAuthError, match="cannot supply bot"):
        auth.credentials("bot")
    assert session.calls == []


def test_long_tokens_use_atomic_vault_chunks_without_plaintext_files():
    class Backend:
        def __init__(self):
            self.values = {}

        def get_password(self, service, key):
            return self.values.get((service, key))

        def set_password(self, service, key, value):
            assert len(value) <= 900
            self.values[service, key] = value

        def delete_password(self, service, key):
            del self.values[service, key]

    Backend.__module__ = "keyring.backends.Windows"
    backend = Backend()
    vault = CredentialVault(backend)
    value = {"access_token": "access" * 1500, "refresh_token": "refresh" * 1500}
    vault.put("user:app:user", value)
    assert vault.get("user:app:user") == value
    assert len(backend.values) > 2


def test_incomplete_chunk_write_keeps_previous_credential_active():
    class Backend:
        def __init__(self):
            self.values = {}
            self.fail = False

        def get_password(self, service, key):
            return self.values.get((service, key))

        def set_password(self, service, key, value):
            if self.fail and key.startswith("chunk:"):
                raise OSError()
            self.values[service, key] = value

        def delete_password(self, service, key):
            del self.values[service, key]

    Backend.__module__ = "keyring.backends.Windows"
    backend = Backend()
    vault = CredentialVault(backend)
    vault.put("user:app:user", {"access_token": "previous"})
    backend.fail = True
    with pytest.raises(FeishuAuthError, match="write failed"):
        vault.put("user:app:user", {"access_token": "large-token" * 1500})
    assert vault.get("user:app:user") == {"access_token": "previous"}


def test_clean_machine_setup_entry_uses_stdin_and_never_prints_secret(tmp_path, monkeypatch, capsys):
    import io
    import sys
    from tools import feishu_auth as module

    auth = FeishuAuth(tmp_path / "new-auth.json", Vault(), Session())
    monkeypatch.setattr(module, "FeishuAuth", lambda: auth)
    monkeypatch.setattr(sys, "argv", ["feishu_auth", "configure"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"app_id": "cli_test", "app_secret": "private-app-secret", "user_open_id": "ou_test"})))
    module.main()
    output = capsys.readouterr().out
    assert json.loads(output)["status"] == "configured"
    assert "private-app-secret" not in output
    assert auth.binding()["user_open_id"] == "ou_test"


@pytest.mark.parametrize("replacement", [{}, {"access_token": "new"}, {"access_token": "new" * 1500}])
def test_replacing_chunked_credentials_removes_retired_secret_chunks(replacement):
    class Backend:
        def __init__(self):
            self.values = {}

        def get_password(self, service, key):
            return self.values.get((service, key))

        def set_password(self, service, key, value):
            self.values[service, key] = value

        def delete_password(self, service, key):
            del self.values[service, key]

    Backend.__module__ = "keyring.backends.Windows"
    backend = Backend()
    vault = CredentialVault(backend)
    vault.put("user:test", {"access_token": "retired-secret" * 200})
    retired = {key for key in backend.values if key[1].startswith("chunk:")}
    vault.put("user:test", replacement)
    assert vault.get("user:test") == replacement
    assert not retired.intersection(backend.values)


@pytest.mark.parametrize("failure", ["journal", "activation", "delete", "activation_and_cleanup"])
def test_chunk_retirement_failures_remain_recoverable(failure):
    class Backend:
        def __init__(self):
            self.values = {}
            self.failure = None

        def get_password(self, service, key):
            return self.values.get((service, key))

        def set_password(self, service, key, value):
            if (self.failure == "journal" and key.startswith("retired:")) or (self.failure in {"activation", "activation_and_cleanup"} and key == "user:test"):
                raise OSError("simulated storage failure")
            self.values[service, key] = value

        def delete_password(self, service, key):
            if self.failure in {"delete", "activation_and_cleanup"} and key.startswith("chunk:"):
                raise OSError("simulated deletion failure")
            del self.values[service, key]

    Backend.__module__ = "keyring.backends.Windows"
    backend = Backend()
    vault = CredentialVault(backend)
    previous = {"access_token": "previous" * 200}
    vault.put("user:test", previous)
    retired = {key for key in backend.values if key[1].startswith("chunk:")}
    backend.failure = failure
    with pytest.raises(FeishuAuthError, match="write failed"):
        vault.put("user:test", {"access_token": "new" * 1000} if failure == "activation_and_cleanup" else {"access_token": "new"})
    assert vault.get("user:test") == ({"access_token": "new"} if failure == "delete" else previous)
    backend.failure = None
    vault.put("user:test", {"access_token": "recovered"})
    assert vault.get("user:test") == {"access_token": "recovered"}
    assert not retired.intersection(backend.values)
    assert not any(key[1].startswith("retired:") for key in backend.values)
    assert not any(key[1].startswith(("pending:", "chunk:")) for key in backend.values)
