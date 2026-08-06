import os

APP_NAME = "VibeVerse"
APP_VERSION = "0.1.0"
PHASE = "Phases 1-14 — Full Platform"


class Settings:
    """Central config sourced from environment only (no hardcoded secrets)."""

    def __init__(self):
        self.app_name = APP_NAME
        self.app_version = APP_VERSION
        self.phase = PHASE
        self.mongo_url = os.environ["MONGO_URL"]
        self.db_name = os.environ["DB_NAME"]
        self.cors_origins = [
            o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()
        ]
        self.frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
        self.env = os.environ.get("APP_ENV", "development")


settings = Settings()
