import json


def test_create_project_requires_login(client):
    resp = client.post("/api/v1/projects", json={"name": "test"})
    # Flask-Login 默认重定向到登录页
    assert resp.status_code == 302


def test_create_and_get_project(client, admin_user):
    client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})

    resp = client.post("/api/v1/projects", json={
        "name": "demo",
        "description": "desc",
        "source_type": "git",
        "source_url": "https://github.com/demo/repo",
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["name"] == "demo"
    project_id = data["id"]

    resp = client.get(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "demo"


def test_duplicate_project_name(client, admin_user):
    client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})

    r1 = client.post("/api/v1/projects", json={"name": "dup"})
    assert r1.status_code == 201

    r2 = client.post("/api/v1/projects", json={"name": "dup"})
    assert r2.status_code == 409
