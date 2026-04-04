"""Tests for app/auth.py"""
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import bcrypt

from app.extensions import db
from app.models import User


class TestLoginPage:
    """Test login page render and form submission"""

    def test_login_page_get(self, client):
        """Test GET request to login page"""
        response = client.get("/login")
        assert response.status_code == 200
        assert "EasyDockCross 登录" in response.data.decode('utf-8')

    def test_login_page_post_success(self, client, admin_user):
        """Test successful login via form"""
        response = client.post("/login", data={
            "username": "admin",
            "password": "admin123",
        }, follow_redirects=True)
        assert response.status_code == 200
        assert "仪表盘" in response.data.decode('utf-8') or "EasyDockCross" in response.data.decode('utf-8')

    def test_login_page_post_wrong_password(self, client, admin_user):
        """Test login with wrong password"""
        response = client.post("/login", data={
            "username": "admin",
            "password": "wrongpassword",
        })
        assert response.status_code == 401
        assert "用户名或密码错误" in response.data.decode('utf-8')

    def test_login_page_post_invalid_user(self, client):
        """Test login with non-existent user"""
        response = client.post("/login", data={
            "username": "nonexistent",
            "password": "password",
        })
        assert response.status_code == 401
        assert "用户名或密码错误" in response.data.decode('utf-8')

    def test_login_page_post_open_redirect_blocked(self, client, admin_user):
        """Test that open redirect is blocked"""
        response = client.post("/login?next=https://evil.com", data={
            "username": "admin",
            "password": "admin123",
        }, follow_redirects=False)
        # Should redirect to dashboard, not evil.com
        assert response.status_code == 302
        assert "evil.com" not in response.location


class TestLogout:
    """Test logout functionality"""

    def test_logout_requires_login(self, client):
        """Test logout without login redirects"""
        response = client.get("/logout", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_logout_success(self, client, admin_user):
        """Test successful logout"""
        # Login first
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        # Then logout
        response = client.get("/logout", follow_redirects=True)
        assert response.status_code == 200
        # After logout, accessing protected page should redirect to login
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location


class TestAPILogin:
    """Test API login endpoint"""

    def test_api_login_success(self, client, admin_user):
        """Test successful API login"""
        response = client.post("/api/v1/login", json={
            "username": "admin",
            "password": "admin123",
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data["username"] == "admin"
        assert data["is_admin"] is True
        assert "user_id" in data

    def test_api_login_missing_credentials(self, client):
        """Test API login with missing credentials"""
        response = client.post("/api/v1/login", json={
            "username": "admin",
        })
        assert response.status_code == 400
        assert "不能为空" in response.get_json()["error"]

    def test_api_login_wrong_password(self, client, admin_user):
        """Test API login with wrong password"""
        response = client.post("/api/v1/login", json={
            "username": "admin",
            "password": "wrongpassword",
        })
        assert response.status_code == 401
        assert "用户名或密码错误" in response.get_json()["error"]


class TestAPILogout:
    """Test API logout endpoint"""

    def test_api_logout_success(self, client, admin_user):
        """Test successful API logout"""
        # Login first
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        # Then logout
        response = client.post("/api/v1/logout")
        assert response.status_code == 200
        assert "已登出" in response.get_json()["message"]

    def test_api_logout_requires_login(self, client):
        """Test API logout without login"""
        response = client.post("/api/v1/logout")
        # Should redirect to login
        assert response.status_code == 302


class TestGetCurrentUser:
    """Test get current user endpoint"""

    def test_get_current_user_success(self, client, admin_user):
        """Test getting current user info"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get("/api/v1/users/me")
        assert response.status_code == 200
        data = response.get_json()
        assert data["username"] == "admin"
        assert data["is_admin"] is True
        assert "id" in data
        assert "created_at" in data

    def test_get_current_user_unauthorized(self, client):
        """Test getting current user without login"""
        response = client.get("/api/v1/users/me")
        assert response.status_code == 302  # Redirect to login


class TestChangePassword:
    """Test change password endpoint"""

    def test_change_password_success(self, client, admin_user):
        """Test successful password change"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.put("/api/v1/users/me/password", json={
            "old_password": "admin123",
            "new_password": "newpassword123",
        })
        assert response.status_code == 200
        assert "密码修改成功" in response.get_json()["message"]

        # Verify new password works
        client.post("/api/v1/logout")
        response = client.post("/api/v1/login", json={
            "username": "admin",
            "password": "newpassword123",
        })
        assert response.status_code == 200

    def test_change_password_missing_fields(self, client, admin_user):
        """Test change password with missing fields"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.put("/api/v1/users/me/password", json={
            "old_password": "admin123",
        })
        assert response.status_code == 400
        assert "不能为空" in response.get_json()["error"]

    def test_change_password_wrong_old_password(self, client, admin_user):
        """Test change password with wrong old password"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.put("/api/v1/users/me/password", json={
            "old_password": "wrongpassword",
            "new_password": "newpassword123",
        })
        assert response.status_code == 401
        assert "旧密码错误" in response.get_json()["error"]

    def test_change_password_too_short(self, client, admin_user):
        """Test change password with too short new password"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.put("/api/v1/users/me/password", json={
            "old_password": "admin123",
            "new_password": "short",
        })
        assert response.status_code == 400
        assert "至少为 8 位" in response.get_json()["error"]

    def test_change_password_unauthorized(self, client):
        """Test change password without login"""
        response = client.put("/api/v1/users/me/password", json={
            "old_password": "old",
            "new_password": "newpassword123",
        })
        assert response.status_code == 302  # Redirect to login


class TestListUsers:
    """Test list users endpoint (admin only)"""

    def test_list_users_as_admin(self, client, admin_user):
        """Test listing users as admin"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get("/api/v1/users")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_users_as_non_admin(self, client, admin_user):
        """Test listing users as non-admin fails"""
        # Create non-admin user
        with client.application.app_context():
            user = User(
                username="regular",
                password_hash=bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode(),
                is_admin=False,
            )
            db.session.add(user)
            db.session.commit()

        client.post("/api/v1/login", json={"username": "regular", "password": "password123"})
        response = client.get("/api/v1/users")
        assert response.status_code == 403
        assert "无权访问" in response.get_json()["error"]

    def test_list_users_unauthorized(self, client):
        """Test listing users without login"""
        response = client.get("/api/v1/users")
        assert response.status_code == 302


class TestAdminResetPassword:
    """Test admin reset password endpoint"""

    def test_admin_reset_password_success(self, client, admin_user):
        """Test admin resetting user password"""
        # Create a user to reset
        with client.application.app_context():
            user = User(
                username="toreset",
                password_hash=bcrypt.hashpw(b"oldpass123", bcrypt.gensalt()).decode(),
                is_admin=False,
            )
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post(f"/api/v1/users/{user_id}/reset-password", json={
            "new_password": "newpass123",
        })
        assert response.status_code == 200
        assert "密码重置成功" in response.get_json()["message"]

        # Verify new password works
        response = client.post("/api/v1/login", json={
            "username": "toreset",
            "password": "newpass123",
        })
        assert response.status_code == 200

    def test_admin_reset_password_auto_generate(self, client, admin_user):
        """Test admin resetting password with auto-generation"""
        # Create a user to reset
        with client.application.app_context():
            user = User(
                username="toautoreset",
                password_hash=bcrypt.hashpw(b"oldpass123", bcrypt.gensalt()).decode(),
                is_admin=False,
            )
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post(f"/api/v1/users/{user_id}/reset-password", json={})
        assert response.status_code == 200
        data = response.get_json()
        assert "new_password" in data
        assert len(data["new_password"]) >= 16  # Auto-generated password

    def test_admin_reset_password_too_short(self, client, admin_user):
        """Test admin resetting with too short password"""
        with client.application.app_context():
            user = User(
                username="toshort",
                password_hash=bcrypt.hashpw(b"oldpass123", bcrypt.gensalt()).decode(),
                is_admin=False,
            )
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post(f"/api/v1/users/{user_id}/reset-password", json={
            "new_password": "short",
        })
        assert response.status_code == 400
        assert "至少为 8 位" in response.get_json()["error"]

    def test_admin_reset_password_non_admin(self, client, admin_user):
        """Test non-admin cannot reset passwords"""
        with client.application.app_context():
            user1 = User(
                username="regular1",
                password_hash=bcrypt.hashpw(b"pass123", bcrypt.gensalt()).decode(),
                is_admin=False,
            )
            user2 = User(
                username="regular2",
                password_hash=bcrypt.hashpw(b"pass123", bcrypt.gensalt()).decode(),
                is_admin=False,
            )
            db.session.add_all([user1, user2])
            db.session.commit()
            user2_id = user2.id

        client.post("/api/v1/login", json={"username": "regular1", "password": "pass123"})
        response = client.post(f"/api/v1/users/{user2_id}/reset-password", json={
            "new_password": "newpass123",
        })
        assert response.status_code == 403

    def test_admin_reset_password_user_not_found(self, client, admin_user):
        """Test resetting password for non-existent user"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post("/api/v1/users/99999/reset-password", json={
            "new_password": "newpass123",
        })
        assert response.status_code == 404


def test_api_login_success_basic(client, admin_user):
    resp = client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["username"] == "admin"
    assert data["is_admin"] is True


def test_api_login_failure_basic(client):
    resp = client.post("/api/v1/login", json={"username": "admin", "password": "wrongpass"})
    assert resp.status_code == 401
    assert "错误" in resp.get_json()["error"]


def test_change_password_basic(client, admin_user):
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
