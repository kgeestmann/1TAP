import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings, loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # tolerate leftover keys in .env
    )

    # --- Discord ---
    discord_bot_token: str = ""

    # --- Database ---
    database_path: str = "data/bot.db"

    # --- Logging ---
    log_level: str = "INFO"
    log_dir: str = "logs"
    log_file_name: str = "bot.log"
    log_max_bytes: int = 5_000_000  # rotate at ~5 MB
    log_backup_count: int = 5       # keep 5 rotated files

    @property
    def database_url(self) -> str:
        """Async URL used by the running bot."""
        return f"sqlite+aiosqlite:///{self.database_path}"

    @property
    def sync_database_url(self) -> str:
        """Sync URL used by Alembic migrations."""
        return f"sqlite:///{self.database_path}"

    @property
    def log_file_path(self) -> str:
        return os.path.join(self.log_dir, self.log_file_name)


settings = Settings()
