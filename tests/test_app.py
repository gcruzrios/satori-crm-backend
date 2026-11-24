from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.main import create_app
from app.models.user import User

PROTECTED_GETS = [
    "/api/v1/users", "/api/v1/leads", "/api/v1/contacts", "/api/v1/companies",
    "/api/v1/services", "/api/v1/pipelines", "/api/v1/opportunities", "/api/v1/quotes",
    "/api/v1/invoices", "/api/v1/activities", "/api/v1/communications",
    "/api/v1/notifications", "/api/v1/search?q=a", "/api/v1/auth/me",
]


class FakeSession:
    """Only supports `db.get(User, id)`, which is all the auth layer needs."""

    def __init__(self, users: dict):
        self.users = users

    async def get(self, model, object_id):
        return self.users.get(object_id)

    async def execute(self, _stmt):
        """Login lookup: pretend the query matched the only user in the store."""
        users = list(self.users.values())

        class _Result:
            def scalar_one_or_none(self_inner):
                return users[0] if users else None

        return _Result()


def make_user(role: str, active: bool = True, password: str = "x") -> User:
    return User(id=uuid4(), first_name="T", last_name="U", email="t@x.cr", password_hash=hash_password(password),
                role=role, is_active=active, deleted_at=None)


def client_with(*users: User) -> TestClient:
    app = create_app()
    store = {u.id: u for u in users}

    async def fake_db():
        yield FakeSession(store)

    app.dependency_overrides[get_db] = fake_db
    return TestClient(app)


def bearer(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def test_health_is_public() -> None:
    assert TestClient(create_app()).get("/health").status_code == 200


@pytest.mark.parametrize("path", PROTECTED_GETS)
def test_endpoints_require_token(path: str) -> None:
    assert TestClient(create_app()).get(path).status_code == 401


def test_invalid_token_rejected() -> None:
    r = TestClient(create_app()).get("/api/v1/leads", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_unknown_or_inactive_user_rejected() -> None:
    ghost, inactive = make_user("admin"), make_user("admin", active=False)
    client = client_with(inactive)
    assert client.get("/api/v1/auth/me", headers=bearer(ghost)).status_code == 401
    assert client.get("/api/v1/auth/me", headers=bearer(inactive)).status_code == 401


def test_me_returns_capabilities() -> None:
    user = make_user("sales")
    r = client_with(user).get("/api/v1/auth/me", headers=bearer(user))
    assert r.status_code == 200 and "leads:read" in r.json()["capabilities"]


def test_role_without_capability_gets_403() -> None:
    user = make_user("therapist")
    client = client_with(user)
    assert client.get("/api/v1/leads", headers=bearer(user)).status_code == 403
    assert client.get("/api/v1/users", headers=bearer(user)).status_code == 403
    assert client.post("/api/v1/contacts", json={"first_name": "a", "last_name": "b"}, headers=bearer(user)).status_code == 403


def test_non_admin_cannot_create_users() -> None:
    user = make_user("sales")
    r = client_with(user).post("/api/v1/users", headers=bearer(user),
                               json={"first_name": "a", "last_name": "b", "email": "a@b.cr", "password": "x"})
    assert r.status_code == 403


def test_cors_only_allowed_origins() -> None:
    client = TestClient(create_app())
    ok = client.options("/health", headers={"Origin": "https://crm.satori.cr", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "https://crm.satori.cr"
    ok2 = client.options("/health", headers={"Origin": "https://satoricrm.greiv.in", "Access-Control-Request-Method": "GET"})
    assert ok2.headers.get("access-control-allow-origin") == "https://satoricrm.greiv.in"
    bad = client.options("/health", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers


def test_login_sets_httponly_refresh_cookie() -> None:
    user = make_user("admin", password="secret-pass")
    r = client_with(user).post("/api/v1/auth/login", json={"email": "t@x.cr", "password": "secret-pass"})
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "refresh_token=" in cookie and "httponly" in cookie and "path=/api/v1/auth" in cookie
    assert "secure" in cookie and "samesite=none" in cookie


def test_refresh_returns_new_access_token() -> None:
    user = make_user("admin")
    client = client_with(user)
    client.cookies.set("refresh_token", create_refresh_token(str(user.id)), path="/api/v1/auth")
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_refresh_requires_valid_refresh_cookie() -> None:
    user = make_user("admin")
    client = client_with(user)
    assert client.post("/api/v1/auth/refresh").status_code == 401
    # an access token is not accepted as a refresh token
    client.cookies.set("refresh_token", create_access_token(str(user.id)), path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_refresh_token_not_accepted_as_bearer() -> None:
    user = make_user("admin")
    r = client_with(user).get("/api/v1/auth/me", headers={"Authorization": f"Bearer {create_refresh_token(str(user.id))}"})
    assert r.status_code == 401


def test_refresh_rejected_for_inactive_user() -> None:
    user = make_user("admin", active=False)
    client = client_with(user)
    client.cookies.set("refresh_token", create_refresh_token(str(user.id)), path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_logout_clears_cookie() -> None:
    r = TestClient(create_app()).post("/api/v1/auth/logout")
    assert r.status_code == 200 and "refresh_token=" in r.headers["set-cookie"].lower()
