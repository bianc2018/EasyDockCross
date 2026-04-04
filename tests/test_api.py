"""Tests for app/api.py"""
import json
from unittest.mock import MagicMock, patch

import pytest

from app.extensions import db


class TestHealthAPI:
    """Test health check APIs"""

    def test_health_check(self, client):
        """Test basic health check"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "EasyDockCross"

    def test_health_dependencies(self, client, admin_user):
        """Test dependencies health check"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})

        with patch('app.api.DockerDependencyChecker') as mock_checker_class:
            mock_checker = MagicMock()
            mock_checker.check_all.return_value = {
                "docker": {"status": "ok", "version": "24.0.0"},
                "python": {"status": "ok", "version": "3.10.0"},
            }
            mock_checker_class.return_value = mock_checker

            response = client.get("/api/v1/health/dependencies")
            assert response.status_code == 200
            data = response.get_json()
            assert "docker" in data
            assert "python" in data

    def test_health_dependencies_auto_install(self, client, admin_user):
        """Test auto install endpoint"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})

        with patch('app.api.DockerDependencyChecker') as mock_checker_class:
            mock_checker = MagicMock()
            mock_checker.run_auto_install.return_value = {
                "status": "ok",
                "message": "Install success",
            }
            mock_checker_class.return_value = mock_checker

            response = client.post("/api/v1/health/dependencies/install", json={
                "component": "docker",
            })
            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "ok"

    def test_health_dependencies_predownload(self, client, admin_user):
        """Test predownload images endpoint"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})

        with patch('app.api.DockerDependencyChecker') as mock_checker_class:
            mock_checker = MagicMock()
            mock_checker.predownload_images.return_value = [
                {"image": "dockcross/linux-x64", "status": "ok"},
            ]
            mock_checker_class.return_value = mock_checker

            response = client.post("/api/v1/health/images/predownload")
            assert response.status_code == 200
            data = response.get_json()
            assert "results" in data
