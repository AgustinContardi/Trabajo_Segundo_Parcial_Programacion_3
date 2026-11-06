import os
import subprocess
import sys
from pathlib import Path

from app.core.config import Settings


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "POSTGRES_USER": "libreria",
        "POSTGRES_PASSWORD": "test-db-password",
        "POSTGRES_DB": "libreria",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": 5432,
        "JWT_SECRET": "test-jwt-secret-not-for-production",
    }
    values.update(overrides)
    return Settings(**values)


def test_cookie_secure_can_be_enabled_for_production() -> None:
    settings = _settings(COOKIE_SECURE=True)
    assert settings.COOKIE_SECURE is True
    assert "test-jwt-secret-not-for-production" not in repr(settings)


def test_cookie_secure_defaults_to_protected_value() -> None:
    assert _settings().COOKIE_SECURE is True


def test_cookie_secure_can_be_explicitly_disabled_for_local_development() -> None:
    assert _settings(COOKIE_SECURE=False).COOKIE_SECURE is False


def test_import_main_needs_no_secrets_or_database_connection() -> None:
    parcial_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    for key in (
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "JWT_SECRET",
    ):
        env.pop(key, None)
    env["PYTHONPATH"] = str(parcial_root)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import main; assert not hasattr(main.app.state, 'engine')",
        ],
        cwd=parcial_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "test-jwt-secret-not-for-production" not in result.stdout + result.stderr
