"""Tests for app/dependency_check.py"""
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch, mock_open

import pytest

from app.dependency_check import DockerDependencyChecker
from app.models import DependencyCheck


class TestDockerDependencyChecker:
    """Test DockerDependencyChecker class"""

    def test_init(self, app):
        """Test checker initialization"""
        with app.app_context():
            checker = DockerDependencyChecker()
            assert checker.resolver is not None
            assert checker.platform_id is not None
            assert len(checker.PRESET_IMAGES) == 5

    def test_check_python_ok(self, app):
        """Test Python version check with valid version"""
        with app.app_context():
            checker = DockerDependencyChecker()
            result = checker._check_python()

            assert result["status"] == "ok"
            assert "version" in result
            assert result["install_command"] is None
            assert "Python" in result["message"]

    @patch.object(sys, 'version_info', (3, 7))
    def test_check_python_old_version(self, app):
        """Test Python version check with old version"""
        with app.app_context():
            checker = DockerDependencyChecker()
            result = checker._check_python()

            assert result["status"] == "error"
            assert "install_command" in result
            assert result["install_command"] is not None

    @patch('app.dependency_check.shutil.which')
    def test_check_docker_missing(self, mock_which, app):
        """Test Docker check when docker command is missing"""
        mock_which.return_value = None

        with app.app_context():
            checker = DockerDependencyChecker()
            result = checker._check_docker()

            assert result["status"] == "missing"
            assert "未检测到 Docker" in result["message"]
            assert result["install_command"] is not None

    @patch('app.dependency_check.shutil.which')
    @patch('app.dependency_check.docker.DockerClient')
    def test_check_docker_ok(self, mock_client_class, mock_which, app):
        """Test Docker check when docker is available"""
        mock_which.return_value = "/usr/bin/docker"
        mock_client = MagicMock()
        mock_client.version.return_value = {"Version": "24.0.0"}
        mock_client_class.return_value = mock_client

        with app.app_context():
            checker = DockerDependencyChecker()
            result = checker._check_docker()

            assert result["status"] == "ok"
            assert result["version"] == "24.0.0"
            mock_client.close.assert_called_once()

    @patch('app.dependency_check.shutil.which')
    @patch('app.dependency_check.docker.DockerClient')
    def test_check_docker_daemon_error(self, mock_client_class, mock_which, app):
        """Test Docker check when daemon is not running"""
        mock_which.return_value = "/usr/bin/docker"
        import docker.errors
        mock_client_class.side_effect = docker.errors.DockerException("Cannot connect")

        with app.app_context():
            checker = DockerDependencyChecker()
            result = checker._check_docker()

            assert result["status"] == "error"
            assert "无法连接到守护进程" in result["message"]

    @patch('app.dependency_check.shutil.which')
    @patch('app.dependency_check.docker.DockerClient')
    def test_check_all(self, mock_client_class, mock_which, app):
        """Test check_all method"""
        mock_which.return_value = "/usr/bin/docker"
        mock_client = MagicMock()
        mock_client.version.return_value = {"Version": "24.0.0"}
        mock_client_class.return_value = mock_client

        with app.app_context():
            checker = DockerDependencyChecker()
            results = checker.check_all()

            assert "docker" in results
            assert "python" in results
            assert results["docker"]["status"] == "ok"
            assert results["python"]["status"] == "ok"

    def test_get_install_command_ubuntu(self, app):
        """Test install command for Ubuntu/Debian"""
        with app.app_context():
            checker = DockerDependencyChecker()
            checker.platform_id = "ubuntu_debian"

            cmd = checker._get_install_command("docker")
            assert "apt-get" in cmd
            assert "docker.io" in cmd

    def test_get_install_command_rhel(self, app):
        """Test install command for RHEL family"""
        with app.app_context():
            checker = DockerDependencyChecker()
            checker.platform_id = "rhel_family"

            cmd = checker._get_install_command("docker")
            assert "dnf" in cmd

    def test_get_install_command_arch(self, app):
        """Test install command for Arch Linux"""
        with app.app_context():
            checker = DockerDependencyChecker()
            checker.platform_id = "arch"

            cmd = checker._get_install_command("docker")
            assert "pacman" in cmd

    def test_get_install_command_macos(self, app):
        """Test install command for macOS"""
        with app.app_context():
            checker = DockerDependencyChecker()
            checker.platform_id = "macos"

            cmd = checker._get_install_command("docker")
            assert "brew" in cmd

    def test_get_install_command_windows(self, app):
        """Test install command for Windows"""
        with app.app_context():
            checker = DockerDependencyChecker()
            checker.platform_id = "windows"

            cmd = checker._get_install_command("docker")
            assert "docs.docker.com" in cmd

    def test_get_install_command_unknown(self, app):
        """Test install command for unknown platform defaults to ubuntu"""
        with app.app_context():
            checker = DockerDependencyChecker()
            checker.platform_id = "unknown"

            cmd = checker._get_install_command("docker")
            assert cmd is not None  # Should fallback to ubuntu_debian

    @patch('app.dependency_check.docker.DockerClient')
    def test_predownload_images_success(self, mock_client_class, app):
        """Test predownload_images with successful pulls"""
        mock_client = MagicMock()
        mock_client.images.pull.return_value = None
        mock_client_class.return_value = mock_client

        with app.app_context():
            checker = DockerDependencyChecker()
            outcomes = checker.predownload_images()

            assert len(outcomes) == 5
            assert all(o["status"] == "ok" for o in outcomes)
            assert mock_client.images.pull.call_count == 5

    @patch('app.dependency_check.docker.DockerClient')
    def test_predownload_images_failure(self, mock_client_class, app):
        """Test predownload_images with failed pulls"""
        mock_client = MagicMock()
        mock_client.images.pull.side_effect = Exception("Network error")
        mock_client_class.return_value = mock_client

        with app.app_context():
            checker = DockerDependencyChecker()
            outcomes = checker.predownload_images()

            assert len(outcomes) == 5
            assert all(o["status"] == "error" for o in outcomes)

    @patch('app.dependency_check.docker.DockerClient')
    def test_predownload_images_docker_unavailable(self, mock_client_class, app):
        """Test predownload_images when Docker is not available"""
        import docker.errors
        mock_client_class.side_effect = docker.errors.DockerException("Not running")

        with app.app_context():
            checker = DockerDependencyChecker()
            outcomes = checker.predownload_images()

            assert len(outcomes) == 5
            assert all(o["status"] == "skipped" for o in outcomes)

    @patch('app.dependency_check.subprocess.run')
    def test_run_auto_install_ubuntu_success(self, mock_run, app):
        """Test auto install on Ubuntu succeeds"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with app.app_context():
            checker = DockerDependencyChecker()
            checker.platform_id = "ubuntu_debian"
            result = checker.run_auto_install("docker")

            assert result["status"] == "ok"
            assert "成功" in result["message"]
            mock_run.assert_called_once()

    @patch('app.dependency_check.subprocess.run')
    def test_run_auto_install_failure(self, mock_run, app):
        """Test auto install when command fails"""
        from subprocess import CalledProcessError
        mock_run.side_effect = CalledProcessError(1, "apt-get", stderr="Permission denied")

        with app.app_context():
            checker = DockerDependencyChecker()
            checker.platform_id = "ubuntu_debian"
            result = checker.run_auto_install("docker")

            assert result["status"] == "error"
            assert "Permission denied" in result["message"]

    def test_run_auto_install_unsupported_platform(self, app):
        """Test auto install on unsupported platform"""
        with app.app_context():
            checker = DockerDependencyChecker()
            checker.platform_id = "macos"
            result = checker.run_auto_install("docker")

            assert result["status"] == "skipped"
            assert "不支持自动安装" in result["message"]

    def test_run_auto_install_unknown_component(self, app):
        """Test auto install with unknown component"""
        with app.app_context():
            checker = DockerDependencyChecker()
            checker.platform_id = "ubuntu_debian"
            result = checker.run_auto_install("unknown_component")

            assert result["status"] == "skipped"
            assert result["command"] is None

    def test_persist_results(self, app):
        """Test persisting check results to database"""
        with app.app_context():
            checker = DockerDependencyChecker()
            results = {
                "docker": {
                    "status": "ok",
                    "version": "24.0.0",
                    "message": "Docker OK",
                    "install_command": None,
                },
                "python": {
                    "status": "ok",
                    "version": "3.10.0",
                    "message": "Python OK",
                    "install_command": None,
                },
            }

            checker._persist_results(results)

            # Verify records were created
            docker_record = DependencyCheck.query.filter_by(component="docker").first()
            assert docker_record is not None
            assert docker_record.status == "ok"
            assert docker_record.version == "24.0.0"

            python_record = DependencyCheck.query.filter_by(component="python").first()
            assert python_record is not None
            assert python_record.status == "ok"
