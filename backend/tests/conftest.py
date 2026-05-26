# Pytest configuration: stubs for CI without full Docker deps.
import os
import sys
import types
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _stub(*names):
    for name in names:
        parts = name.split(".")
        for i in range(1, len(parts) + 1):
            key = ".".join(parts[:i])
            if key not in sys.modules:
                sys.modules[key] = MagicMock()


# 1. Stub heavy external deps (ML, PDF, DB drivers)
_stub("sentence_transformers", "fitz", "asyncpg")
_stub("pgvector", "pgvector.sqlalchemy")
sys.modules["pgvector.sqlalchemy"].Vector = lambda dim: None

# 2. Stub pydantic_settings
import pydantic

_ps = types.ModuleType("pydantic_settings")

class _BS(pydantic.BaseModel):
    model_config = {"env_file": ".env", "extra": "ignore"}

_ps.BaseSettings = _BS
_ps.SettingsConfigDict = dict
sys.modules["pydantic_settings"] = _ps

# 3. Stub app.config (avoids Settings() instantiation at import)
# Do NOT stub "app" itself — let Python find the real app/ package on disk.
_cfg = types.ModuleType("app.config")

class _FakeSettings:
    database_url = "postgresql+asyncpg://test:test@localhost/test"
    openrouter_api_key = "sk-or-test"
    llm_model = "test-model"
    allowed_origins = "http://localhost:3000"
    max_upload_size = 50 * 1024 * 1024
    upload_dir = "data/regulations"
    port = 8000

    @property
    def cors_origins_list(self):
        return ["http://localhost:3000"]

_cfg.Settings = _FakeSettings
_cfg.settings = _FakeSettings()
sys.modules["app.config"] = _cfg

# 4. Stub app.database (avoids create_async_engine at module level)
_db = types.ModuleType("app.database")
_db.Base = MagicMock()
_db.engine = MagicMock()
_db.async_session = MagicMock()
_db.get_db = MagicMock()
sys.modules["app.database"] = _db
