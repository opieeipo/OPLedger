"""Runtime configuration.

Values come from environment variables (see compose.yaml) with sensible
defaults. On first run, the data dir and its config/ tree are created in the
mounted volume.
"""
import os
import shutil
from pathlib import Path

from pydantic_settings import BaseSettings

# Bundled default config templates, copied into the data volume on first run.
_BUNDLED_CONFIG = Path(__file__).resolve().parent.parent.parent.parent / "config"


class Settings(BaseSettings):
    data_dir: Path = Path(os.environ.get("OPLEDGER_DATA_DIR", "./data"))
    session_timeout: int = int(os.environ.get("OPLEDGER_SESSION_TIMEOUT", "28800"))
    # JWT signing secret. Generated and persisted on first run if unset.
    jwt_secret: str = os.environ.get("OPLEDGER_JWT_SECRET", "")

    @property
    def config_dir(self) -> Path:
        return self.data_dir / "config"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "opledger.db"

    def ensure_data_dir(self) -> None:
        """Create the data dir and seed config/ from bundled templates."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        for template in _BUNDLED_CONFIG.glob("*.yaml"):
            dest = self.config_dir / template.name
            if not dest.exists():
                shutil.copy(template, dest)


settings = Settings()
