from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from mfe_study_cloud.db.base import Base
from mfe_study_cloud.db.session import create_session_factory, engine_for


@pytest.fixture
def sessions(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    factory = create_session_factory(f"sqlite+pysqlite:///{tmp_path / 'test.db'}")
    engine = engine_for(factory)
    Base.metadata.create_all(engine)
    try:
        yield factory
    finally:
        engine.dispose()
