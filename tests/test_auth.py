"""Unauthenticated requests are rejected (build-order step 2's "done when").

Needs no database: get_db is swapped for a stub that finds no device.
Run from the repo root:  python -m tests.test_auth
"""
import os

os.environ.setdefault("DATABASE_URL", "postgresql://unused@localhost/unused")
os.environ["ENROLLMENT_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402

from app import auth  # noqa: E402
from app.main import app  # noqa: E402


class NoDevices:
    """Stands in for a Session: every query finds nothing."""
    def query(self, *_): return self
    def filter(self, *_): return self
    def first(self): return None


app.dependency_overrides[auth.get_db] = lambda: NoDevices()
client = TestClient(app)

HEARTBEAT = {"st_device_id": "C02TEST", "st_hostname": "lab-mac-1"}
EVENT = {**HEARTBEAT, "st_user_name": "jdoe", "st_event_type": "lock",
         "st_session_id": "s1", "st_platform": "macOS"}
REGISTER = {"st_device_id": "C02TEST", "st_hostname": "lab-mac-1", "st_platform": "macOS"}


def test_device_endpoints_need_a_valid_token():
    for path, body in (("/api/heartbeat", HEARTBEAT), ("/api/event", EVENT)):
        for headers in ({}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer not-a-real-token"}):
            r = client.post(path, json=body, headers=headers)
            assert r.status_code == 401, (path, headers, r.status_code, r.text)


def test_register_needs_the_enrollment_secret():
    for headers in ({}, {"X-Enrollment-Secret": "wrong"}):
        r = client.post("/api/register", json=REGISTER, headers=headers)
        assert r.status_code == 401, (headers, r.status_code, r.text)


def test_no_command_endpoint():
    r = client.post("/api/admin/queue_command", params={"device_id": "x", "command_text": "id"})
    assert r.status_code == 404, r.status_code


if __name__ == "__main__":
    test_device_endpoints_need_a_valid_token()
    test_register_needs_the_enrollment_secret()
    test_no_command_endpoint()
    print("auth tests OK")
