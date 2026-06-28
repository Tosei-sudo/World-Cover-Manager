import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture
def db_engine():
    # StaticPool reuses the same in-memory connection so db_session and the
    # client's sessions share identical state without needing a file-backed DB.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_engine, monkeypatch):
    Session = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    # Prevent background tasks from touching the production DB or running
    # expensive orbit propagation during unit/integration tests.
    monkeypatch.setattr(
        "app.routers.satellites.bg_compute_for_satellite_id", lambda sat_id: None
    )
    monkeypatch.setattr(
        "app.routers.stats.ensure_passes_fresh", lambda db: None
    )

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()
