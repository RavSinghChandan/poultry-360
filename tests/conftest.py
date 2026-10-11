"""With TEST_DATABASE_URL set (CI sets a Postgres one), every test uses that database, emptied first."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


@pytest.fixture(autouse=True)
def _test_database(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        yield
        return
    from core import store

    monkeypatch.setenv("DATABASE_URL", url)
    with store.connect() as c:
        for table in reversed(store.metadata.sorted_tables):
            c.execute(table.delete())
    yield
