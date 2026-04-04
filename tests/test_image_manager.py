"""Tests for app/image_manager.py"""
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.image_manager import (
    _image_to_dict,
    _validate_dockerfile_input,
    generate_dockerfile,
)
from app.models import CustomImage


class TestImageToDict:
    """Test _image_to_dict function"""

    def test_image_to_dict(self, app):
        """Test converting CustomImage to dictionary"""
        with app.app_context():
            image = CustomImage(
                id=1,
                name="test-image",
                description="Test description",
                base_image="ubuntu:22.04",
                config_yaml='{"packages": ["git"]}',
                generated_dockerfile="FROM ubuntu:22.04",
                status="ready",
                image_id="abc123",
                build_log="Build successful",
                created_at=datetime(2024, 1, 1, 12, 0, 0),
                updated_at=datetime(2024, 1, 2, 12, 0, 0),
            )
            result = _image_to_dict(image)

            assert result["id"] == 1
            assert result["name"] == "test-image"
            assert result["description"] == "Test description"
            assert result["base_image"] == "ubuntu:22.04"
            assert result["config_yaml"] == '{"packages": ["git"]}'
            assert result["generated_dockerfile"] == "FROM ubuntu:22.04"
            assert result["status"] == "ready"
            assert result["image_id"] == "abc123"
            assert result["build_log"] == "Build successful"
            assert result["created_at"] == "2024-01-01T12:00:00"
            assert result["updated_at"] == "2024-01-02T12:00:00"


class TestValidateDockerfileInput:
    """Test _validate_dockerfile_input function"""

    def test_valid_input(self):
        """Test valid Dockerfile input"""
        config = {
            "system_packages": ["git", "curl"],
            "tools": ["make"],
            "env_vars": {"KEY": "value"},
            "pre_build_script": "echo hello",
        }
        # Should not raise
        _validate_dockerfile_input("ubuntu:22.04", config)

    def test_invalid_base_image_with_newline(self):
        """Test base image with newline is rejected"""
        config = {"system_packages": []}
        with pytest.raises(ValueError) as exc_info:
            _validate_dockerfile_input("ubuntu:22.04\nRUN evil", config)
        assert "基础镜像格式无效" in str(exc_info.value)

    def test_invalid_base_image_with_space(self):
        """Test base image with space is rejected"""
        config = {"system_packages": []}
        with pytest.raises(ValueError) as exc_info:
            _validate_dockerfile_input("ubuntu 22.04", config)
        assert "基础镜像格式无效" in str(exc_info.value)

    def test_invalid_package_with_semicolon(self):
        """Test package with semicolon is rejected"""
        config = {"system_packages": ["git; rm -rf /"]}
        with pytest.raises(ValueError) as exc_info:
            _validate_dockerfile_input("ubuntu:22.04", config)
        assert "非法的系统依赖包" in str(exc_info.value)

    def test_invalid_package_with_pipe(self):
        """Test package with pipe is rejected"""
        config = {"system_packages": ["git | cat"]}
        with pytest.raises(ValueError) as exc_info:
            _validate_dockerfile_input("ubuntu:22.04", config)
        assert "非法的系统依赖包" in str(exc_info.value)

    def test_invalid_package_with_ampersand(self):
        """Test package with ampersand is rejected"""
        config = {"system_packages": ["git && rm -rf /"]}
        with pytest.raises(ValueError) as exc_info:
            _validate_dockerfile_input("ubuntu:22.04", config)
        assert "非法的系统依赖包" in str(exc_info.value)

    def test_invalid_tool(self):
        """Test invalid tool name is rejected"""
        config = {"tools": ["make; evil"]}
        with pytest.raises(ValueError) as exc_info:
            _validate_dockerfile_input("ubuntu:22.04", config)
        assert "非法的开发工具" in str(exc_info.value)

    def test_invalid_env_var_name(self):
        """Test invalid env var name is rejected"""
        config = {"env_vars": {"123_INVALID": "value"}}
        with pytest.raises(ValueError) as exc_info:
            _validate_dockerfile_input("ubuntu:22.04", config)
        assert "非法的环境变量名" in str(exc_info.value)

    def test_env_var_with_newline(self):
        """Test env var value with newline is rejected"""
        config = {"env_vars": {"KEY": "value\nevil"}}
        with pytest.raises(ValueError) as exc_info:
            _validate_dockerfile_input("ubuntu:22.04", config)
        assert "环境变量值不能包含换行" in str(exc_info.value)

    def test_pre_build_with_newline(self):
        """Test pre-build script with newline is rejected"""
        config = {"pre_build_script": "echo hello\nevil"}
        with pytest.raises(ValueError) as exc_info:
            _validate_dockerfile_input("ubuntu:22.04", config)
        assert "预构建脚本不能包含换行符" in str(exc_info.value)


class TestGenerateDockerfile:
    """Test generate_dockerfile function"""

    def test_basic_dockerfile(self):
        """Test basic Dockerfile generation"""
        config = {}
        result = generate_dockerfile("ubuntu:22.04", config)

        assert result.startswith("FROM ubuntu:22.04")
        assert "RUN" not in result or result.count("\n") == 1

    def test_dockerfile_with_packages(self):
        """Test Dockerfile with system packages"""
        config = {"system_packages": ["git", "curl", "wget"]}
        result = generate_dockerfile("ubuntu:22.04", config)

        assert "FROM ubuntu:22.04" in result
        assert "apt-get update" in result
        assert "git curl wget" in result

    def test_dockerfile_with_tools(self):
        """Test Dockerfile with development tools"""
        config = {"tools": ["make", "gcc"]}
        result = generate_dockerfile("ubuntu:22.04", config)

        assert "make gcc" in result

    def test_dockerfile_with_ccache(self):
        """Test Dockerfile with ccache enabled"""
        config = {"use_ccache": True}
        result = generate_dockerfile("ubuntu:22.04", config)

        assert "ccache" in result
        assert "CCACHE_DIR=/ccache" in result

    def test_dockerfile_with_env_vars(self):
        """Test Dockerfile with environment variables"""
        config = {"env_vars": {"KEY1": "value1", "KEY2": "value with spaces"}}
        result = generate_dockerfile("ubuntu:22.04", config)

        assert "ENV KEY1=value1" in result
        # Should use shlex.quote for values with spaces
        assert "ENV KEY2=" in result

    def test_dockerfile_with_pre_build(self):
        """Test Dockerfile with pre-build script"""
        config = {"pre_build_script": "mkdir -p /work"}
        result = generate_dockerfile("ubuntu:22.04", config)

        assert "RUN mkdir -p /work" in result

    def test_complete_dockerfile(self):
        """Test complete Dockerfile with all options"""
        config = {
            "system_packages": ["git"],
            "tools": ["make"],
            "use_ccache": True,
            "env_vars": {"CC": "gcc"},
            "pre_build_script": "echo ready",
        }
        result = generate_dockerfile("ubuntu:22.04", config)

        assert result.startswith("FROM ubuntu:22.04")
        assert "apt-get" in result
        assert "ccache" in result
        assert "ENV CC=gcc" in result
        assert "echo ready" in result


class TestImageAPIs:
    """Test image blueprint APIs"""

    def test_list_images_empty(self, client, admin_user):
        """Test listing images when none exist"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get("/api/v1/images")

        assert response.status_code == 200
        data = response.get_json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_images_with_data(self, client, admin_user):
        """Test listing images with data"""
        with client.application.app_context():
            from app.extensions import db
            image = CustomImage(
                name="test-image",
                base_image="ubuntu:22.04",
                config_yaml="{}",
                generated_dockerfile="FROM ubuntu:22.04",
                status="ready",
            )
            db.session.add(image)
            db.session.commit()

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get("/api/v1/images")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "test-image"

    def test_create_image_success(self, client, admin_user):
        """Test creating an image successfully"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post("/api/v1/images", json={
            "name": "my-image",
            "base_image": "ubuntu:22.04",
            "description": "My custom image",
            "mode": "simple",
            "config": {"system_packages": ["git"]},
        })

        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "my-image"
        assert data["base_image"] == "ubuntu:22.04"
        assert data["status"] == "ready"
        assert "git" in data["generated_dockerfile"]

    def test_create_image_missing_name(self, client, admin_user):
        """Test creating an image without name fails"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post("/api/v1/images", json={
            "base_image": "ubuntu:22.04",
        })

        assert response.status_code == 400
        assert "名称和基础镜像不能为空" in response.get_json()["error"]

    def test_create_image_duplicate_name(self, client, admin_user):
        """Test creating image with duplicate name fails"""
        with client.application.app_context():
            from app.extensions import db
            image = CustomImage(
                name="existing-image",
                base_image="ubuntu:22.04",
                config_yaml="{}",
                generated_dockerfile="FROM ubuntu:22.04",
                status="ready",
            )
            db.session.add(image)
            db.session.commit()

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post("/api/v1/images", json={
            "name": "existing-image",
            "base_image": "debian:11",
        })

        assert response.status_code == 409
        assert "镜像名称已存在" in response.get_json()["error"]

    def test_get_image_not_found(self, client, admin_user):
        """Test getting non-existent image"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get("/api/v1/images/99999")

        assert response.status_code == 404

    def test_get_image_success(self, client, admin_user):
        """Test getting an existing image"""
        with client.application.app_context():
            from app.extensions import db
            image = CustomImage(
                name="test-image",
                base_image="ubuntu:22.04",
                config_yaml="{}",
                generated_dockerfile="FROM ubuntu:22.04",
                status="ready",
            )
            db.session.add(image)
            db.session.commit()
            image_id = image.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get(f"/api/v1/images/{image_id}")

        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "test-image"

    def test_update_image_success(self, client, admin_user):
        """Test updating an image"""
        with client.application.app_context():
            from app.extensions import db
            image = CustomImage(
                name="old-name",
                base_image="ubuntu:20.04",
                config_yaml='{"old": "config"}',
                generated_dockerfile="FROM ubuntu:20.04",
                status="ready",
            )
            db.session.add(image)
            db.session.commit()
            image_id = image.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.put(f"/api/v1/images/{image_id}", json={
            "name": "new-name",
            "base_image": "ubuntu:22.04",
            "mode": "simple",
            "config": {},
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "new-name"
        assert data["base_image"] == "ubuntu:22.04"

    def test_update_image_duplicate_name(self, client, admin_user):
        """Test updating with duplicate name fails"""
        with client.application.app_context():
            from app.extensions import db
            image1 = CustomImage(
                name="image-1",
                base_image="ubuntu:22.04",
                config_yaml="{}",
                generated_dockerfile="FROM ubuntu:22.04",
                status="ready",
            )
            image2 = CustomImage(
                name="image-2",
                base_image="debian:11",
                config_yaml="{}",
                generated_dockerfile="FROM debian:11",
                status="ready",
            )
            db.session.add_all([image1, image2])
            db.session.commit()
            image2_id = image2.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.put(f"/api/v1/images/{image2_id}", json={
            "name": "image-1",
        })

        assert response.status_code == 409
        assert "镜像名称已存在" in response.get_json()["error"]

    def test_delete_image_success(self, client, admin_user):
        """Test deleting an image"""
        with client.application.app_context():
            from app.extensions import db
            image = CustomImage(
                name="to-delete",
                base_image="ubuntu:22.04",
                config_yaml="{}",
                generated_dockerfile="FROM ubuntu:22.04",
                status="ready",
            )
            db.session.add(image)
            db.session.commit()
            image_id = image.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.delete(f"/api/v1/images/{image_id}")

        assert response.status_code == 200
        assert "删除成功" in response.get_json()["message"]

        # Verify it's deleted
        response = client.get(f"/api/v1/images/{image_id}")
        assert response.status_code == 404

    def test_delete_image_not_found(self, client, admin_user):
        """Test deleting non-existent image"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.delete("/api/v1/images/99999")

        assert response.status_code == 404

    def test_preview_dockerfile_success(self, client, admin_user):
        """Test previewing Dockerfile generation"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post("/api/v1/images/preview", json={
            "base_image": "ubuntu:22.04",
            "config": {"system_packages": ["git", "curl"]},
        })

        assert response.status_code == 200
        data = response.get_json()
        assert "dockerfile" in data
        assert "FROM ubuntu:22.04" in data["dockerfile"]
        assert "git curl" in data["dockerfile"]

    def test_preview_dockerfile_missing_base(self, client, admin_user):
        """Test preview without base image fails"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post("/api/v1/images/preview", json={
            "config": {},
        })

        assert response.status_code == 400
        assert "基础镜像不能为空" in response.get_json()["error"]

    def test_build_image_not_found(self, client, admin_user):
        """Test building non-existent image"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post("/api/v1/images/99999/build")

        assert response.status_code == 404

    def test_build_image_no_dockerfile(self, client, admin_user):
        """Test building image without Dockerfile"""
        with client.application.app_context():
            from app.extensions import db
            image = CustomImage(
                name="no-dockerfile",
                base_image="ubuntu:22.04",
                config_yaml="{}",
                generated_dockerfile="",
                status="ready",
            )
            db.session.add(image)
            db.session.commit()
            image_id = image.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post(f"/api/v1/images/{image_id}/build")

        assert response.status_code == 400
        assert "未生成 Dockerfile" in response.get_json()["error"]

    def test_build_image_already_building(self, client, admin_user):
        """Test building image that's already building"""
        with client.application.app_context():
            from app.extensions import db
            image = CustomImage(
                name="building",
                base_image="ubuntu:22.04",
                config_yaml="{}",
                generated_dockerfile="FROM ubuntu:22.04",
                status="building",
            )
            db.session.add(image)
            db.session.commit()
            image_id = image.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post(f"/api/v1/images/{image_id}/build")

        assert response.status_code == 409
        assert "正在构建中" in response.get_json()["error"]

    def test_get_build_log_not_found(self, client, admin_user):
        """Test getting build log for non-existent image"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get("/api/v1/images/99999/build-log")

        assert response.status_code == 404

    def test_get_build_log_success(self, client, admin_user):
        """Test getting build log for existing image"""
        with client.application.app_context():
            from app.extensions import db
            image = CustomImage(
                name="test",
                base_image="ubuntu:22.04",
                config_yaml="{}",
                generated_dockerfile="FROM ubuntu:22.04",
                status="ready",
                build_log="Build successful!",
            )
            db.session.add(image)
            db.session.commit()
            image_id = image.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get(f"/api/v1/images/{image_id}/build-log")

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ready"
        assert data["build_log"] == "Build successful!"
