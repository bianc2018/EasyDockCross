"""Tests for app/models.py"""
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app.extensions import db
from app.models import (
    User, Project, BuildTarget, BuildGroup, BuildTask,
    BuildArtifact, CustomImage, DependencyCheck
)


class TestUserModel:
    """Test User model"""

    def test_user_creation(self, app):
        """Test creating a user"""
        with app.app_context():
            user = User(
                username="testuser",
                password_hash="hashed_password",
                is_admin=False,
            )
            db.session.add(user)
            db.session.commit()

            assert user.id is not None
            assert user.username == "testuser"
            assert user.is_admin is False
            assert user.created_at is not None

    def test_user_repr(self, app):
        """Test User __repr__"""
        with app.app_context():
            user = User(username="testuser", password_hash="hash")
            assert repr(user) == "<User testuser>"

    def test_user_projects_relationship(self, app):
        """Test User projects relationship"""
        with app.app_context():
            user = User(username="testuser", password_hash="hash")
            db.session.add(user)
            db.session.commit()

            project = Project(name="test", user_id=user.id)
            db.session.add(project)
            db.session.commit()

            # Check relationship
            assert user.projects.count() == 1
            assert user.projects.first().name == "test"


class TestProjectModel:
    """Test Project model"""

    def test_project_creation(self, app):
        """Test creating a project"""
        with app.app_context():
            user = User(username="testuser", password_hash="hash")
            db.session.add(user)
            db.session.commit()

            project = Project(
                name="test-project",
                description="Test description",
                user_id=user.id,
                source_type="git",
                source_url="https://github.com/user/repo.git",
                source_branch="main",
                triggers={"webhook": True},
            )
            db.session.add(project)
            db.session.commit()

            assert project.id is not None
            assert project.name == "test-project"
            assert project.source_type == "git"
            assert project.created_at is not None
            assert project.updated_at is not None

    def test_project_repr(self, app):
        """Test Project __repr__"""
        with app.app_context():
            project = Project(name="test", user_id=1)
            assert repr(project) == "<Project test>"

    def test_project_targets_relationship(self, app):
        """Test Project targets relationship"""
        with app.app_context():
            user = User(username="testuser", password_hash="hash")
            db.session.add(user)
            db.session.commit()

            project = Project(name="test", user_id=user.id)
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

            assert len(project.targets) == 1
            assert project.targets[0].name == "linux"

    def test_project_unique_constraint(self, app):
        """Test project name unique constraint per user"""
        with app.app_context():
            user = User(username="testuser", password_hash="hash")
            db.session.add(user)
            db.session.commit()

            project1 = Project(name="same", user_id=user.id)
            db.session.add(project1)
            db.session.commit()

            # Same name, same user should fail
            project2 = Project(name="same", user_id=user.id)
            db.session.add(project2)
            with pytest.raises(Exception):
                db.session.commit()
            db.session.rollback()

            # Same name, different user should succeed
            user2 = User(username="testuser2", password_hash="hash")
            db.session.add(user2)
            db.session.commit()

            project3 = Project(name="same", user_id=user2.id)
            db.session.add(project3)
            db.session.commit()


class TestBuildTargetModel:
    """Test BuildTarget model"""

    def test_target_creation(self, app):
        """Test creating a build target"""
        with app.app_context():
            user = User(username="testuser", password_hash="hash")
            db.session.add(user)
            db.session.commit()

            project = Project(name="test", user_id=user.id)
            db.session.add(project)
            db.session.commit()

            target = BuildTarget(
                project_id=project.id,
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
            db.session.add(target)
            db.session.commit()

            assert target.id is not None
            assert target.name == "linux-amd64"
            assert target.output_type == "binary"

    def test_target_repr(self, app):
        """Test BuildTarget __repr__"""
        with app.app_context():
            target = BuildTarget(
                project_id=1,
                name="test-target",
                image="img",
                build_command="cmd",
            )
            assert repr(target) == "<BuildTarget test-target>"

    def test_target_default_values(self, app):
        """Test BuildTarget default values"""
        with app.app_context():
            user = User(username="testuser", password_hash="hash")
            db.session.add(user)
            db.session.commit()

            project = Project(name="test", user_id=user.id)
            db.session.add(project)
            db.session.commit()

            target = BuildTarget(
                project_id=project.id,
                name="test",
                image="img",
                build_command="cmd",
            )
            db.session.add(target)
            db.session.commit()

            assert target.output_type == "binary"
            assert target.env_vars == {}


class TestBuildGroupModel:
    """Test BuildGroup model"""

    def test_group_creation(self, app):
        """Test creating a build group"""
        with app.app_context():
            user = User(username="testuser", password_hash="hash")
            db.session.add(user)
            db.session.commit()

            project = Project(name="test", user_id=user.id)
            db.session.add(project)
            db.session.commit()

            group = BuildGroup(
                project_id=project.id,
                trigger_type="manual",
                status="pending",
            )
            db.session.add(group)
            db.session.commit()

            assert group.id is not None
            assert group.trigger_type == "manual"
            assert group.status == "pending"
            assert group.created_at is not None

    def test_group_repr(self, app):
        """Test BuildGroup __repr__"""
        with app.app_context():
            group = BuildGroup(project_id=1, status="running")
            assert repr(group) == "<BuildGroup None running>"

    def test_group_default_values(self, app):
        """Test BuildGroup default values"""
        with app.app_context():
            user = User(username="testuser", password_hash="hash")
            db.session.add(user)
            db.session.commit()

            project = Project(name="test", user_id=user.id)
            db.session.add(project)
            db.session.commit()

            group = BuildGroup(project_id=project.id)
            db.session.add(group)
            db.session.commit()

            assert group.trigger_type == "manual"
            assert group.status == "pending"


class TestBuildTaskModel:
    """Test BuildTask model"""

    def test_task_creation(self, app):
        """Test creating a build task"""
        with app.app_context():
            user = User(username="testuser", password_hash="hash")
            db.session.add(user)
            db.session.commit()

            project = Project(name="test", user_id=user.id)
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

            group = BuildGroup(project_id=project.id)
            db.session.add(group)
            db.session.commit()

            task = BuildTask(
                project_id=project.id,
                target_id=target.id,
                build_group_id=group.id,
                status="pending",
                container_id="abc123",
            )
            db.session.add(task)
            db.session.commit()

            assert task.id is not None
            assert task.status == "pending"
            assert task.container_id == "abc123"

    def test_task_repr(self, app):
        """Test BuildTask __repr__"""
        with app.app_context():
            task = BuildTask(
                project_id=1,
                target_id=1,
                build_group_id=1,
                status="running",
            )
            assert repr(task) == "<BuildTask None running>"

    def test_task_default_values(self, app):
        """Test BuildTask default values"""
        with app.app_context():
            user = User(username="testuser", password_hash="hash")
            db.session.add(user)
            db.session.commit()

            project = Project(name="test", user_id=user.id)
            db.session.add(project)
            db.session.commit()

            target = BuildTarget(
                project_id=project.id,
                name="linux",
                image="img",
                build_command="cmd",
            )
            db.session.add(target)
            db.session.commit()

            group = BuildGroup(project_id=project.id)
            db.session.add(group)
            db.session.commit()

            task = BuildTask(
                project_id=project.id,
                target_id=target.id,
                build_group_id=group.id,
            )
            db.session.add(task)
            db.session.commit()

            assert task.status == "pending"


class TestBuildArtifactModel:
    """Test BuildArtifact model"""

    def test_artifact_creation(self, app):
        """Test creating a build artifact"""
        with app.app_context():
            user = User(username="testuser", password_hash="hash")
            db.session.add(user)
            db.session.commit()

            project = Project(name="test", user_id=user.id)
            db.session.add(project)
            db.session.commit()

            target = BuildTarget(
                project_id=project.id,
                name="linux",
                image="img",
                build_command="cmd",
            )
            db.session.add(target)
            db.session.commit()

            group = BuildGroup(project_id=project.id)
            db.session.add(group)
            db.session.commit()

            task = BuildTask(
                project_id=project.id,
                target_id=target.id,
                build_group_id=group.id,
            )
            db.session.add(task)
            db.session.commit()

            artifact = BuildArtifact(
                build_task_id=task.id,
                file_path="output/binary",
                file_size=1024,
                download_url="/api/v1/artifacts/1/download/output/binary",
            )
            db.session.add(artifact)
            db.session.commit()

            assert artifact.id is not None
            assert artifact.file_path == "output/binary"
            assert artifact.file_size == 1024

    def test_artifact_repr(self, app):
        """Test BuildArtifact __repr__"""
        with app.app_context():
            artifact = BuildArtifact(
                build_task_id=1,
                file_path="output/binary",
            )
            assert repr(artifact) == "<BuildArtifact output/binary>"


class TestCustomImageModel:
    """Test CustomImage model"""

    def test_image_creation(self, app):
        """Test creating a custom image"""
        with app.app_context():
            image = CustomImage(
                name="my-image",
                description="My custom image",
                base_image="ubuntu:22.04",
                config_yaml="{}",
                generated_dockerfile="FROM ubuntu:22.04",
                status="ready",
            )
            db.session.add(image)
            db.session.commit()

            assert image.id is not None
            assert image.name == "my-image"
            assert image.status == "ready"
            assert image.created_at is not None
            assert image.updated_at is not None

    def test_image_repr(self, app):
        """Test CustomImage __repr__"""
        with app.app_context():
            image = CustomImage(name="test-image")
            assert repr(image) == "<CustomImage test-image>"

    def test_image_default_status(self, app):
        """Test CustomImage default status"""
        with app.app_context():
            image = CustomImage(
                name="test",
                base_image="ubuntu:22.04",
                config_yaml="{}",
            )
            db.session.add(image)
            db.session.commit()

            assert image.status == "building"


class TestDependencyCheckModel:
    """Test DependencyCheck model"""

    def test_check_creation(self, app):
        """Test creating a dependency check record"""
        with app.app_context():
            check = DependencyCheck(
                component="docker",
                status="ok",
                version="24.0.0",
                message="Docker is running",
                install_command=None,
            )
            db.session.add(check)
            db.session.commit()

            assert check.id is not None
            assert check.component == "docker"
            assert check.status == "ok"
            assert check.checked_at is not None

    def test_check_repr(self, app):
        """Test DependencyCheck __repr__"""
        with app.app_context():
            check = DependencyCheck(component="docker", status="ok")
            assert repr(check) == "<DependencyCheck docker ok>"
