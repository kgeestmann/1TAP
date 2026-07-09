from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings, loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # tolerate leftover keys in .env (e.g. old LOG_CHANNEL_ID)
    )

    discord_bot_token: str = ""
    database_path: str = "data/bot.db"

    @property
    def database_url(self) -> str:
        """Async URL used by the running bot."""
        return f"sqlite+aiosqlite:///{self.database_path}"

    @property
    def sync_database_url(self) -> str:
        """Sync URL used by Alembic migrations."""
        return f"sqlite:///{self.database_path}"


settings = Settings()
