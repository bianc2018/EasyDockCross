"""Tests for app/utils.py"""
import json
import platform
from pathlib import Path, PurePosixPath
from unittest.mock import MagicMock, patch, mock_open

import pytest

from app.utils import (
    PathResolver,
    safe_join,
    format_bytes,
    load_preset_templates,
)


class TestPathResolver:
    """Test PathResolver class"""

    def test_init_linux(self):
        """Test initialization on Linux"""
        with patch('app.utils.platform.system', return_value='Linux'):
            resolver = PathResolver()
            assert resolver.system == 'linux'
            assert resolver.is_docker_desktop is False

    def test_init_windows(self):
        """Test initialization on Windows"""
        with patch('app.utils.platform.system', return_value='Windows'):
            resolver = PathResolver()
            assert resolver.system == 'windows'
            assert resolver.is_docker_desktop is True

    def test_init_macos(self):
        """Test initialization on macOS"""
        with patch('app.utils.platform.system', return_value='Darwin'):
            resolver = PathResolver()
            assert resolver.system == 'darwin'
            assert resolver.is_docker_desktop is True

    def test_docker_desktop_env_override(self):
        """Test DOCKER_DESKTOP environment variable"""
        with patch.dict('os.environ', {'DOCKER_DESKTOP': '1'}, clear=False):
            with patch('app.utils.platform.system', return_value='unknown_os'):
                resolver = PathResolver()
                assert resolver.is_docker_desktop is True

    def test_get_docker_socket_linux_default(self):
        """Test getting Docker socket on Linux"""
        with patch('app.utils.platform.system', return_value='Linux'):
            resolver = PathResolver()
            socket = resolver.get_docker_socket()
            assert socket == "unix:///var/run/docker.sock"

    def test_get_docker_socket_windows_default(self):
        """Test getting Docker socket on Windows"""
        with patch('app.utils.platform.system', return_value='Windows'):
            resolver = PathResolver()
            socket = resolver.get_docker_socket()
            assert "npipe://" in socket

    def test_get_docker_socket_env_override(self):
        """Test DOCKER_SOCKET environment variable override"""
        with patch.dict('os.environ', {'DOCKER_SOCKET': 'tcp://localhost:2375'}):
            with patch('app.utils.platform.system', return_value='Linux'):
                resolver = PathResolver()
                socket = resolver.get_docker_socket()
                assert socket == "tcp://localhost:2375"

    def test_host_to_container_path_linux(self):
        """Test path conversion on Linux"""
        with patch('app.utils.platform.system', return_value='Linux'):
            resolver = PathResolver()
            result = resolver.host_to_container_path("/home/user/project")
            assert result == "/home/user/project"

    def test_host_to_container_path_docker_desktop(self):
        """Test path conversion on Docker Desktop"""
        with patch('app.utils.platform.system', return_value='Darwin'):
            resolver = PathResolver()
            result = resolver.host_to_container_path("/Users/user/project")
            assert result.startswith("/host/")
            assert "Users/user/project" in result

    def test_ensure_dir_creates_directory(self, tmp_path):
        """Test ensure_dir creates directory"""
        with patch('app.utils.platform.system', return_value='Linux'):
            resolver = PathResolver()
            test_path = tmp_path / "new" / "nested" / "dir"
            result = resolver.ensure_dir(test_path)
            assert test_path.exists()
            assert result == test_path

    def test_ensure_dir_existing_directory(self, tmp_path):
        """Test ensure_dir with existing directory"""
        with patch('app.utils.platform.system', return_value='Linux'):
            resolver = PathResolver()
            existing_path = tmp_path / "existing"
            existing_path.mkdir()
            result = resolver.ensure_dir(existing_path)
            assert result == existing_path

    def test_platform_id_ubuntu(self):
        """Test platform detection for Ubuntu"""
        os_release = 'ID=ubuntu\nVERSION="20.04"'
        with patch('builtins.open', mock_open(read_data=os_release)):
            with patch('app.utils.platform.system', return_value='Linux'):
                resolver = PathResolver()
                assert resolver.platform_id == "ubuntu_debian"

    def test_platform_id_debian(self):
        """Test platform detection for Debian"""
        os_release = 'ID=debian\nVERSION="11"'
        with patch('builtins.open', mock_open(read_data=os_release)):
            with patch('app.utils.platform.system', return_value='Linux'):
                resolver = PathResolver()
                assert resolver.platform_id == "ubuntu_debian"

    def test_platform_id_centos(self):
        """Test platform detection for CentOS"""
        os_release = 'ID=centos\nVERSION="8"'
        with patch('builtins.open', mock_open(read_data=os_release)):
            with patch('app.utils.platform.system', return_value='Linux'):
                resolver = PathResolver()
                assert resolver.platform_id == "rhel_family"

    def test_platform_id_fedora(self):
        """Test platform detection for Fedora"""
        os_release = 'ID=fedora\nVERSION="35"'
        with patch('builtins.open', mock_open(read_data=os_release)):
            with patch('app.utils.platform.system', return_value='Linux'):
                resolver = PathResolver()
                assert resolver.platform_id == "rhel_family"

    def test_platform_id_arch(self):
        """Test platform detection for Arch"""
        os_release = 'ID=arch\n'
        with patch('builtins.open', mock_open(read_data=os_release)):
            with patch('app.utils.platform.system', return_value='Linux'):
                resolver = PathResolver()
                assert resolver.platform_id == "arch"

    def test_platform_id_macos(self):
        """Test platform detection for macOS"""
        with patch('app.utils.platform.system', return_value='Darwin'):
            resolver = PathResolver()
            assert resolver.platform_id == "macos"

    def test_platform_id_windows(self):
        """Test platform detection for Windows"""
        with patch('app.utils.platform.system', return_value='Windows'):
            resolver = PathResolver()
            assert resolver.platform_id == "windows"

    def test_platform_id_read_error(self):
        """Test platform detection when os-release read fails"""
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            with patch('app.utils.platform.system', return_value='Linux'):
                resolver = PathResolver()
                assert resolver.platform_id == "linux_other"


class TestSafeJoin:
    """Test safe_join function"""

    def test_safe_join_normal(self, tmp_path):
        """Test normal path joining"""
        base = tmp_path / "base"
        base.mkdir()
        result = safe_join(base, "subdir", "file.txt")
        assert result == base / "subdir" / "file.txt"

    def test_safe_join_traversal_blocked(self, tmp_path):
        """Test path traversal is blocked"""
        base = tmp_path / "base"
        base.mkdir()
        with pytest.raises(ValueError) as exc_info:
            safe_join(base, "..", "..", "etc", "passwd")
        assert "路径穿越" in str(exc_info.value)


class TestFormatBytes:
    """Test format_bytes function"""

    def test_format_bytes_bytes(self):
        """Test formatting bytes"""
        assert format_bytes(512) == "512.0 B"

    def test_format_bytes_kilobytes(self):
        """Test formatting kilobytes"""
        assert format_bytes(1536) == "1.5 KB"

    def test_format_bytes_megabytes(self):
        """Test formatting megabytes"""
        assert format_bytes(5 * 1024 * 1024) == "5.0 MB"

    def test_format_bytes_gigabytes(self):
        """Test formatting gigabytes"""
        assert format_bytes(2 * 1024 * 1024 * 1024) == "2.0 GB"

    def test_format_bytes_terabytes(self):
        """Test formatting terabytes"""
        assert format_bytes(1024 ** 4) == "1.0 TB"

    def test_format_bytes_petabytes(self):
        """Test formatting petabytes"""
        assert format_bytes(1024 ** 5) == "1.0 PB"

    def test_format_bytes_zero(self):
        """Test formatting zero bytes"""
        assert format_bytes(0) == "0.0 B"


def test_safe_join_prevents_traversal(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    (base / "file.txt").write_text("ok")

    result = safe_join(base, "file.txt")
    assert result.name == "file.txt"

    with pytest.raises(ValueError, match="路径穿越"):
        safe_join(base, "../outside.txt")


def test_format_bytes_basic():
    assert format_bytes(512) == "512.0 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1024 * 1024) == "1.0 MB"


class TestLoadPresetTemplates:
    """Test load_preset_templates function"""

    def test_load_presets_empty_directory(self, tmp_path):
        """Test loading from empty directory"""
        presets_dir = tmp_path / "presets"
        presets_dir.mkdir()
        result = load_preset_templates(presets_dir)
        assert result == {}

    def test_load_presets_with_valid_files(self, tmp_path):
        """Test loading valid preset files"""
        presets_dir = tmp_path / "presets"
        templates_dir = presets_dir / "templates"
        templates_dir.mkdir(parents=True)

        # Create valid JSON preset
        preset1 = {"key": "go-linux", "name": "Go Linux", "language": "go"}
        (templates_dir / "go_linux.json").write_text(json.dumps(preset1))

        preset2 = {"key": "python-linux", "name": "Python Linux", "language": "python"}
        (templates_dir / "python_linux.json").write_text(json.dumps(preset2))

        result = load_preset_templates(presets_dir)

        assert len(result) == 2
        assert result["go-linux"]["name"] == "Go Linux"
        assert result["python-linux"]["name"] == "Python Linux"

    def test_load_presets_invalid_json(self, tmp_path):
        """Test loading with invalid JSON file"""
        presets_dir = tmp_path / "presets"
        templates_dir = presets_dir / "templates"
        templates_dir.mkdir(parents=True)

        # Create invalid JSON file
        (templates_dir / "invalid.json").write_text("not valid json")

        # Create valid JSON file
        preset = {"key": "valid", "name": "Valid"}
        (templates_dir / "valid.json").write_text(json.dumps(preset))

        result = load_preset_templates(presets_dir)

        # Should skip invalid file and load valid one
        assert len(result) == 1
        assert "valid" in result

    def test_load_presets_missing_key_uses_filename(self, tmp_path):
        """Test using filename as key when key is missing"""
        presets_dir = tmp_path / "presets"
        templates_dir = presets_dir / "templates"
        templates_dir.mkdir(parents=True)

        # Create preset without key
        preset = {"name": "No Key Preset"}
        (templates_dir / "my_preset.json").write_text(json.dumps(preset))

        result = load_preset_templates(presets_dir)

        assert "my_preset" in result

    def test_load_presets_no_templates_dir(self, tmp_path):
        """Test when templates directory doesn't exist"""
        presets_dir = tmp_path / "presets"
        presets_dir.mkdir()
        # Don't create templates subdirectory

        result = load_preset_templates(presets_dir)
        assert result == {}

    def test_load_presets_non_json_files_ignored(self, tmp_path):
        """Test that non-JSON files are ignored"""
        presets_dir = tmp_path / "presets"
        templates_dir = presets_dir / "templates"
        templates_dir.mkdir(parents=True)

        # Create various file types
        (templates_dir / "readme.txt").write_text("Not a preset")
        (templates_dir / "config.yaml").write_text("key: value")
        preset = {"key": "valid", "name": "Valid"}
        (templates_dir / "valid.json").write_text(json.dumps(preset))

        result = load_preset_templates(presets_dir)

        assert len(result) == 1
        assert "valid" in result
