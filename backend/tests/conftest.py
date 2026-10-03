import atexit
import os
import shutil
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import text

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5433/learning_assistant_test",
)
_test_chroma_path = Path(tempfile.mkdtemp(prefix="learning-assistant-test-chroma-"))
os.environ["CHROMA_DB_PATH"] = str(_test_chroma_path)
atexit.register(shutil.rmtree, _test_chroma_path, ignore_errors=True)

from app.database import engine
from app.core import rate_limit

# Keep HTTP-level API tests independent of requests made in other tests.
rate_limit._windows.clear()


@pytest.fixture(scope="session", autouse=True)
def prepare_test_database():
    from app.database import Base

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_test_database(prepare_test_database):
    rate_limit._windows.clear()
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE notebooks, users "
                "RESTART IDENTITY CASCADE"
            )
        )

    yield


# FILE PURPOSE:
# Configures the isolated PostgreSQL test database and cleans test data before each test.

# FILE PURPOSE:
# Configures the isolated PostgreSQL database used by the automated test suite.
