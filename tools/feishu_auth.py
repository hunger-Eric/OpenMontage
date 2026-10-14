"""Python device authorization and refresh using the OS credential vault.

Only public binding metadata lives on disk. Secrets stay in the Python keyring
backend; no native CLI, shell command, or CLI profile is accessed.
"""

from __future__ import annotations

import json
import hashlib
import os
import time
import uuid
from pathlib import Path
from typing import Any

import requests


SERVICE = "OpenMontage.Feishu"
SCOPES = "base:app:copy base:table:read base:field:read base:record:read base:record:create base:record:update docs:document.media:upload offline_access"


class FeishuAuthError(RuntimeError):
    pass


def config_path() -> Path:
    return Path(os.environ.get("FEISHU_AUTH_CONFIG", str(Path.home() / ".config" / "openmontage" / "feishu-auth.json")))


class CredentialVault:
    def __init__(self, backend=None):
        if backend is None:
            import keyring
            backend = keyring.get_keyring()
        self.backend = backend
        # No plaintext or command-based fallback backend is acceptable.
        if type(self.backend).__module__ not in {
            "keyring.backends.Windows", "keyring.backends.macOS", "keyring.backends.SecretService",
        }:
            raise FeishuAuthError("Python secure credential vault is unavailable")

    def get(self, key: str) -> dict[str, Any] | None:
        try:
            raw = self.backend.get_password(SERVICE, key)
            value = json.loads(raw) if raw else None
            if isinstance(value, dict) and value.get("vault_chunks") == 1:
                generation, count = value["generation"], value["count"]
                if not isinstance(generation, str) or type(count) is not int or not 0 < count <= 128:
                    raise ValueError()
                chunks = [self.backend.get_password(SERVICE, f"chunk:{key}:{generation}:{index}") for index in range(count)]
                if not all(isinstance(chunk, str) for chunk in chunks):
                    raise ValueError()
                raw = "".join(chunks)
                if hashlib.sha256(raw.encode()).hexdigest() != value["sha256"]:
                    raise ValueError()
                value = json.loads(raw)
            if value is not None and not isinstance(value, dict):
                raise ValueError()
            return value
        except Exception:
            raise FeishuAuthError("Python credential vault read failed") from None

    def put(self, key: str, value: dict[str, Any]) -> None:
        try:
            self._clean_retired(key, "pending:")
            self._clean_retired(key)
            previous_raw = self.backend.get_password(SERVICE, key)
            previous = json.loads(previous_raw) if previous_raw else None
            # Journal the old generation before activation. If this write
            # fails, the previous credential remains active and discoverable.
            if isinstance(previous, dict) and previous.get("vault_chunks") == 1:
                self.backend.set_password(SERVICE, "retired:" + key, json.dumps(previous))
            raw = json.dumps(value, ensure_ascii=True)
            if len(raw) <= 900:
                self.backend.set_password(SERVICE, key, raw)
            else:
                # Activate a complete generation before retiring the old one.
                generation = uuid.uuid4().hex
                chunks = [raw[index:index + 900] for index in range(0, len(raw), 900)]
                if len(chunks) > 128:
                    raise ValueError()
                manifest = {"vault_chunks": 1, "generation": generation, "count": len(chunks),
                            "sha256": hashlib.sha256(raw.encode()).hexdigest()}
                # Recover partial writes even when their immediate cleanup
                # also fails. The active-generation guard protects activation
                # whose storage outcome was uncertain.
                self.backend.set_password(SERVICE, "pending:" + key, json.dumps(manifest))
                try:
                    for index, chunk in enumerate(chunks):
                        chunk_key = f"chunk:{key}:{generation}:{index}"
                        self.backend.set_password(SERVICE, chunk_key, chunk)
                    self.backend.set_password(SERVICE, key, json.dumps(manifest))
                except Exception:
                    self._clean_retired(key, "pending:")
                    raise
                self._clean_retired(key, "pending:")
            if isinstance(previous, dict) and previous.get("vault_chunks") == 1:
                # Retain only non-secret cleanup metadata so a failed deletion
                # is visible and can be retried without re-exchanging a token.
                self._clean_retired(key)
        except Exception:
            raise FeishuAuthError("Python credential vault write failed") from None

    def _clean_retired(self, key: str, prefix: str = "retired:") -> None:
        raw = self.backend.get_password(SERVICE, prefix + key)
        if not raw:
            return
        manifest = json.loads(raw)
        generation, count = manifest["generation"], manifest["count"]
        if not isinstance(generation, str) or type(count) is not int or not 0 < count <= 128:
            raise ValueError()
        active_raw = self.backend.get_password(SERVICE, key)
        active = json.loads(active_raw) if active_raw else None
        # A crash before activation leaves a journal for the still-live
        # generation. Never delete that generation's secret chunks.
        if not (isinstance(active, dict) and active.get("vault_chunks") == 1 and active.get("generation") == generation):
            for index in range(count):
                chunk_key = f"chunk:{key}:{generation}:{index}"
                if self.backend.get_password(SERVICE, chunk_key) is not None:
                    self.backend.delete_password(SERVICE, chunk_key)
        self.backend.delete_password(SERVICE, prefix + key)


class FeishuAuth:
    def __init__(self, path: Path | None = None, vault=None, session=None, now=time.time):
        self.path = path or config_path()
        self.vault = vault if vault is not None else CredentialVault()
        self.session = session if session is not None else requests.Session()
        self.now = now

    def binding(self) -> dict[str, str]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if (value.get("version") != 1 or value.get("brand") not in {"feishu", "lark"}
                    or not value.get("app_id") or not value.get("user_open_id")):
                raise ValueError()
            return value
        except Exception:
            raise FeishuAuthError("Python Feishu authorization binding is unavailable") from None

    def configure(self, app_id: str, app_secret: str, user_open_id: str, brand="feishu") -> None:
        if not app_id or not app_secret or not user_open_id or brand not in {"feishu", "lark"}:
            raise FeishuAuthError("Python Feishu authorization binding is invalid")
        value = {"version": 1, "app_id": app_id, "user_open_id": user_open_id, "brand": brand}
        if self.path.exists() and self.binding() != value:
            raise FeishuAuthError("Existing Python authorization binding must not be replaced")
        self.vault.put("app:" + app_id, {"app_secret": app_secret})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            with self.path.open("x", encoding="utf-8") as stream:
                json.dump(value, stream)
            self.path.chmod(0o600)

    def _request(self, method: str, url: str, **kwargs) -> dict[str, Any]:
        try:
            response = self.session.request(method, url, timeout=(10, 30), allow_redirects=False, **kwargs)
            data = response.json()
        except (requests.RequestException, ValueError):
            raise FeishuAuthError("Python Feishu authorization request outcome is unknown; no retry was sent") from None
        if (not isinstance(data, dict) or not (200 <= response.status_code < 300 or
                (400 <= response.status_code < 500 and isinstance(data.get("error"), str)))):
            raise FeishuAuthError("Python Feishu authorization returned an invalid response")
        return data

    @staticmethod
    def _accounts(binding) -> str:
        return "https://accounts.feishu.cn" if binding["brand"] == "feishu" else "https://accounts.larksuite.com"

    def _secret(self, binding) -> str:
        value = self.vault.get("app:" + binding["app_id"])
        if not value or not isinstance(value.get("app_secret"), str):
            raise FeishuAuthError("Python Feishu app credential is unavailable")
        return value["app_secret"]

    def begin(self) -> dict[str, Any]:
        binding = self.binding()
        key = "pending:" + binding["app_id"]
        pending = self.vault.get(key)
        if pending and isinstance(pending.get("candidate"), dict) and pending["candidate"].get("expires_at", 0) > self.now():
            return {"status": "ready_to_finish", "app_id": binding["app_id"]}
        if pending and pending.get("expires_at", 0) > self.now() and pending.get("exchange_outcome") != "unknown":
            return self._public_pending(pending)
        if pending and pending.get("exchange_outcome") == "unknown":
            self.vault.put("abandoned-exchange:" + binding["app_id"], pending)
        data = self._request("POST", self._accounts(binding) + "/oauth/v1/device_authorization",
            auth=(binding["app_id"], self._secret(binding)), data={"client_id": binding["app_id"], "scope": SCOPES})
        if not all(isinstance(data.get(key), str) and data[key] for key in ("device_code", "verification_uri_complete")):
            raise FeishuAuthError("Python Feishu device authorization was not accepted")
        interval = data.get("interval", 5)
        expires_in = data.get("expires_in", 240)
        if type(interval) is not int or type(expires_in) is not int or interval <= 0 or expires_in <= 0:
            raise FeishuAuthError("Python Feishu device authorization timing is invalid")
        pending = {"device_code": data["device_code"], "url": data["verification_uri_complete"],
                   "expires_at": self.now() + expires_in, "interval": interval,
                   "next_poll_at": self.now() + interval}
        self.vault.put(key, pending)
        return self._public_pending(pending)

    @staticmethod
    def _public_pending(pending):
        return {"status": "needs_authorization", "verification_url": pending["url"], "expires_at": pending["expires_at"]}

    def finish(self) -> dict[str, Any]:
        binding = self.binding()
        lock = self.path.with_suffix(".finish.lock")
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise FeishuAuthError("Python authorization completion is active or interrupted; no exchange was sent") from None
        try:
            os.close(descriptor)
            return self._finish_locked(binding)
        finally:
            lock.unlink()

    def _finish_locked(self, binding: dict[str, str]) -> dict[str, Any]:
        key = "pending:" + binding["app_id"]
        pending = self.vault.get(key)
        candidate = pending.get("candidate") if pending else None
        if not pending or (not candidate and pending.get("expires_at", 0) <= self.now()):
            raise FeishuAuthError("Python Feishu device authorization expired")
        if not candidate:
            if pending.get("exchange_outcome") == "unknown":
                raise FeishuAuthError("Python device exchange has an unknown outcome; this code must not be exchanged again")
            if self.now() < pending["next_poll_at"]:
                return {"status": "authorization_pending", "retry_after": pending["next_poll_at"] - self.now()}
            # Mark before sending: a crash or failed candidate save cannot permit
            # another exchange of a potentially consumed one-use device code.
            pending["next_poll_at"] = self.now() + pending["interval"]
            pending["exchange_outcome"] = "unknown"
            self.vault.put(key, pending)
            data = self._request("POST", self._accounts(binding) + "/oauth/v3/token", data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code", "device_code": pending["device_code"],
                "client_id": binding["app_id"], "client_secret": self._secret(binding)})
            if data.get("error") in {"authorization_pending", "slow_down"}:
                pending.pop("exchange_outcome", None)
                if data["error"] == "slow_down":
                    pending["interval"] += 5
                    pending["next_poll_at"] = self.now() + pending["interval"]
                self.vault.put(key, pending)
                return {"status": "authorization_pending", "retry_after": pending["interval"]}
            candidate = self._validate_token(data)
            # A successful one-use exchange must survive a later read/storage
            # failure; resume verification without exchanging this code again.
            pending["candidate"] = candidate
            self.vault.put(key, pending)
        token = candidate
        if token.get("expires_at", 0) <= self.now():
            raise FeishuAuthError("Python Feishu candidate credential expired")
        self._verify_user(binding, token)
        self.vault.put(self._user_key(binding), token)
        self.vault.put(key, {})
        return {"status": "authorized", "app_id": binding["app_id"], "user_open_id": binding["user_open_id"]}

    def _verify_user(self, binding, token) -> None:
        host = "https://open.feishu.cn" if binding["brand"] == "feishu" else "https://open.larksuite.com"
        info = self._request("GET", host + "/open-apis/authen/v1/user_info",
            headers={"Authorization": "Bearer " + token["access_token"]})
        user = info.get("data")
        if info.get("code") != 0 or not isinstance(user, dict) or user.get("open_id") != binding["user_open_id"]:
            raise FeishuAuthError("Python authorization user differs from the locked user; credential was not activated")

    def _validate_token(self, data) -> dict[str, Any]:
        if (not isinstance(data.get("access_token"), str) or not data["access_token"] or
                not isinstance(data.get("refresh_token"), str) or not data["refresh_token"] or
                type(data.get("expires_in")) is not int or data["expires_in"] <= 0 or
                not isinstance(data.get("token_type", "Bearer"), str) or
                data.get("token_type", "Bearer").lower() != "bearer"):
            raise FeishuAuthError("Python Feishu token exchange failed or returned an unsupported token")
        return {"access_token": data["access_token"], "refresh_token": data["refresh_token"],
                "expires_at": self.now() + data["expires_in"]}

    @staticmethod
    def _user_key(binding):
        return "user:" + binding["app_id"] + ":" + binding["user_open_id"]

    def credentials(self, identity: str):
        from tools.feishu_base_client import FeishuCredentials

        if identity != "user":
            raise FeishuAuthError("Python user authorization cannot supply bot credentials")
        binding = self.binding()
        key = self._user_key(binding)
        token = self.vault.get(key)
        if not token:
            raise FeishuAuthError("Python Feishu user authorization is required")
        if token.get("expires_at", 0) <= self.now() + 60:
            lock = self.path.with_suffix(".refresh.lock")
            try:
                descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                raise FeishuAuthError("Python credential refresh is active or has an unknown outcome") from None
            try:
                os.close(descriptor)
                # Unknown rotating refresh outcomes deliberately retain the lock.
                data = self._request("POST", self._accounts(binding) + "/oauth/v3/token", data={
                    "grant_type": "refresh_token", "refresh_token": token["refresh_token"],
                    "client_id": binding["app_id"], "client_secret": self._secret(binding)})
                token = self._validate_token(data)
                self._verify_user(binding, token)
                self.vault.put(key, token)
            except Exception:
                raise
            else:
                lock.unlink()
        return FeishuCredentials(binding["app_id"], identity, token["access_token"], binding["brand"], binding["user_open_id"])


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["configure", "begin", "finish", "status"])
    args = parser.parse_args()
    try:
        auth = FeishuAuth()
        if args.operation == "configure":
            # The installer/authorized host passes secrets over stdin, never in
            # argv, logs, model inputs or a versioned configuration file.
            try:
                supplied = json.load(sys.stdin)
                auth.configure(supplied["app_id"], supplied["app_secret"], supplied["user_open_id"], supplied.get("brand", "feishu"))
            except (ValueError, KeyError, TypeError):
                raise FeishuAuthError("Python authorization setup input is invalid") from None
            result = {"status": "configured", "app_id": supplied["app_id"], "user_open_id": supplied["user_open_id"]}
        elif args.operation == "begin":
            result = auth.begin()
        elif args.operation == "finish":
            result = auth.finish()
        else:
            credentials = auth.credentials("user")
            result = {"status": "authorized", "app_id": credentials.app_id, "identity": credentials.identity}
        print(json.dumps(result, ensure_ascii=False))
    except FeishuAuthError as error:
        print(json.dumps({"status": "failed", "message": str(error)}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
