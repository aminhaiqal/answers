"""Bootstrap the initial schema explicitly; replace with migrations before schema changes."""

from sqlalchemy import create_engine

from axelyn.config import Settings
from axelyn.infrastructure.database import Base


def main() -> None:
    engine = create_engine(Settings().database_url)
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
