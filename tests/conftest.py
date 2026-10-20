from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app

_TEST_DB_URL = "sqlite://"


@pytest.fixture
def session() -> Generator[Session]:
    # StaticPool keeps a single connection alive for the whole engine — without it, each
    # checkout against an in-memory sqlite URL gets its own empty database, so the tables
    # created below wouldn't be visible to the session actually used in a test.
    engine = create_engine(
        _TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as test_session:
        yield test_session


@pytest.fixture
def client(session: Session) -> Generator[TestClient]:
    def _get_session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = _get_session_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
