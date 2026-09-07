from fastapi.testclient import TestClient

from app.app import app

client = TestClient(app)


def test_feed_requires_auth():
    response = client.get("/feed")
    assert response.status_code == 401

def test_fail_requires_auth():
    response = client.get("/red")
    assert response.status_code == 401