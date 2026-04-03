import json


def test_api_login_success(client, admin_user):
    resp = client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["username"] == "admin"
    assert data["is_admin"] is True


def test_api_login_failure(client):
    resp = client.post("/api/v1/login", json={"username": "admin", "password": "wrongpass"})
    assert resp.status_code == 401
    assert "错误" in resp.get_json()["error"]


def test_change_password(client, admin_user):
    # 先登录
    client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})

    # 修改密码
    resp = client.put(
        "/api/v1/users/me/password",
        json={"old_password": "admin123", "new_password": "newsecure123"},
    )
    assert resp.status_code == 200

    # 旧密码失效
    resp = client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 401

    # 新密码生效
    resp = client.post("/api/v1/login", json={"username": "admin", "password": "newsecure123"})
    assert resp.status_code == 200
