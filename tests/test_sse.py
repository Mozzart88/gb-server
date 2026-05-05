import asyncio
import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "test-jwt-secret-key")
os.environ["JWT_SECRET_KEY"] = JWT_SECRET_KEY

from src.server import app, get_db
from src.db import DB
from src.sse import SSEManager, _DISCONNECT, _format_event, sse_manager

SCRIPT_DIR = os.path.dirname(__file__)
SCHEMA_PATH = os.path.join(SCRIPT_DIR, "../sql/schema.sql")


# ---------------------------------------------------------------------------
# Fixtures (mirror test_api.py to keep test_sse.py self-contained)
# ---------------------------------------------------------------------------

@pytest.fixture(name="db_session")
def db_session_fixture():
    test_db = DB(path=":memory:")
    with open(SCHEMA_PATH, "r") as f:
        test_db.conn.executescript(f.read())
    yield test_db
    test_db.close()


@pytest.fixture(name="client")
def client_fixture(db_session: DB):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}


def _register(client: TestClient) -> tuple[str, str]:
    """Register a device and return (installation_id, auth_header)."""
    iid = str(uuid.uuid4())
    resp = client.post("/register", json={"id": iid})
    assert resp.status_code == 200
    token = resp.json()["jwt"]
    return iid, f"Bearer {token}"


# ---------------------------------------------------------------------------
# Unit tests — SSEManager (no HTTP, fresh instances)
# ---------------------------------------------------------------------------

def test_format_event_with_data():
    assert _format_event("package", '{"x":1}') == 'event: package\ndata: {"x":1}\n\n'


def test_format_event_no_data():
    result = _format_event("handshake")
    assert result == "event: handshake\ndata: \n\n"


def test_connect_creates_queue():
    mgr = SSEManager()
    mgr.connect("dev-1")
    assert mgr.active_connections() == {"dev-1": 1}


def test_disconnect_removes_queue():
    mgr = SSEManager()
    q = mgr.connect("dev-1")
    mgr.disconnect("dev-1", q)
    assert mgr.active_connections() == {}


def test_multi_connection_same_device():
    mgr = SSEManager()
    q1 = mgr.connect("dev-1")
    q2 = mgr.connect("dev-1")
    assert mgr.active_connections() == {"dev-1": 2}
    mgr.disconnect("dev-1", q1)
    mgr.disconnect("dev-1", q2)
    assert mgr.active_connections() == {}


def test_notify_puts_formatted_chunk():
    mgr = SSEManager()
    q = mgr.connect("dev-1")
    mgr.notify("dev-1", "package", '{"package_id":"abc"}')
    chunk = q.get_nowait()
    assert chunk == 'event: package\ndata: {"package_id":"abc"}\n\n'
    mgr.disconnect("dev-1", q)


def test_notify_unknown_id_noop():
    mgr = SSEManager()
    mgr.notify("nonexistent", "package")  # must not raise


def test_notify_full_queue_does_not_raise():
    mgr = SSEManager()
    q: asyncio.Queue = asyncio.Queue(maxsize=1)
    mgr._connections["dev-1"] = [q]
    mgr.notify("dev-1", "package", "first")
    mgr.notify("dev-1", "package", "second")  # queue full — must not raise
    mgr._connections.pop("dev-1")


def test_notify_many_fans_out():
    mgr = SSEManager()
    qa = mgr.connect("dev-a")
    qb = mgr.connect("dev-b")
    mgr.notify_many(["dev-a", "dev-b"], "package", '{"package_id":"xyz"}')
    assert not qa.empty()
    assert not qb.empty()
    mgr.disconnect("dev-a", qa)
    mgr.disconnect("dev-b", qb)


async def test_heartbeat_yielded_on_timeout():
    mgr = SSEManager()
    q = mgr.connect("dev-1")
    gen = mgr.event_generator("dev-1", q, heartbeat_interval=0.01)
    chunk = await gen.__anext__()
    assert chunk == ": heartbeat\n\n"
    mgr.disconnect("dev-1", q)


async def test_disconnect_sentinel_stops_generator():
    mgr = SSEManager()
    q = mgr.connect("dev-1")
    q.put_nowait(_DISCONNECT)
    chunks = []
    async for chunk in mgr.event_generator("dev-1", q):
        chunks.append(chunk)
    assert chunks == []
    mgr.disconnect("dev-1", q)


async def test_event_generator_yields_chunk():
    mgr = SSEManager()
    q = mgr.connect("dev-1")
    mgr.notify("dev-1", "package", '{"package_id":"p1"}')
    q.put_nowait(_DISCONNECT)
    chunks = []
    async for chunk in mgr.event_generator("dev-1", q):
        chunks.append(chunk)
    assert len(chunks) == 1
    assert "package" in chunks[0]
    mgr.disconnect("dev-1", q)


# ---------------------------------------------------------------------------
# Integration tests — SSE notifications triggered by HTTP endpoints
# ---------------------------------------------------------------------------

def test_push_notifies_sse_recipient(client: TestClient, db_session: DB):
    sender_iid, sender_auth = _register(client)
    recipient_iid, _ = _register(client)

    q = sse_manager.connect(recipient_iid)
    try:
        payload = {
            "package": {
                "sender_id": sender_iid,
                "iv": "aaaaaa",
                "ciphertext": "bbbbbb",
                "recipient_keys": [{"installation_id": recipient_iid, "encrypted_key": "key1"}],
            }
        }
        resp = client.post("/sync/push", json=payload, headers={"Authorization": sender_auth})
        assert resp.status_code == 200
        package_id = resp.json()["package_id"]

        chunk = q.get_nowait()
        data = json.loads(chunk.split("data: ")[1].strip())
        assert data["package_id"] == package_id
    finally:
        sse_manager.disconnect(recipient_iid, q)


def test_push_notifies_only_addressed_recipients(client: TestClient, db_session: DB):
    sender_iid, sender_auth = _register(client)
    recipient_iid, _ = _register(client)
    bystander_iid, _ = _register(client)

    qa = sse_manager.connect(recipient_iid)
    qb = sse_manager.connect(bystander_iid)
    try:
        payload = {
            "package": {
                "sender_id": sender_iid,
                "iv": "aaaaaa",
                "ciphertext": "bbbbbb",
                "recipient_keys": [{"installation_id": recipient_iid, "encrypted_key": "key1"}],
            }
        }
        client.post("/sync/push", json=payload, headers={"Authorization": sender_auth})

        assert not qa.empty()
        assert qb.empty()
    finally:
        sse_manager.disconnect(recipient_iid, qa)
        sse_manager.disconnect(bystander_iid, qb)


def test_push_notifies_all_recipients(client: TestClient, db_session: DB):
    sender_iid, sender_auth = _register(client)
    iid_a, _ = _register(client)
    iid_b, _ = _register(client)

    qa = sse_manager.connect(iid_a)
    qb = sse_manager.connect(iid_b)
    try:
        payload = {
            "package": {
                "sender_id": sender_iid,
                "iv": "aaaaaa",
                "ciphertext": "bbbbbb",
                "recipient_keys": [
                    {"installation_id": iid_a, "encrypted_key": "key1"},
                    {"installation_id": iid_b, "encrypted_key": "key2"},
                ],
            }
        }
        client.post("/sync/push", json=payload, headers={"Authorization": sender_auth})

        assert not qa.empty()
        assert not qb.empty()
    finally:
        sse_manager.disconnect(iid_a, qa)
        sse_manager.disconnect(iid_b, qb)


def test_init_post_notifies_sse(client: TestClient, db_session: DB):
    sender_iid, sender_auth = _register(client)
    target_iid, _ = _register(client)

    q = sse_manager.connect(target_iid)
    try:
        resp = client.post(
            "/sync/init",
            json={"uuid": target_iid, "payload": "handshake-blob"},
            headers={"Authorization": sender_auth},
        )
        assert resp.status_code == 200

        chunk = q.get_nowait()
        assert "event: handshake" in chunk
    finally:
        sse_manager.disconnect(target_iid, q)


# ---------------------------------------------------------------------------
# HTTP smoke tests
# ---------------------------------------------------------------------------

def test_sync_events_no_auth(client: TestClient):
    resp = client.get("/sync/events?installation_id=some-id")
    assert resp.status_code == 401


def test_sync_events_missing_installation_id(client: TestClient):
    _, auth = _register(client)
    resp = client.get("/sync/events", headers={"Authorization": auth})
    assert resp.status_code == 422


async def test_sync_events_returns_stream_headers(db_session: DB):
    import httpx

    app.dependency_overrides[get_db] = lambda: db_session

    # Patch connect so the generator terminates immediately (ASGI transport
    # needs the response to be finite before it can deliver headers to the caller)
    original_connect = sse_manager.connect
    def patched_connect(installation_id: str) -> asyncio.Queue:
        q = original_connect(installation_id)
        q.put_nowait(_DISCONNECT)
        return q
    sse_manager.connect = patched_connect  # type: ignore[method-assign]

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            iid = str(uuid.uuid4())
            reg = await http_client.post("/register", json={"id": iid})
            auth = f"Bearer {reg.json()['jwt']}"

            resp = await http_client.get(
                f"/sync/events?installation_id={iid}",
                headers={"Authorization": auth},
            )
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            assert resp.headers.get("x-accel-buffering") == "no"
    finally:
        sse_manager.connect = original_connect  # type: ignore[method-assign]
        app.dependency_overrides = {}
