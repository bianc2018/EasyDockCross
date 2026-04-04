"""Tests for app/project.py"""
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.extensions import db
from app.models import Project, BuildTarget, User
from app.project import _project_to_dict, _target_to_dict


class TestProjectToDict:
    """Test _project_to_dict function"""

    def test_project_to_dict(self, app):
        """Test converting Project to dictionary"""
        with app.app_context():
            project = Project(
                id=1,
                name="test-project",
                description="Test description",
                source_type="git",
                source_url="https://github.com/user/repo.git",
                source_branch="main",
                triggers={"webhook": True},
                preset_key="go-linux",
                user_id=2,
                created_at=datetime(2024, 1, 1, 12, 0, 0),
                updated_at=datetime(2024, 1, 2, 12, 0, 0),
            )
            result = _project_to_dict(project)

            assert result["id"] == 1
            assert result["name"] == "test-project"
            assert result["description"] == "Test description"
            assert result["source_type"] == "git"
            assert result["source_url"] == "https://github.com/user/repo.git"
            assert result["source_branch"] == "main"
            assert result["triggers"] == {"webhook": True}
            assert result["preset_key"] == "go-linux"
            assert result["user_id"] == 2
            assert result["created_at"] == "2024-01-01T12:00:00"
            assert result["updated_at"] == "2024-01-02T12:00:00"


class TestTargetToDict:
    """Test _target_to_dict function"""

    def test_target_to_dict(self, app):
        """Test converting BuildTarget to dictionary"""
        with app.app_context():
            target = BuildTarget(
                id=1,
                project_id=2,
                name="linux-amd64",
                output_type="binary",
                os="linux",
                distro="ubuntu",
                arch="x86_64",
                image="dockcross/linux-x64",
                build_command="make build",
                build_tool="make",
                env_vars={"CC": "gcc"},
                artifacts_path="dist/",
            )
            result = _target_to_dict(target)

            assert result["id"] == 1
            assert result["project_id"] == 2
            assert result["name"] == "linux-amd64"
            assert result["output_type"] == "binary"
            assert result["os"] == "linux"
            assert result["distro"] == "ubuntu"
            assert result["arch"] == "x86_64"
            assert result["image"] == "dockcross/linux-x64"
            assert result["build_command"] == "make build"
            assert result["build_tool"] == "make"
            assert result["env_vars"] == {"CC": "gcc"}
            assert result["artifacts_path"] == "dist/"


class TestPresetAPIs:
    """Test preset template APIs"""

    def test_list_presets(self, client, admin_user):
        """Test listing presets"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get("/api/v1/presets")

        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_get_preset_not_found(self, client, admin_user):
        """Test getting non-existent preset"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get("/api/v1/presets/nonexistent")

        assert response.status_code == 404
        assert "预设模板不存在" in response.get_json()["error"]


class TestProjectCRUD:
    """Test Project CRUD APIs"""

    def test_list_projects_empty(self, client, admin_user):
        """Test listing projects when none exist"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get("/api/v1/projects")

        assert response.status_code == 200
        data = response.get_json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_projects_with_data(self, client, admin_user):
        """Test listing projects with data"""
        with client.application.app_context():
            user = User.query.filter_by(username="admin").first()
            project = Project(name="test-project", user_id=user.id, description="Test")
            db.session.add(project)
            db.session.commit()

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get("/api/v1/projects")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "test-project"

    def test_create_project_success(self, client, admin_user):
        """Test creating a project successfully"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post("/api/v1/projects", json={
            "name": "my-project",
            "description": "My test project",
            "source_type": "git",
            "source_url": "https://github.com/user/repo.git",
            "source_branch": "develop",
        })

        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "my-project"
        assert data["description"] == "My test project"
        assert data["source_type"] == "git"

    def test_create_project_missing_name(self, client, admin_user):
        """Test creating project without name fails"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post("/api/v1/projects", json={
            "description": "No name project",
        })

        assert response.status_code == 400
        assert "项目名称不能为空" in response.get_json()["error"]

    def test_create_project_duplicate_name(self, client, admin_user):
        """Test creating project with duplicate name fails"""
        with client.application.app_context():
            user = User.query.filter_by(username="admin").first()
            project = Project(name="existing", user_id=user.id)
            db.session.add(project)
            db.session.commit()

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post("/api/v1/projects", json={
            "name": "existing",
        })

        assert response.status_code == 409
        assert "项目名称已存在" in response.get_json()["error"]

    def test_create_project_with_targets(self, client, admin_user):
        """Test creating project with targets"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post("/api/v1/projects", json={
            "name": "project-with-targets",
            "targets": [
                {
                    "name": "linux-build",
                    "output_type": "binary",
                    "image": "dockcross/linux-x64",
                    "build_command": "make",
                }
            ],
        })

        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "project-with-targets"

        # Verify target was created
        with client.application.app_context():
            project = Project.query.filter_by(name="project-with-targets").first()
            targets = BuildTarget.query.filter_by(project_id=project.id).all()
            assert len(targets) == 1
            assert targets[0].name == "linux-build"

    def test_get_project_not_found(self, client, admin_user):
        """Test getting non-existent project"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get("/api/v1/projects/99999")

        assert response.status_code == 404

    def test_get_project_success(self, client, admin_user):
        """Test getting existing project"""
        with client.application.app_context():
            user = User.query.filter_by(username="admin").first()
            project = Project(name="get-test", user_id=user.id)
            db.session.add(project)
            db.session.commit()
            project_id = project.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get(f"/api/v1/projects/{project_id}")

        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "get-test"
        assert "targets" in data

    def test_get_project_unauthorized(self, client, admin_user):
        """Test getting project owned by another user"""
        with client.application.app_context():
            import bcrypt
            other_user = User(username="other", password_hash=bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode())
            db.session.add(other_user)
            db.session.commit()

            project = Project(name="private", user_id=other_user.id)
            db.session.add(project)
            db.session.commit()
            project_id = project.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get(f"/api/v1/projects/{project_id}")

        assert response.status_code == 200  # Admin can access any project

    def test_update_project_success(self, client, admin_user):
        """Test updating a project"""
        with client.application.app_context():
            user = User.query.filter_by(username="admin").first()
            project = Project(name="old-name", user_id=user.id, description="Old desc")
            db.session.add(project)
            db.session.commit()
            project_id = project.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.put(f"/api/v1/projects/{project_id}", json={
            "name": "new-name",
            "description": "New desc",
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "new-name"
        assert data["description"] == "New desc"

    def test_update_project_duplicate_name(self, client, admin_user):
        """Test updating project with duplicate name fails"""
        with client.application.app_context():
            user = User.query.filter_by(username="admin").first()
            project1 = Project(name="project-1", user_id=user.id)
            project2 = Project(name="project-2", user_id=user.id)
            db.session.add_all([project1, project2])
            db.session.commit()
            project2_id = project2.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.put(f"/api/v1/projects/{project2_id}", json={
            "name": "project-1",
        })

        assert response.status_code == 409

    def test_update_project_not_found(self, client, admin_user):
        """Test updating non-existent project"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.put("/api/v1/projects/99999", json={"name": "new"})

        assert response.status_code == 404

    def test_delete_project_success(self, client, admin_user):
        """Test deleting a project"""
        with client.application.app_context():
            user = User.query.filter_by(username="admin").first()
            project = Project(name="to-delete", user_id=user.id)
            db.session.add(project)
            db.session.commit()
            project_id = project.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.delete(f"/api/v1/projects/{project_id}")

        assert response.status_code == 200
        assert "删除成功" in response.get_json()["message"]

        # Verify it's deleted
        with client.application.app_context():
            assert Project.query.get(project_id) is None

    def test_delete_project_not_found(self, client, admin_user):
        """Test deleting non-existent project"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.delete("/api/v1/projects/99999")

        assert response.status_code == 404


class TestTargetCRUD:
    """Test Build Target CRUD APIs"""

    def test_list_targets(self, client, admin_user):
        """Test listing targets for a project"""
        with client.application.app_context():
            user = User.query.filter_by(username="admin").first()
            project = Project(name="target-test", user_id=user.id)
            db.session.add(project)
            db.session.commit()

            target = BuildTarget(
                project_id=project.id,
                name="linux-build",
                image="dockcross/linux-x64",
                build_command="make",
            )
            db.session.add(target)
            db.session.commit()
            project_id = project.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get(f"/api/v1/projects/{project_id}/targets")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]["name"] == "linux-build"

    def test_create_target_success(self, client, admin_user):
        """Test creating a target"""
        with client.application.app_context():
            user = User.query.filter_by(username="admin").first()
            project = Project(name="target-create", user_id=user.id)
            db.session.add(project)
            db.session.commit()
            project_id = project.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post(f"/api/v1/projects/{project_id}/targets", json={
            "name": "arm-build",
            "image": "dockcross/linux-arm64",
            "build_command": "make ARCH=arm64",
            "output_type": "binary",
            "os": "linux",
            "arch": "arm64",
        })

        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "arm-build"
        assert data["image"] == "dockcross/linux-arm64"

    def test_create_target_missing_fields(self, client, admin_user):
        """Test creating target with missing required fields"""
        with client.application.app_context():
            user = User.query.filter_by(username="admin").first()
            project = Project(name="target-missing", user_id=user.id)
            db.session.add(project)
            db.session.commit()
            project_id = project.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post(f"/api/v1/projects/{project_id}/targets", json={
            "name": "incomplete",
        })

        assert response.status_code == 400
        assert "名称、镜像和构建命令不能为空" in response.get_json()["error"]

    def test_get_target_success(self, client, admin_user):
        """Test getting a target"""
        with client.application.app_context():
            user = User.query.filter_by(username="admin").first()
            project = Project(name="target-get", user_id=user.id)
            db.session.add(project)
            db.session.commit()

            target = BuildTarget(
                project_id=project.id,
                name="get-target",
                image="dockcross/linux-x64",
                build_command="make",
            )
            db.session.add(target)
            db.session.commit()
            target_id = target.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get(f"/api/v1/targets/{target_id}")

        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "get-target"

    def test_get_target_not_found(self, client, admin_user):
        """Test getting non-existent target"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get("/api/v1/targets/99999")

        assert response.status_code == 404

    def test_update_target_success(self, client, admin_user):
        """Test updating a target"""
        with client.application.app_context():
            user = User.query.filter_by(username="admin").first()
            project = Project(name="target-update", user_id=user.id)
            db.session.add(project)
            db.session.commit()

            target = BuildTarget(
                project_id=project.id,
                name="old-target",
                image="dockcross/linux-x64",
                build_command="make",
            )
            db.session.add(target)
            db.session.commit()
            target_id = target.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.put(f"/api/v1/targets/{target_id}", json={
            "name": "new-target",
            "build_command": "make clean && make",
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "new-target"
        assert data["build_command"] == "make clean && make"

    def test_delete_target_success(self, client, admin_user):
        """Test deleting a target"""
        with client.application.app_context():
            user = User.query.filter_by(username="admin").first()
            project = Project(name="target-delete", user_id=user.id)
            db.session.add(project)
            db.session.commit()

            target = BuildTarget(
                project_id=project.id,
                name="delete-me",
                image="dockcross/linux-x64",
                build_command="make",
            )
            db.session.add(target)
            db.session.commit()
            target_id = target.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.delete(f"/api/v1/targets/{target_id}")

        assert response.status_code == 200
        assert "删除成功" in response.get_json()["message"]


class TestProjectImportExport:
    """Test YAML import/export APIs"""

    def test_export_project(self, client, admin_user):
        """Test exporting project to YAML"""
        with client.application.app_context():
            user = User.query.filter_by(username="admin").first()
            project = Project(
                name="export-test",
                user_id=user.id,
                description="Test export",
                source_type="git",
                source_url="https://github.com/user/repo.git",
            )
            db.session.add(project)
            db.session.commit()

            target = BuildTarget(
                project_id=project.id,
                name="linux",
                image="dockcross/linux-x64",
                build_command="make",
            )
            db.session.add(target)
            db.session.commit()
            project_id = project.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get(f"/api/v1/projects/{project_id}/export")

        assert response.status_code == 200
        assert response.content_type == "text/yaml; charset=utf-8"
        yaml_content = response.data.decode('utf-8')
        assert "export-test" in yaml_content
        assert "dockcross/linux-x64" in yaml_content

    def test_export_project_not_found(self, client, admin_user):
        """Test exporting non-existent project"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get("/api/v1/projects/99999/export")

        assert response.status_code == 404

    def test_import_project_success(self, client, admin_user):
        """Test importing project from YAML"""
        yaml_content = """
name: imported-project
description: Imported from YAML
source_type: git
source_url: https://github.com/user/repo.git
source_branch: main
triggers:
  webhook: true
targets:
  - name: linux-build
    output_type: binary
    os: linux
    arch: x86_64
    image: dockcross/linux-x64
    build_command: make build
"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post("/api/v1/projects/import",
                               data=yaml_content,
                               content_type="text/yaml")

        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "imported-project"
        assert data["description"] == "Imported from YAML"

    def test_import_project_json_format(self, client, admin_user):
        """Test importing project via JSON"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post("/api/v1/projects/import", json={
            "yaml": """
name: json-imported
source_type: git
source_url: https://github.com/user/repo.git
targets: []
"""
        })

        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "json-imported"

    def test_import_project_empty_yaml(self, client, admin_user):
        """Test importing with empty YAML"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post("/api/v1/projects/import", data="", content_type="text/yaml")

        assert response.status_code == 400
        assert "YAML 内容不能为空" in response.get_json()["error"]

    def test_import_project_invalid_yaml(self, client, admin_user):
        """Test importing with invalid YAML"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post("/api/v1/projects/import", json={
            "yaml": "not: valid: yaml: [",
        })

        assert response.status_code == 400
        assert "YAML 解析失败" in response.get_json()["error"]

    def test_import_project_not_dict(self, client, admin_user):
        """Test importing YAML that doesn't parse to dict"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post("/api/v1/projects/import", data="just a string", content_type="text/yaml")

        assert response.status_code == 400
        assert "YAML 格式不正确" in response.get_json()["error"]

    def test_import_project_missing_name(self, client, admin_user):
        """Test importing without project name"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post("/api/v1/projects/import", data="description: no name", content_type="text/yaml")

        assert response.status_code == 400
        assert "项目名称不能为空" in response.get_json()["error"]

    def test_import_project_duplicate_name(self, client, admin_user):
        """Test importing with duplicate project name"""
        with client.application.app_context():
            user = User.query.filter_by(username="admin").first()
            project = Project(name="existing-import", user_id=user.id)
            db.session.add(project)
            db.session.commit()

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post("/api/v1/projects/import", data="name: existing-import", content_type="text/yaml")

        assert response.status_code == 409
        assert "项目名称已存在" in response.get_json()["error"]


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
