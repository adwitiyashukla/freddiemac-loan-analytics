from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ENV_PREFIX = "FREDDIE_DB_"


@dataclass(frozen=True)
class Config:
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "freddie"
    db_password: str = "freddie"
    db_name: str = "freddie"
    sql_dir: Path = field(default_factory=lambda: Path("sql"))

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Config:
        env = os.environ if env is None else env
        port_raw = env.get(f"{ENV_PREFIX}PORT", "5432")
        try:
            port = int(port_raw)
        except ValueError as exc:
            raise ValueError(f"{ENV_PREFIX}PORT must be an integer, got {port_raw!r}") from exc
        return cls(
            db_host=env.get(f"{ENV_PREFIX}HOST", cls.db_host),
            db_port=port,
            db_user=env.get(f"{ENV_PREFIX}USER", cls.db_user),
            db_password=env.get(f"{ENV_PREFIX}PASSWORD", cls.db_password),
            db_name=env.get(f"{ENV_PREFIX}NAME", cls.db_name),
            sql_dir=Path(env.get("FREDDIE_SQL_DIR", "sql")),
        )

    def conninfo(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} user={self.db_user} "
            f"password={self.db_password} dbname={self.db_name}"
        )

    def safe_conninfo(self) -> str:
        return f"host={self.db_host} port={self.db_port} dbname={self.db_name} user={self.db_user}"
