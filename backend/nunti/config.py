import json
import os
from dataclasses import dataclass, field
from pathlib import Path


def flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name, str(default)).lower()
    if value not in {"true", "false"}:
        raise ValueError(f"{name} must be true or false")
    return value == "true"


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path("data/nunti.sqlite3")
    tokens: dict[str, str] = field(default_factory=dict, repr=False)
    sync_enabled: bool = False
    enable_mocks: bool = False
    retention_days: int = 30
    require_https: bool = True
    max_body_bytes: int = 262144

    def __post_init__(self):
        if not self.tokens or any(
            not isinstance(token, str) or len(token) < 32
            or not token.isascii() or any(c.isspace() for c in token)
            or not isinstance(owner, str) or not owner or len(owner) > 128
            for token, owner in self.tokens.items()
        ):
            raise ValueError("Configure NUNTI_AUTH_TOKENS with random tokens of at least 32 characters")
        if not 1 <= self.retention_days <= 365:
            raise ValueError("NUNTI_RETENTION_DAYS must be between 1 and 365")

    @classmethod
    def from_env(cls):
        try:
            tokens = json.loads(os.getenv("NUNTI_AUTH_TOKENS", "{}"))
        except json.JSONDecodeError:
            raise ValueError("NUNTI_AUTH_TOKENS must be a JSON object") from None
        if not isinstance(tokens, dict):
            raise ValueError("NUNTI_AUTH_TOKENS must be a JSON object")
        return cls(
            db_path=Path(os.getenv("NUNTI_DB_PATH", "data/nunti.sqlite3")),
            tokens=tokens,
            sync_enabled=flag("NUNTI_SYNC_ENABLED"),
            enable_mocks=flag("NUNTI_ENABLE_MOCKS"),
            retention_days=int(os.getenv("NUNTI_RETENTION_DAYS", "30")),
            require_https=flag("NUNTI_REQUIRE_HTTPS", True),
        )
