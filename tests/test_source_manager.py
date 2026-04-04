"""Tests for app/source_manager.py"""
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.source_manager import SourceManager
from app.models import Project


class TestSourceManagerInit:
    """Test SourceManager initialization"""

    def test_init_creates_directory(self, app, tmp_path):
        """Test that initialization creates base directory"""
        with app.app_context():
            # Patch DATA_DIR to use temp path
            with patch('app.source_manager.Config.DATA_DIR', tmp_path):
                manager = SourceManager()
                assert manager.base_dir.exists()
                assert manager.base_dir == tmp_path / "sources"


class TestSourceManagerPrepare:
    """Test prepare method"""

    def test_prepare_upload_source(self, app, tmp_path):
        """Test preparing upload source"""
        with app.app_context():
            from app.extensions import db
            from app.config import Config

            project = Project(
                name="test",
                user_id=1,
                source_type="upload",
            )
            db.session.add(project)
            db.session.commit()

            # Create upload directory
            upload_dir = tmp_path / "uploads" / str(project.id)
            upload_dir.mkdir(parents=True)
            (upload_dir / "file.txt").write_text("test")

            with patch('app.source_manager.Config.UPLOADS_DIR', tmp_path / "uploads"):
                manager = SourceManager()
                result = manager.prepare(project)

                assert result == upload_dir

    def test_prepare_upload_source_missing(self, app, tmp_path):
        """Test preparing upload source when directory doesn't exist"""
        with app.app_context():
            from app.extensions import db

            project = Project(
                name="test",
                user_id=1,
                source_type="upload",
            )
            db.session.add(project)
            db.session.commit()

            with patch('app.source_manager.Config.UPLOADS_DIR', tmp_path / "uploads"):
                manager = SourceManager()
                with pytest.raises(FileNotFoundError) as exc_info:
                    manager.prepare(project)
                assert "源码目录不存在" in str(exc_info.value)

    def test_prepare_invalid_source_type(self, app):
        """Test preparing with invalid source type"""
        with app.app_context():
            from app.extensions import db

            project = Project(
                name="test",
                user_id=1,
                source_type="invalid",
            )
            db.session.add(project)
            db.session.commit()

            manager = SourceManager()
            with pytest.raises(ValueError) as exc_info:
                manager.prepare(project)
            assert "不支持的源码类型" in str(exc_info.value)


class TestPrepareGit:
    """Test _prepare_git method"""

    @patch('app.source_manager.subprocess.run')
    def test_prepare_git_clone_new(self, mock_run, app, tmp_path):
        """Test cloning new git repository"""
        mock_run.return_value = MagicMock(returncode=0)

        with app.app_context():
            from app.extensions import db

            project = Project(
                name="test",
                user_id=1,
                source_type="git",
                source_url="https://github.com/user/repo.git",
                source_branch="main",
            )
            db.session.add(project)
            db.session.commit()

            with patch('app.source_manager.Config.DATA_DIR', tmp_path):
                manager = SourceManager()
                result = manager._prepare_git(project)

                expected_path = tmp_path / "sources" / str(project.id)
                assert result == expected_path

                # Verify git clone was called
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                assert call_args[0] == "git"
                assert call_args[1] == "clone"

    @patch('app.source_manager.subprocess.run')
    def test_prepare_git_update_existing(self, mock_run, app, tmp_path):
        """Test updating existing git repository"""
        mock_run.return_value = MagicMock(returncode=0)

        with app.app_context():
            from app.extensions import db

            project = Project(
                name="test",
                user_id=1,
                source_type="git",
                source_url="https://github.com/user/repo.git",
                source_branch="develop",
            )
            db.session.add(project)
            db.session.commit()

            # Create .git directory to simulate existing repo
            git_dir = tmp_path / "sources" / str(project.id) / ".git"
            git_dir.mkdir(parents=True)

            with patch('app.source_manager.Config.DATA_DIR', tmp_path):
                manager = SourceManager()
                result = manager._prepare_git(project)

                # Verify git pull was called
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                assert call_args[0] == "git"
                assert call_args[1] == "-C"

    def test_prepare_git_missing_url(self, app, tmp_path):
        """Test git prepare without URL"""
        with app.app_context():
            from app.extensions import db

            project = Project(
                name="test",
                user_id=1,
                source_type="git",
                source_url="",
            )
            db.session.add(project)
            db.session.commit()

            with patch('app.source_manager.Config.DATA_DIR', tmp_path):
                manager = SourceManager()
                with pytest.raises(ValueError) as exc_info:
                    manager._prepare_git(project)
                assert "Git 仓库地址不能为空" in str(exc_info.value)


class TestPrepareSvn:
    """Test _prepare_svn method"""

    @patch('app.source_manager.subprocess.run')
    @patch('app.source_manager.shutil.rmtree')
    def test_prepare_svn_checkout(self, mock_rmtree, mock_run, app, tmp_path):
        """Test SVN checkout"""
        mock_run.return_value = MagicMock(returncode=0)

        with app.app_context():
            from app.extensions import db

            project = Project(
                name="test",
                user_id=1,
                source_type="svn",
                source_url="https://svn.example.com/repo",
            )
            db.session.add(project)
            db.session.commit()

            with patch('app.source_manager.Config.DATA_DIR', tmp_path):
                manager = SourceManager()
                result = manager._prepare_svn(project)

                expected_path = tmp_path / "sources" / str(project.id)
                assert result == expected_path

                # Verify svn checkout was called
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                assert call_args[0] == "svn"
                assert call_args[1] == "checkout"

    def test_prepare_svn_missing_url(self, app, tmp_path):
        """Test SVN prepare without URL"""
        with app.app_context():
            from app.extensions import db

            project = Project(
                name="test",
                user_id=1,
                source_type="svn",
                source_url="",
            )
            db.session.add(project)
            db.session.commit()

            with patch('app.source_manager.Config.DATA_DIR', tmp_path):
                manager = SourceManager()
                with pytest.raises(ValueError) as exc_info:
                    manager._prepare_svn(project)
                assert "SVN 仓库地址不能为空" in str(exc_info.value)

    def test_prepare_svn_dangerous_url(self, app, tmp_path):
        """Test SVN prepare with potentially dangerous URL"""
        with app.app_context():
            from app.extensions import db

            project = Project(
                name="test",
                user_id=1,
                source_type="svn",
                source_url="--username=admin",  # Attempt at option injection
            )
            db.session.add(project)
            db.session.commit()

            with patch('app.source_manager.Config.DATA_DIR', tmp_path):
                manager = SourceManager()
                with pytest.raises(ValueError) as exc_info:
                    manager._prepare_svn(project)
                assert "非法的 SVN 仓库地址" in str(exc_info.value)


class TestSourceManagerIntegration:
    """Integration tests for SourceManager"""

    def test_prepare_dispatches_to_correct_handler(self, app, tmp_path):
        """Test that prepare dispatches to correct handler based on source_type"""
        with app.app_context():
            from app.extensions import db

            # Test git dispatch
            git_project = Project(
                name="git-test",
                user_id=1,
                source_type="git",
                source_url="https://github.com/test/repo.git",
            )
            db.session.add(git_project)
            db.session.commit()

            # Create .git dir to trigger update path
            git_dir = tmp_path / "sources" / str(git_project.id) / ".git"
            git_dir.mkdir(parents=True)

            with patch('app.source_manager.Config.DATA_DIR', tmp_path):
                with patch('app.source_manager.subprocess.run') as mock_run:
                    mock_run.return_value = MagicMock(returncode=0)
                    manager = SourceManager()
                    manager.prepare(git_project)

                    # Verify git command was called
                    assert mock_run.call_args[0][0][0] == "git"

            # Test svn dispatch
            svn_project = Project(
                name="svn-test",
                user_id=1,
                source_type="svn",
                source_url="https://svn.example.com/repo",
            )
            db.session.add(svn_project)
            db.session.commit()

            with patch('app.source_manager.Config.DATA_DIR', tmp_path):
                with patch('app.source_manager.subprocess.run') as mock_run:
                    mock_run.return_value = MagicMock(returncode=0)
                    manager = SourceManager()
                    manager.prepare(svn_project)

                    # Verify svn command was called
                    assert mock_run.call_args[0][0][0] == "svn"
