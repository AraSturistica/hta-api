"""API keys formato hta_<id>_<secreto>; se guarda solo hash argon2id."""
import json
import secrets
from dataclasses import dataclass, field
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

_ph = PasswordHasher()


@dataclass
class KeyData:
    key_id: str
    hash: str
    sociedades: list[int] = field(default_factory=list)
    rate_per_hour: int = 100
    active: bool = True


def generate_key(key_id: str) -> tuple[str, str]:
    raw = f"hta_{key_id}_{secrets.token_hex(24)}"
    return raw, _ph.hash(raw)


class KeyStore:
    def __init__(self, keys: list[KeyData]):
        self._keys = {k.key_id: k for k in keys}

    @classmethod
    def from_file(cls, path: str) -> "KeyStore":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls([KeyData(**k) for k in data.get("keys", [])])

    def verify(self, raw: str) -> KeyData | None:
        parts = raw.split("_")
        if len(parts) < 3 or parts[0] != "hta":
            return None
        kd = self._keys.get("_".join(parts[1:-1]))
        if kd is None or not kd.active:
            return None
        try:
            _ph.verify(kd.hash, raw)
            return kd
        except (VerifyMismatchError, InvalidHashError):
            return None
