"""Test-Setup: eigene SQLite-Datei statt MySQL, eigener Upload-Ordner."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

TMP = Path(tempfile.mkdtemp(prefix="edudevice_test_"))
os.environ["EDUDEVICE_DB_URL"] = f"sqlite:///{TMP / 'test.db'}"
os.environ["EDUDEVICE_UPLOAD_DIR"] = str(TMP / "uploads")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from scripts.seed import seed  # noqa: E402

Base.metadata.create_all(engine)
seed()


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


def _login(client, username, password):
    r = client.post("/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin(client):
    return _login(client, "admin", "admin123")


@pytest.fixture(scope="session")
def teacher(client):
    return _login(client, "alehrer", "lehrer123")


@pytest.fixture(scope="session")
def student(client):
    return _login(client, "tschueler", "schueler123")
