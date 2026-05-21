from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/streamx"
    SECRET_KEY: str = "change-me-in-production-must-be-at-least-32-chars!!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    APP_ENV: str = "development"
    DEBUG: bool = True
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5500,http://localhost:8000,https://streamx.team"

    ADMIN_EMAIL: str = "admin@streamx.team"
    ADMIN_PASSWORD: str = Field(..., description="Admin password from Railway env")
    ADMIN_FULL_NAME: str = "Administrator"

    # ── Telegram Posting ──────────────────────────────────────────────────────
    BOT_TOKEN: str = ""
    CHANNEL_EN: str = "@stockity_en"
    CHANNEL_ES: str = "@stockity_es"
    CHANNEL_PT: str = "@stockity_pt"
    UPLOAD_DIR: str = "./uploads"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_db_url_scheme(cls, v: str) -> str:
        if v.startswith("postgresql://"):
            return "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v

    @property
    def sync_database_url(self) -> str:
        """Synchronous DB URL for APScheduler SQLAlchemyJobStore (uses psycopg2)."""
        url = self.DATABASE_URL
        if "+asyncpg" in url:
            return url.replace("+asyncpg", "")
        return url

    @property
    def origins(self) -> list[str]:
        if not self.ALLOWED_ORIGINS.strip():
            return ["*"]
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


settings = Settings()
