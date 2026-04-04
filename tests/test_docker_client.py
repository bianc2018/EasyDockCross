"""Tests for app/docker_client.py"""
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from app.docker_client import DockerBuildClient
from app.extensions import db
from app.models import BuildTask, BuildTarget, BuildArtifact, Project


class TestDockerBuildClientInit:
    """Test DockerBuildClient initialization"""

    @patch('app.docker_client.docker.DockerClient')
    def test_init_success(self, mock_client_class, app):
        """Test successful initialization"""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client_class.return_value = mock_client

        with app.app_context():
            client = DockerBuildClient()
            assert client.resolver is not None
            assert client.source_manager is not None
            assert client.client is not None

    @patch('app.docker_client.docker.DockerClient')
    def test_init_failure(self, mock_client_class, app):
        """Test initialization when Docker is unavailable"""
        from docker.errors import DockerException
        mock_client_class.side_effect = DockerException("Cannot connect")

        with app.app_context():
            with pytest.raises(RuntimeError) as exc_info:
                DockerBuildClient()
            assert "无法连接到 Docker 守护进程" in str(exc_info.value)


class TestBuildCacheVolumes:
    """Test cache volume building"""

    @patch('app.docker_client.docker.DockerClient')
    def test_build_cache_volumes(self, mock_client_class, app):
        """Test cache volume configuration"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        with app.app_context():
            client = DockerBuildClient()
            volumes = client._build_cache_volumes(project_id=1)

            assert "pip" in str(list(volumes.keys())[0])
            assert "/root/.cache/pip" in volumes.values()
            assert "/root/.npm" in volumes.values()
            assert "/ccache" in volumes.values()


class TestCollectArtifacts:
    """Test artifact collection"""

    @patch('app.docker_client.docker.DockerClient')
    def test_collect_artifacts_empty_dir(self, mock_client_class, app):
        """Test collecting artifacts from empty directory"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        with app.app_context():
            from app.extensions import db
            project = Project(name="test", user_id=1)
            db.session.add(project)
            db.session.commit()

            target = BuildTarget(project_id=project.id, name="linux")
            db.session.add(target)
            db.session.commit()

            group = MagicMock()
            group.id = 1

            task = BuildTask(
                project_id=project.id,
                target_id=target.id,
                build_group_id=1,
                status="running",
            )
            db.session.add(task)
            db.session.commit()

            client = DockerBuildClient()
            artifact_dir = Path("/tmp/test_artifacts")
            artifact_dir.mkdir(parents=True, exist_ok=True)

            client._collect_artifacts(task, artifact_dir)

            # No artifacts should be created
            artifacts = BuildArtifact.query.filter_by(build_task_id=task.id).all()
            assert len(artifacts) == 0

            artifact_dir.rmdir()

    @patch('app.docker_client.docker.DockerClient')
    def test_collect_artifacts_with_files(self, mock_client_class, app):
        """Test collecting artifacts with files"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        with app.app_context():
            from app.extensions import db
            project = Project(name="test", user_id=1)
            db.session.add(project)
            db.session.commit()

            target = BuildTarget(project_id=project.id, name="linux")
            db.session.add(target)
            db.session.commit()

            task = BuildTask(
                project_id=project.id,
                target_id=target.id,
                build_group_id=1,
                status="running",
            )
            db.session.add(task)
            db.session.commit()

            client = DockerBuildClient()
            artifact_dir = Path("/tmp/test_artifacts_2")
            artifact_dir.mkdir(parents=True, exist_ok=True)

            # Create test files
            (artifact_dir / "binary").write_text("test binary content")
            subdir = artifact_dir / "subdir"
            subdir.mkdir()
            (subdir / "file.txt").write_text("text content")

            client._collect_artifacts(task, artifact_dir)

            artifacts = BuildArtifact.query.filter_by(build_task_id=task.id).all()
            assert len(artifacts) == 2

            # Cleanup
            import shutil
            shutil.rmtree(artifact_dir)


class TestStreamLogs:
    """Test log streaming"""

    @patch('app.docker_client.docker.DockerClient')
    def test_stream_logs_success(self, mock_client_class, app):
        """Test successful log streaming"""
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.logs.return_value = [
            b"line1\n",
            b"line2\n",
        ]
        mock_client.containers.get.return_value = mock_container
        mock_client_class.return_value = mock_client

        with app.app_context():
            client = DockerBuildClient()
            logs = list(client.stream_logs("container123"))

            assert logs == ["line1\n", "line2\n"]
            mock_client.containers.get.assert_called_once_with("container123")

    @patch('app.docker_client.docker.DockerClient')
    def test_stream_logs_container_not_found(self, mock_client_class, app):
        """Test log streaming when container not found"""
        mock_client = MagicMock()
        from docker.errors import NotFound
        mock_client.containers.get.side_effect = NotFound("Container not found")
        mock_client_class.return_value = mock_client

        with app.app_context():
            client = DockerBuildClient()
            logs = list(client.stream_logs("container123"))

            assert len(logs) == 1
            assert "容器已不存在" in logs[0]

    @patch('app.docker_client.docker.DockerClient')
    def test_stream_logs_exception(self, mock_client_class, app):
        """Test log streaming with exception"""
        mock_client = MagicMock()
        mock_client.containers.get.side_effect = Exception("Some error")
        mock_client_class.return_value = mock_client

        with app.app_context():
            client = DockerBuildClient()
            logs = list(client.stream_logs("container123"))

            assert len(logs) == 1
            assert "日志流异常" in logs[0]


class TestRunBuild:
    """Test run_build method"""

    @patch('app.docker_client.docker.DockerClient')
    def test_run_build_task_not_found(self, mock_client_class, app):
        """Test run_build when task doesn't exist"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        with app.app_context():
            client = DockerBuildClient()
            cancel_event = threading.Event()
            result = client.run_build(99999, cancel_event)
            assert result is False

    @patch('app.docker_client.SourceManager')
    @patch('app.docker_client.docker.DockerClient')
    def test_run_build_source_prepare_failure(self, mock_client_class, mock_source_manager_class, app):
        """Test run_build when source preparation fails"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_source_manager = MagicMock()
        mock_source_manager.prepare.side_effect = Exception("Git clone failed")
        mock_source_manager_class.return_value = mock_source_manager

        with app.app_context():
            from app.extensions import db
            project = Project(name="test", user_id=1)
            db.session.add(project)
            db.session.commit()

            target = BuildTarget(project_id=project.id, name="linux")
            db.session.add(target)
            db.session.commit()

            task = BuildTask(
                project_id=project.id,
                target_id=target.id,
                build_group_id=1,
                status="pending",
            )
            db.session.add(task)
            db.session.commit()

            client = DockerBuildClient()
            cancel_event = threading.Event()
            result = client.run_build(task.id, cancel_event)

            assert result is False
            updated_task = BuildTask.query.get(task.id)
            assert updated_task.status == "failed"
            assert "源码准备失败" in updated_task.error_log


class TestRunBuildWithMocks:
    """Test run_build with full mocking"""

    @patch('app.docker_client.Path.mkdir')
    @patch('app.docker_client.SourceManager')
    @patch('app.docker_client.docker.DockerClient')
    def test_run_build_image_not_found_pulls_image(self, mock_client_class, mock_source_manager_class, mock_mkdir, app):
        """Test that image is pulled if not found locally"""
        mock_client = MagicMock()
        from docker.errors import ImageNotFound
        mock_client.images.get.side_effect = ImageNotFound("Image not found")
        mock_container = MagicMock()
        mock_container.logs.return_value = []
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_client.containers.run.return_value = mock_container
        mock_client_class.return_value = mock_client

        mock_source_manager = MagicMock()
        mock_source_manager.prepare.return_value = Path("/tmp/source")
        mock_source_manager_class.return_value = mock_source_manager

        with app.app_context():
            from app.extensions import db
            project = Project(name="test", user_id=1)
            db.session.add(project)
            db.session.commit()

            target = BuildTarget(
                project_id=project.id,
                name="linux",
                image="test/image:latest",
                build_command="make",
                artifacts_path="dist",
            )
            db.session.add(target)
            db.session.commit()

            task = BuildTask(
                project_id=project.id,
                target_id=target.id,
                build_group_id=1,
                status="pending",
            )
            db.session.add(task)
            db.session.commit()

            client = DockerBuildClient()
            cancel_event = threading.Event()
            result = client.run_build(task.id, cancel_event)

            # Image pull should have been attempted
            mock_client.images.pull.assert_called_once_with("test/image:latest")
