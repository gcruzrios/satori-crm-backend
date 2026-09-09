from fastapi.testclient import TestClient

from app.main import create_app


def test_create_app_and_health() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_auth_login_route_exists() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@clinicasatori.cr", "password": "admin123"},
    )
    assert response.status_code in {200, 401}
