"""Tests for app/build.py"""
from datetime import datetime
from unittest.mock import MagicMock, patch, call

import pytest

from app.build import (
    _group_to_dict,
    _task_to_dict,
    _update_group_status,
    BuildScheduler,
    scheduler,
)
from app.extensions import db
from app.models import BuildGroup, BuildTask, BuildTarget, Project


class TestGroupToDict:
    """Test _group_to_dict function"""

    def test_group_to_dict(self, app):
        """Test converting BuildGroup to dictionary"""
        with app.app_context():
            group = BuildGroup(
                id=1,
                project_id=2,
                trigger_type="manual",
                status="running",
                created_at=datetime(2024, 1, 1, 12, 0, 0),
                completed_at=None,
            )
            result = _group_to_dict(group)

            assert result["id"] == 1
            assert result["project_id"] == 2
            assert result["trigger_type"] == "manual"
            assert result["status"] == "running"
            assert result["created_at"] == "2024-01-01T12:00:00"
            assert result["completed_at"] is None


class TestTaskToDict:
    """Test _task_to_dict function"""

    def test_task_to_dict(self, app):
        """Test converting BuildTask to dictionary"""
        with app.app_context():
            task = BuildTask(
                id=1,
                project_id=2,
                target_id=3,
                build_group_id=4,
                status="success",
                container_id="abc123",
                start_time=datetime(2024, 1, 1, 12, 0, 0),
                end_time=datetime(2024, 1, 1, 12, 30, 0),
                output_log="build output",
                error_log="",
            )
            result = _task_to_dict(task)

            assert result["id"] == 1
            assert result["project_id"] == 2
            assert result["target_id"] == 3
            assert result["build_group_id"] == 4
            assert result["status"] == "success"
            assert result["container_id"] == "abc123"
            assert result["start_time"] == "2024-01-01T12:00:00"
            assert result["end_time"] == "2024-01-01T12:30:00"
            assert result["output_log"] == "build output"
            assert result["error_log"] == ""


class TestUpdateGroupStatus:
    """Test _update_group_status function"""

    def test_update_group_no_tasks_sets_success(self, app):
        """Test group with no tasks is marked as success"""
        with app.app_context():
            project = Project(name="test", user_id=1)
            db.session.add(project)
            db.session.commit()

            group = BuildGroup(project_id=project.id, status="pending")
            db.session.add(group)
            db.session.commit()

            _update_group_status(group.id)

            updated_group = BuildGroup.query.get(group.id)
            assert updated_group.status == "success"
            assert updated_group.completed_at is not None

    def test_update_group_with_running_task(self, app):
        """Test group with running task stays running"""
        with app.app_context():
            project = Project(name="test", user_id=1)
            db.session.add(project)
            db.session.commit()

            target = BuildTarget(project_id=project.id, name="linux")
            db.session.add(target)
            db.session.commit()

            group = BuildGroup(project_id=project.id, status="pending")
            db.session.add(group)
            db.session.commit()

            task = BuildTask(
                project_id=project.id,
                target_id=target.id,
                build_group_id=group.id,
                status="running",
            )
            db.session.add(task)
            db.session.commit()

            _update_group_status(group.id)

            updated_group = BuildGroup.query.get(group.id)
            assert updated_group.status == "running"

    def test_update_group_all_success(self, app):
        """Test group with all successful tasks"""
        with app.app_context():
            project = Project(name="test", user_id=1)
            db.session.add(project)
            db.session.commit()

            target = BuildTarget(project_id=project.id, name="linux")
            db.session.add(target)
            db.session.commit()

            group = BuildGroup(project_id=project.id, status="running")
            db.session.add(group)
            db.session.commit()

            task1 = BuildTask(
                project_id=project.id,
                target_id=target.id,
                build_group_id=group.id,
                status="success",
            )
            task2 = BuildTask(
                project_id=project.id,
                target_id=target.id,
                build_group_id=group.id,
                status="success",
            )
            db.session.add_all([task1, task2])
            db.session.commit()

            _update_group_status(group.id)

            updated_group = BuildGroup.query.get(group.id)
            assert updated_group.status == "success"
            assert updated_group.completed_at is not None

    def test_update_group_with_failed_task(self, app):
        """Test group with one failed task is marked as failed"""
        with app.app_context():
            project = Project(name="test", user_id=1)
            db.session.add(project)
            db.session.commit()

            target = BuildTarget(project_id=project.id, name="linux")
            db.session.add(target)
            db.session.commit()

            group = BuildGroup(project_id=project.id, status="running")
            db.session.add(group)
            db.session.commit()

            task1 = BuildTask(
                project_id=project.id,
                target_id=target.id,
                build_group_id=group.id,
                status="success",
            )
            task2 = BuildTask(
                project_id=project.id,
                target_id=target.id,
                build_group_id=group.id,
                status="failed",
            )
            db.session.add_all([task1, task2])
            db.session.commit()

            _update_group_status(group.id)

            updated_group = BuildGroup.query.get(group.id)
            assert updated_group.status == "failed"

    def test_update_group_with_cancelled_task(self, app):
        """Test group with cancelled task but no failed"""
        with app.app_context():
            project = Project(name="test", user_id=1)
            db.session.add(project)
            db.session.commit()

            target = BuildTarget(project_id=project.id, name="linux")
            db.session.add(target)
            db.session.commit()

            group = BuildGroup(project_id=project.id, status="running")
            db.session.add(group)
            db.session.commit()

            task1 = BuildTask(
                project_id=project.id,
                target_id=target.id,
                build_group_id=group.id,
                status="success",
            )
            task2 = BuildTask(
                project_id=project.id,
                target_id=target.id,
                build_group_id=group.id,
                status="cancelled",
            )
            db.session.add_all([task1, task2])
            db.session.commit()

            _update_group_status(group.id)

            updated_group = BuildGroup.query.get(group.id)
            assert updated_group.status == "cancelled"


class TestBuildScheduler:
    """Test BuildScheduler class"""

    def test_scheduler_init(self, app):
        """Test scheduler initialization"""
        with app.app_context():
            sched = BuildScheduler()
            assert sched.max_concurrent == 3
            assert sched.timeout_seconds == 7200
            assert sched._semaphore is not None

    def test_scheduler_init_app(self, app):
        """Test scheduler init with app config"""
        with app.app_context():
            sched = BuildScheduler()
            sched.init_app(app)
            # Default values from config
            assert sched.max_concurrent == 3

    def test_cancel_task_not_found(self, app):
        """Test cancel_task returns False for non-existent task"""
        with app.app_context():
            sched = BuildScheduler(app)
            result = sched.cancel_task(99999)
            assert result is False

    def test_cancel_task_already_finished(self, app):
        """Test cancel_task returns False for already finished task"""
        with app.app_context():
            project = Project(name="test", user_id=1)
            db.session.add(project)
            db.session.commit()

            target = BuildTarget(project_id=project.id, name="linux")
            db.session.add(target)
            db.session.commit()

            group = BuildGroup(project_id=project.id, status="success")
            db.session.add(group)
            db.session.commit()

            task = BuildTask(
                project_id=project.id,
                target_id=target.id,
                build_group_id=group.id,
                status="success",
            )
            db.session.add(task)
            db.session.commit()

            sched = BuildScheduler(app)
            result = sched.cancel_task(task.id)
            assert result is False

    def test_cancel_task_pending(self, app):
        """Test cancel_task for pending task"""
        with app.app_context():
            project = Project(name="test", user_id=1)
            db.session.add(project)
            db.session.commit()

            target = BuildTarget(project_id=project.id, name="linux")
            db.session.add(target)
            db.session.commit()

            group = BuildGroup(project_id=project.id, status="pending")
            db.session.add(group)
            db.session.commit()

            task = BuildTask(
                project_id=project.id,
                target_id=target.id,
                build_group_id=group.id,
                status="pending",
            )
            db.session.add(task)
            db.session.commit()

            sched = BuildScheduler(app)
            result = sched.cancel_task(task.id)

            assert result is True
            updated_task = BuildTask.query.get(task.id)
            assert updated_task.status == "cancelled"
            assert updated_task.end_time is not None

    def test_cancel_task_running(self, app):
        """Test cancel_task for running task"""
        with app.app_context():
            project = Project(name="test", user_id=1)
            db.session.add(project)
            db.session.commit()

            target = BuildTarget(project_id=project.id, name="linux")
            db.session.add(target)
            db.session.commit()

            group = BuildGroup(project_id=project.id, status="running")
            db.session.add(group)
            db.session.commit()

            task = BuildTask(
                project_id=project.id,
                target_id=target.id,
                build_group_id=group.id,
                status="running",
            )
            db.session.add(task)
            db.session.commit()

            # Add cancel event for the task
            import threading
            sched = BuildScheduler(app)
            sched._cancel_events[task.id] = threading.Event()

            result = sched.cancel_task(task.id)

            assert result is True
            updated_task = BuildTask.query.get(task.id)
            assert updated_task.status == "cancelled"
            assert sched._cancel_events[task.id].is_set()

    def test_submit_group_not_found(self, app):
        """Test submit_group returns False for non-existent group"""
        with app.app_context():
            sched = BuildScheduler(app)
            result = sched.submit_group(99999)
            assert result is False

    def test_submit_group_no_pending_tasks(self, app):
        """Test submit_group with no pending tasks"""
        with app.app_context():
            project = Project(name="test", user_id=1)
            db.session.add(project)
            db.session.commit()

            group = BuildGroup(project_id=project.id, status="pending")
            db.session.add(group)
            db.session.commit()

            sched = BuildScheduler(app)
            result = sched.submit_group(group.id)

            assert result is True
            updated_group = BuildGroup.query.get(group.id)
            assert updated_group.status == "success"


class TestBuildAPIs:
    """Test build blueprint APIs"""

    def test_trigger_build_unauthorized(self, client, admin_user):
        """Test triggering build without permission"""
        # Create a project owned by another user
        from app.models import User
        from app.extensions import db
        import bcrypt

        with client.application.app_context():
            other_user = User(username="other", password_hash=bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode())
            db.session.add(other_user)
            db.session.commit()

            project = Project(name="test", user_id=other_user.id)
            db.session.add(project)
            db.session.commit()
            project_id = project.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post(f"/api/v1/projects/{project_id}/build", json={})

        assert response.status_code == 403

    def test_cancel_build_not_found(self, client, admin_user):
        """Test canceling non-existent build"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post("/api/v1/builds/99999/cancel")
        assert response.status_code == 404

    def test_get_build_log_not_found(self, client, admin_user):
        """Test getting log for non-existent build"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get("/api/v1/builds/99999/log")
        assert response.status_code == 404

    def test_list_builds_unauthorized(self, client):
        """Test listing builds without login"""
        response = client.get("/api/v1/builds")
        assert response.status_code == 302  # Redirect to login

    def test_get_build_group_not_found(self, client, admin_user):
        """Test getting non-existent build group"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get("/api/v1/builds/99999")
        assert response.status_code == 404

    def test_get_build_group_tasks_not_found(self, client, admin_user):
        """Test getting tasks for non-existent build group"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get("/api/v1/builds/99999/tasks")
        assert response.status_code == 404


class TestBuildRoutes:
    """Test build blueprint routes"""

    def test_list_builds_empty(self, client, admin_user):
        """Test listing builds with no builds"""
        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.get("/api/v1/builds")

        assert response.status_code == 200
        data = response.get_json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_trigger_build_no_targets(self, client, admin_user):
        """Test triggering build with no targets defined"""
        with client.application.app_context():
            from app.models import User
            user = User.query.filter_by(username="admin").first()
            project = Project(name="test", user_id=user.id)
            from app.extensions import db
            db.session.add(project)
            db.session.commit()
            project_id = project.id

        client.post("/api/v1/login", json={"username": "admin", "password": "admin123"})
        response = client.post(f"/api/v1/projects/{project_id}/build", json={})

        assert response.status_code == 400
        assert "没有可用的构建目标" in response.get_json()["error"]
