from pathlib import Path

import pytest

from freddie_pipeline.config import Config


def test_defaults_match_docker_compose():
    config = Config.from_env(env={})
    assert config.db_host == "localhost"
    assert config.db_port == 5432
    assert config.db_user == "freddie"
    assert config.db_name == "freddie"
    assert config.sql_dir == Path("sql")


def test_env_overrides():
    config = Config.from_env(
        env={
            "FREDDIE_DB_HOST": "db.internal",
            "FREDDIE_DB_PORT": "6543",
            "FREDDIE_DB_USER": "alice",
            "FREDDIE_DB_PASSWORD": "secret",
            "FREDDIE_DB_NAME": "loans",
            "FREDDIE_SQL_DIR": "custom/sql",
        }
    )
    assert config.db_host == "db.internal"
    assert config.db_port == 6543
    assert config.db_user == "alice"
    assert config.db_name == "loans"
    assert config.sql_dir == Path("custom/sql")


def test_invalid_port_raises():
    with pytest.raises(ValueError, match="PORT"):
        Config.from_env(env={"FREDDIE_DB_PORT": "not-a-number"})


def test_conninfo_contains_all_parts():
    config = Config.from_env(env={})
    conninfo = config.conninfo()
    for part in ("host=", "port=", "user=", "password=", "dbname="):
        assert part in conninfo


def test_safe_conninfo_hides_password():
    config = Config.from_env(env={"FREDDIE_DB_PASSWORD": "hunter2"})
    assert "hunter2" not in config.safe_conninfo()
