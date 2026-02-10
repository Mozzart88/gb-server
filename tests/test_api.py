import pytest
from fastapi.testclient import TestClient
import os
import jwt
import uuid
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

# Use dummy key for tests if not set - MUST be set before importing app
API_KEY = os.getenv("API_KEY", "test-key")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "test-jwt-secret-key")

# Ensure the app uses the test JWT secret key
os.environ["JWT_SECRET_KEY"] = JWT_SECRET_KEY

from src.server import app
from src.db import DB # Import the DB class, not the singleton instance

# Path to the schema.sql file
SCRIPT_DIR = os.path.dirname(__file__)
SCHEMA_PATH = os.path.join(SCRIPT_DIR, "../schema.sql")

@pytest.fixture(name="db_session")
def db_session_fixture():
    # Use an in-memory SQLite database for testing
    test_db = DB(path=":memory:")
    # Apply schema to the in-memory database
    with open(SCHEMA_PATH, "r") as f:
        test_db.conn.executescript(f.read())
    yield test_db
    test_db.close()

@pytest.fixture(name="client")
def client_fixture(db_session: DB):
    # Override the app's db dependency for tests
    # FastAPI's Depends() injects the singleton `db` from src.db via get_db().
    # We need to replace get_db() return value with our test_db.
    from src.server import get_db
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    # Clear overrides after the test
    app.dependency_overrides = {}


def get_jwt_token(client: TestClient, new_uuid: str, uuid_to_increment: Optional[str] = None) -> str:
    payload = {"id": new_uuid}
    params = {}
    if uuid_to_increment:
        params["uuid"] = uuid_to_increment
    response = client.post("/register", json=payload, params=params)
    assert response.status_code == 200
    return response.json()["jwt"]

def test_get_currencies_no_auth(client: TestClient):
    response = client.get("/currencies")
    assert response.status_code == 401

def test_get_currencies_valid_auth(client: TestClient, db_session: DB):
    test_uuid = str(uuid.uuid4())
    token = get_jwt_token(client, test_uuid)
    response = client.get("/currencies", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert "list" in response.json()

def test_get_latest(client: TestClient, db_session: DB):
    test_uuid = str(uuid.uuid4())
    token = get_jwt_token(client, test_uuid)
    response = client.get("/latest", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert "rates" in response.json()

def test_get_historical_missing_date(client: TestClient, db_session: DB):
    test_uuid = str(uuid.uuid4())
    token = get_jwt_token(client, test_uuid)
    response = client.get("/historical", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 422 

def test_get_historical_with_date(client: TestClient, db_session: DB):
    test_uuid = str(uuid.uuid4())
    token = get_jwt_token(client, test_uuid)
    response = client.get("/historical?date=2025-01-01", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert "rates" in response.json()

# test cors headers
def test_cors_headers(client: TestClient):
    response = client.options("/latest", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET"
    })
    assert response.status_code == 200
    # CORSMiddleware reflects the origin if it matches allowed origins
    assert response.headers.get("access-control-allow-origin") in ["*", "http://localhost:3000"]

# test /latest?currency=USD
def test_latest_singular_currency(client: TestClient, db_session: DB):
    test_uuid = str(uuid.uuid4())
    token = get_jwt_token(client, test_uuid)
    response = client.get("/latest?currency=USD", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

# test /latest?currency=USD,ETH
def test_latest_singular_multiple_currencies(client: TestClient, db_session: DB):
    test_uuid = str(uuid.uuid4())
    token = get_jwt_token(client, test_uuid)
    response = client.get("/latest?currency=USD,ETH", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

# test /historical?date=2025-01-01&currency=USD
def test_historical_singular_currency(client: TestClient, db_session: DB):
    test_uuid = str(uuid.uuid4())
    token = get_jwt_token(client, test_uuid)
    response = client.get("/historical?date=2025-01-01&currency=USD", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

# test /historical?date=2025-01-01&currency=USD,ETH
def test_historical_singular_multiple_currencies(client: TestClient, db_session: DB):
    test_uuid = str(uuid.uuid4())
    token = get_jwt_token(client, test_uuid)
    response = client.get("/historical?date=2025-01-01&currency=USD,ETH", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

# test wrong auth in header
def test_wrong_auth_in_header(client: TestClient):
    response = client.get("/latest", headers={"Authorization": "Bearer wrong-jwt"})
    assert response.status_code == 401

# --- New /register endpoint tests ---

def test_register_new_installation(client: TestClient, db_session: DB):
    new_install_uuid = str(uuid.uuid4())
    response = client.post("/register", json={"id": new_install_uuid})
    assert response.status_code == 200
    assert "jwt" in response.json()
    
    # Verify the installation in DB
    installation = db_session.get_installation_by_uuid(new_install_uuid)
    assert installation is not None
    assert installation["installations"] == 1
    assert installation["jwt"] == response.json()["jwt"]

def test_register_with_existing_uuid_query_param(client: TestClient, db_session: DB):
    # First, create an existing installation
    existing_install_uuid = str(uuid.uuid4())
    get_jwt_token(client, existing_install_uuid) # This creates it with installations = 1

    # Now register a new one, referencing the existing one in query param
    new_install_uuid = str(uuid.uuid4())
    response = client.post(f"/register?uuid={existing_install_uuid}", json={"id": new_install_uuid})
    assert response.status_code == 200
    assert "jwt" in response.json()

    # Verify existing installation count increased
    existing_installation = db_session.get_installation_by_uuid(existing_install_uuid)
    assert existing_installation is not None
    assert existing_installation["installations"] == 2

    # Verify new installation created with correct count
    new_installation = db_session.get_installation_by_uuid(new_install_uuid)
    assert new_installation is not None
    assert new_installation["installations"] == 2
    assert new_installation["jwt"] == response.json()["jwt"]

def test_register_with_non_existing_uuid_query_param(client: TestClient, db_session: DB):
    non_existing_uuid = str(uuid.uuid4())
    new_install_uuid = str(uuid.uuid4())
    response = client.post(f"/register?uuid={non_existing_uuid}", json={"id": new_install_uuid})
    assert response.status_code == 200
    assert "jwt" in response.json()

    # Verify new installation created with default count (1)
    new_installation = db_session.get_installation_by_uuid(new_install_uuid)
    assert new_installation is not None
    assert new_installation["installations"] == 1
    assert new_installation["jwt"] == response.json()["jwt"]
    
    # Verify non-existing UUID is still not in DB
    assert db_session.get_installation_by_uuid(non_existing_uuid) is None

def test_register_returns_valid_jwt(client: TestClient, db_session: DB):
    new_install_uuid = str(uuid.uuid4())
    response = client.post("/register", json={"id": new_install_uuid})
    assert response.status_code == 200
    token = response.json()["jwt"]

    decoded_payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
    assert "jwt" in decoded_payload
    assert "issued" in decoded_payload
    assert "exp" in decoded_payload
    assert decoded_payload["exp"] > time.time() # Check expiration is in the future

def test_jwt_authentication_with_expired_token(client: TestClient, db_session: DB):
    # Generate an expired token
    expired_uuid = str(uuid.uuid4())
    expire_time = datetime.now(timezone.utc) - timedelta(days=1)
    to_encode = {"jwt": str(uuid.uuid4()), "issued": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(), "exp": expire_time.timestamp()}
    expired_token = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm="HS256")

    # Store the expired token in the DB to simulate it being valid but expired
    db_session.add_installation(expired_uuid, expired_token)

    response = client.get("/latest", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401 # Should fail due to expired token