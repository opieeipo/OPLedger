"""Runtime configuration.

Values come from environment variables (see compose.yaml) with sensible
defaults. On first run, the data dir and its config/ tree are created in the
mounted volume.
"""
import os
import shutil
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings

# Bundled default config templates, copied into the data volume on first run.
_BUNDLED_CONFIG = Path(__file__).resolve().parent.parent.parent.parent / "config"


class Settings(BaseSettings):
    data_dir: Path = Path(os.environ.get("OPLEDGER_DATA_DIR", "./data"))
    session_timeout: int = int(os.environ.get("OPLEDGER_SESSION_TIMEOUT", "28800"))

    # Optional: supplying the passphrase via the environment auto-unlocks the
    # database at startup (convenient for unattended container restarts). When
    # unset, the database must be unlocked through the web UI on each boot, and
    # the passphrase never touches disk. Leave unset for the stricter posture.
    passphrase: str | None = os.environ.get("OPLEDGER_PASSPHRASE") or None

    @property
    def config_dir(self) -> Path:
        return self.data_dir / "config"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "opledger.db"

    @property
    def database_url(self) -> str | None:
        """Resolve the SQLAlchemy URL: env override, else config/settings.yaml.

        The default (sqlite+pysqlcipher) selects the local encrypted SQLCipher
        store. Point this at PostgreSQL to run against an external database
        instead — no application code changes required.
        """
        env = os.environ.get("OPLEDGER_DATABASE_URL")
        if env:
            return env
        path = self.config_dir / "settings.yaml"
        if path.exists():
            try:
                data = yaml.safe_load(path.read_text()) or {}
            except yaml.YAMLError:
                return None
            return data.get("database_url")
        return None

    def ensure_data_dir(self) -> None:
        """Create the data dir and seed config/ from bundled templates."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        for template in _BUNDLED_CONFIG.glob("*.yaml"):
            dest = self.config_dir / template.name
            if not dest.exists():
                shutil.copy(template, dest)


settings = Settings()
