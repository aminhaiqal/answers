import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from axelyn.infrastructure.database import Base, SqlDocumentRepository


@pytest.fixture
def repository():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    yield SqlDocumentRepository(sessionmaker(engine))
    engine.dispose()
