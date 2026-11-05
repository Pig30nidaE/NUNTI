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
    generation_mode: str = "DISABLED"
    character_db_path: Path | None = None
    character_media_path: Path | None = None
    fixture_png: Path | None = None
    fixture_manifest: Path | None = None
    fixture_character_id: str | None = None
    generation_pipeline: str = "OPENAI_ELEVEN"
    openai_key: str = field(default="", repr=False)
    elevenlabs_key: str = field(default="", repr=False)
    google_key: str = field(default="", repr=False)
    recraft_key: str = field(default="", repr=False)
    generation_prices_verified: bool = False
    generation_step_ceilings: dict[str, int] = field(default_factory=dict)
    generation_job_cap_micros: int = 300000
    generation_total_cap_micros: int = 6000000
    generation_initial_limit: int = 20
    generation_voice_capacity: int = 30
    audio_ffmpeg: Path | None = None

    def __post_init__(self):
        if not self.tokens or any(
            not isinstance(token, str)
            or len(token) < 32
            or not token.isascii()
            or any(c.isspace() for c in token)
            or not isinstance(owner, str)
            or not owner
            or len(owner) > 128
            for token, owner in self.tokens.items()
        ):
            raise ValueError(
                "Configure NUNTI_AUTH_TOKENS with random tokens of at least 32 characters"
            )
        if not 1 <= self.retention_days <= 365:
            raise ValueError("NUNTI_RETENTION_DAYS must be between 1 and 365")
        if self.generation_mode not in {"DISABLED", "OFFLINE_FIXTURE", "API"}:
            raise ValueError("NUNTI_GENERATION_MODE must be DISABLED, OFFLINE_FIXTURE or API")
        if self.generation_pipeline not in {"OPENAI_ELEVEN", "GOOGLE_COMPARE"}:
            raise ValueError("Unsupported generation pipeline")
        if not isinstance(self.generation_step_ceilings, dict) or any(
            not isinstance(key, str) for key in self.generation_step_ceilings
        ):
            raise ValueError("Generation cost ceilings must be a JSON object")
        if any(
            type(value) is not int or value < 0 for value in self.generation_step_ceilings.values()
        ):
            raise ValueError("Generation cost ceilings must be nonnegative integer microdollars")
        if (
            not 1 <= self.generation_initial_limit <= 20
            or not 1 <= self.generation_voice_capacity <= 1000
        ):
            raise ValueError("Invalid initial batch or voice slot limit")
        if (
            not 0 < self.generation_job_cap_micros <= 300000
            or not 0 < self.generation_total_cap_micros <= 6000000
        ):
            raise ValueError("Generation budget exceeds approved initial limits")

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
            generation_mode=os.getenv("NUNTI_GENERATION_MODE", "DISABLED"),
            character_db_path=Path(os.environ["NUNTI_CHARACTER_DB_PATH"])
            if os.getenv("NUNTI_CHARACTER_DB_PATH")
            else None,
            character_media_path=Path(os.environ["NUNTI_CHARACTER_MEDIA_PATH"])
            if os.getenv("NUNTI_CHARACTER_MEDIA_PATH")
            else None,
            fixture_png=Path(os.environ["NUNTI_FIXTURE_PNG"])
            if os.getenv("NUNTI_FIXTURE_PNG")
            else None,
            fixture_manifest=Path(os.environ["NUNTI_FIXTURE_MANIFEST"])
            if os.getenv("NUNTI_FIXTURE_MANIFEST")
            else None,
            fixture_character_id=os.getenv("NUNTI_FIXTURE_CHARACTER_ID"),
            generation_pipeline=os.getenv("NUNTI_GENERATION_PIPELINE", "OPENAI_ELEVEN"),
            openai_key=os.getenv("OPENAI_API_KEY", ""),
            elevenlabs_key=os.getenv("ELEVENLABS_API_KEY", ""),
            google_key=os.getenv("GOOGLE_API_KEY", ""),
            recraft_key=os.getenv("RECRAFT_API_TOKEN", ""),
            generation_prices_verified=flag("NUNTI_GENERATION_PRICES_VERIFIED"),
            generation_step_ceilings=json.loads(
                os.getenv("NUNTI_GENERATION_STEP_CEILINGS_MICROS", "{}")
            ),
            generation_job_cap_micros=int(os.getenv("NUNTI_GENERATION_JOB_CAP_MICROS", "300000")),
            generation_total_cap_micros=int(
                os.getenv("NUNTI_GENERATION_TOTAL_CAP_MICROS", "6000000")
            ),
            generation_initial_limit=int(os.getenv("NUNTI_GENERATION_INITIAL_LIMIT", "20")),
            generation_voice_capacity=int(os.getenv("NUNTI_GENERATION_VOICE_CAPACITY", "30")),
            audio_ffmpeg=Path(os.environ["NUNTI_AUDIO_FFMPEG"])
            if os.getenv("NUNTI_AUDIO_FFMPEG")
            else None,
        )
