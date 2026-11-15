"""Tokens de API revocables (plan §12A.2). Solo se guarda el SHA-256 del token; el token se muestra una vez al crearlo.

Formato: `ets_<key_id>_<secreto>`. Almacén JSON en `API_KEYS_FILE` (por defecto `.cache/security/`, no versionado).
Gestión: `scripts/manage_api_keys.py create|list|revoke`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

ALL_SCOPES = ("catalog:read", "analyses:write", "runs:read", "exports:read", "events:read", "workspaces:write")
DEFAULT_SCOPES = ("catalog:read", "analyses:write", "runs:read")


class InvalidToken(Exception):
    """Token presente pero inválido o revocado (→ 401)."""


@dataclass(frozen=True)
class Identity:
    kind: str  # anonymous | api_key
    subject: str  # key_id o "anon:<ip>"
    name: str | None = None
    scopes: tuple[str, ...] = ()

    @property
    def is_anonymous(self) -> bool:
        return self.kind == "anonymous"

    def has(self, scope: str) -> bool:
        return scope in self.scopes


@dataclass
class ApiKeyRecord:
    key_id: str
    name: str
    token_sha256: str
    scopes: list[str]
    created_at: str
    revoked_at: str | None = None
    last_used_at: str | None = None
    extra: dict = field(default_factory=dict)

    def public(self) -> dict:
        d = asdict(self)
        d.pop("token_sha256")
        return d


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class ApiKeyStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def _read(self) -> dict[str, ApiKeyRecord]:
        if not self.path.is_file():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return {k: ApiKeyRecord(**v) for k, v in data.items()}

    def _write(self, recs: dict[str, ApiKeyRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({k: asdict(v) for k, v in recs.items()}, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def create(self, name: str, scopes: tuple[str, ...] = DEFAULT_SCOPES) -> tuple[str, ApiKeyRecord]:
        unknown = set(scopes) - set(ALL_SCOPES)
        if unknown:
            raise ValueError(f"Scopes desconocidos: {sorted(unknown)}")
        key_id = secrets.token_hex(4)
        token = f"ets_{key_id}_{secrets.token_urlsafe(32)}"
        rec = ApiKeyRecord(key_id, name, _sha(token), list(scopes), datetime.now(UTC).isoformat())
        with self._lock:
            recs = self._read()
            recs[key_id] = rec
            self._write(recs)
        return token, rec

    def list(self) -> list[ApiKeyRecord]:
        return list(self._read().values())

    def revoke(self, key_id: str) -> bool:
        with self._lock:
            recs = self._read()
            rec = recs.get(key_id)
            if rec is None or rec.revoked_at:
                return False
            rec.revoked_at = datetime.now(UTC).isoformat()
            self._write(recs)
            return True

    def verify(self, token: str) -> Identity:
        parts = token.split("_", 2)
        if len(parts) != 3 or parts[0] != "ets":
            raise InvalidToken("Formato de token no reconocido")
        rec = self._read().get(parts[1])
        if rec is None or not hmac.compare_digest(rec.token_sha256, _sha(token)):
            raise InvalidToken("Token inválido")
        if rec.revoked_at:
            raise InvalidToken("Token revocado")
        return Identity("api_key", rec.key_id, rec.name, tuple(rec.scopes))
