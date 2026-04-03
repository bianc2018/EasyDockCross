import os
import sys
import platform
from pathlib import Path, PurePosixPath, PureWindowsPath


class PathResolver:
    """跨平台路径解析器，处理 Linux / Windows / macOS 宿主机的路径差异"""

    def __init__(self):
        self.system = platform.system().lower()
        self.is_docker_desktop = self._detect_docker_desktop()

    def _detect_docker_desktop(self) -> bool:
        """检测是否运行在 Docker Desktop 环境（Windows 或 macOS）"""
        if self.system == "linux":
            return False
        if self.system in ("darwin", "windows"):
            return True
        # 通过环境变量兜底判断
        if os.environ.get("DOCKER_DESKTOP"):
            return True
        return False

    def get_docker_socket(self) -> str:
        """返回适合当前平台的 Docker socket 路径"""
        if self.system == "windows":
            return os.environ.get("DOCKER_SOCKET", "npipe:////./pipe/docker_engine")
        return os.environ.get("DOCKER_SOCKET", "unix:///var/run/docker.sock")

    def host_to_container_path(self, host_path: str, container_prefix: str = "/host") -> str:
        """
        将宿主机路径转换为容器内部挂载路径。
        在 Docker Desktop 下，共享卷挂载通常通过 /host 前缀映射。
        """
        if self.is_docker_desktop:
            # macOS/Windows 的 Docker Desktop 绑定挂载在 Linux VM 中
            p = Path(host_path).resolve()
            return str(PurePosixPath(container_prefix) / p.relative_to(p.anchor))
        else:
            # 原生 Linux 直接挂载
            return str(PurePosixPath(Path(host_path).resolve()))

    def ensure_dir(self, path: Path) -> Path:
        """确保目录存在并返回 Path 对象"""
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def platform_id(self) -> str:
        """返回平台标识，用于依赖检查模块分发安装命令"""
        if self.system == "linux":
            try:
                with open("/etc/os-release") as f:
                    lines = {k.strip().lower(): v.strip('"').lower() for line in f if "=" in line for k, v in [line.split("=", 1)]}
                distro_id = lines.get("id", "unknown")
                if distro_id in ("ubuntu", "debian"):
                    return "ubuntu_debian"
                if distro_id in ("centos", "rhel", "fedora", "rocky", "almalinux"):
                    return "rhel_family"
                if distro_id in ("arch", "manjaro"):
                    return "arch"
                return "linux_other"
            except Exception:
                return "linux_other"
        if self.system == "darwin":
            return "macos"
        if self.system == "windows":
            return "windows"
        return "unknown"


def safe_join(base: Path, *paths: str) -> Path:
    """安全的路径拼接，防止路径穿越"""
    target = (base / os.path.join(*paths)).resolve()
    base_resolved = base.resolve()
    try:
        target.relative_to(base_resolved)
    except ValueError:
        raise ValueError("非法路径：路径穿越被阻止")
    return target


def format_bytes(size: int) -> str:
    """将字节数格式化为人类可读字符串"""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def load_preset_templates(presets_dir: Path) -> dict:
    """加载 presets/templates/ 下的所有 JSON 预设模板"""
    templates = {}
    templates_dir = presets_dir / "templates"
    if not templates_dir.exists():
        return templates
    for f in sorted(templates_dir.glob("*.json")):
        try:
            import json
            data = json.loads(f.read_text(encoding="utf-8"))
            key = data.get("key") or f.stem
            templates[key] = data
        except Exception:
            continue
    return templates
