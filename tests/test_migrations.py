from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_initial_migration_upgrades_and_downgrades(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    database = tmp_path / "migration.db"
    configuration = Config(str(root / "alembic.ini"))
    configuration.set_main_option("script_location", str(root / "migrations"))
    configuration.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database}")

    command.upgrade(configuration, "head")
    engine = create_engine(f"sqlite+pysqlite:///{database}")
    try:
        assert set(inspect(engine).get_table_names()) == {
            "alembic_version",
            "analysis_jobs",
            "chapters",
            "courses",
            "documents",
            "memberships",
            "notes",
            "page_analyses",
            "reading_progress",
            "tenants",
            "users",
        }
    finally:
        engine.dispose()

    command.check(configuration)
    command.downgrade(configuration, "base")
    engine = create_engine(f"sqlite+pysqlite:///{database}")
    try:
        assert inspect(engine).get_table_names() == ["alembic_version"]
    finally:
        engine.dispose()
