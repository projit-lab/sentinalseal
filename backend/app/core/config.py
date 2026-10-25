from typing import Any, List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore"
    )

    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "SentinelSeal Backend"

    # CORS Origins (accepts JSON list or comma-separated string)
    # Demo-only endpoints (/demo/replay). Set DEMO_TOOLS=false to turn off.
    DEMO_TOOLS: bool = True

    # Browser origins on the venue LAN (laptop IP changes): any localhost / private-network port.
    BACKEND_CORS_ORIGIN_REGEX: str = r"^https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?$"

    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        import json
        if isinstance(v, str) and v.startswith("["):
            return json.loads(v)
        return v

    # Security
    SECRET_KEY: str = "secret-key-change-me-in-production"

    # Session configuration
    SESSION_EXPIRY_SECONDS: int = 300  # 5 minutes

    # Biometric validation bounds
    BPM_MIN: int = 40
    BPM_MAX: int = 220

    # Database Configuration (Placeholder)
    DATABASE_URL: str = "sqlite:///./sql_app.db"


settings = Settings()
