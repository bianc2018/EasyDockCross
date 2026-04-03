import os
import shutil
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

import docker

from app.extensions import db
from app.models import DependencyCheck
from app.utils import PathResolver


class DockerDependencyChecker:
    """Docker 依赖检查器：检测安装状态、版本、提供安装指引"""

    PRESET_IMAGES = [
        "dockcross/linux-x64:latest",
        "dockcross/linux-arm64:latest",
        "dockcross/linux-armv7:latest",
        "dockcross/windows-x64:latest",
        "dockcross/manylinux2014-x64:latest",
    ]

    def __init__(self):
        self.resolver = PathResolver()
        self.platform_id = self.resolver.platform_id

    def check_all(self) -> Dict[str, dict]:
        """执行全部依赖检查并返回结果字典"""
        results = {}
        results["docker"] = self._check_docker()
        results["python"] = self._check_python()
        self._persist_results(results)
        return results

    def _check_docker(self) -> dict:
        """检查 Docker 客户端与守护进程可用性"""
        result = {
            "status": "pending",
            "version": None,
            "message": "",
            "install_command": None,
        }

        # 1) 检查 docker 命令是否存在
        docker_bin = shutil.which("docker")
        if not docker_bin:
            result["status"] = "missing"
            result["message"] = "未检测到 Docker 命令，请安装 Docker。"
            result["install_command"] = self._get_install_command("docker")
            return result

        # 2) 尝试连接 Docker daemon
        try:
            client = docker.DockerClient(base_url=self.resolver.get_docker_socket())
            version_info = client.version()
            result["status"] = "ok"
            result["version"] = version_info.get("Version", "unknown")
            result["message"] = f"Docker 运行正常，版本: {result['version']}"
            client.close()
        except docker.errors.DockerException as e:
            result["status"] = "error"
            result["message"] = f"Docker 已安装但无法连接到守护进程: {str(e)}"
            result["install_command"] = self._get_install_command("docker_service")
        except Exception as e:
            result["status"] = "error"
            result["message"] = f"检查 Docker 时发生未知错误: {str(e)}"

        return result

    def _check_python(self) -> dict:
        """检查 Python 版本"""
        import sys

        major, minor = sys.version_info[:2]
        version = f"{major}.{minor}"
        result = {
            "status": "ok",
            "version": sys.version.split()[0],
            "message": f"Python 版本 {version}",
            "install_command": None,
        }
        if (major, minor) < (3, 8):
            result["status"] = "error"
            result["message"] = f"Python 版本过低，需要 3.8+，当前 {version}"
            result["install_command"] = self._get_install_command("python3")
        return result

    def _get_install_command(self, component: str) -> Optional[str]:
        """根据平台返回安装命令指引"""
        commands = {
            "ubuntu_debian": {
                "docker": "sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin && sudo systemctl enable --now docker",
                "docker_service": "sudo systemctl start docker",
                "python3": "sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv",
            },
            "rhel_family": {
                "docker": "sudo dnf install -y docker docker-compose-plugin && sudo systemctl enable --now docker",
                "docker_service": "sudo systemctl start docker",
                "python3": "sudo dnf install -y python3 python3-pip",
            },
            "arch": {
                "docker": "sudo pacman -S --noconfirm docker docker-compose && sudo systemctl enable --now docker",
                "docker_service": "sudo systemctl start docker",
                "python3": "sudo pacman -S --noconfirm python python-pip",
            },
            "macos": {
                "docker": "brew install --cask docker",
                "docker_service": "open -a Docker",
                "python3": "brew install python@3.11",
            },
            "windows": {
                "docker": "请访问 https://docs.docker.com/desktop/install/windows-install/ 下载 Docker Desktop",
                "docker_service": "请启动 Docker Desktop 应用程序",
                "python3": "请访问 https://www.python.org/downloads/windows/ 下载 Python 安装包",
            },
        }

        platform_map = {
            "ubuntu_debian": "ubuntu_debian",
            "rhel_family": "rhel_family",
            "arch": "arch",
            "macos": "macos",
            "windows": "windows",
        }

        plat = platform_map.get(self.platform_id, "ubuntu_debian")
        return commands.get(plat, {}).get(component)

    def _persist_results(self, results: Dict[str, dict]):
        """将检查结果持久化到数据库"""
        for component, data in results.items():
            record = DependencyCheck.query.filter_by(component=component).first()
            if not record:
                record = DependencyCheck(component=component)
                db.session.add(record)
            record.status = data["status"]
            record.version = data.get("version")
            record.message = data.get("message")
            record.install_command = data.get("install_command")
            record.checked_at = datetime.utcnow()
        db.session.commit()

    def predownload_images(self) -> List[dict]:
        """尝试预下载常用 dockcross 镜像，返回每个镜像的拉取结果"""
        try:
            client = docker.DockerClient(base_url=self.resolver.get_docker_socket())
        except Exception as e:
            return [{"image": img, "status": "skipped", "message": f"Docker 不可用: {e}"} for img in self.PRESET_IMAGES]

        outcomes = []
        for image in self.PRESET_IMAGES:
            try:
                client.images.pull(image)
                outcomes.append({"image": image, "status": "ok", "message": "拉取成功"})
            except Exception as e:
                outcomes.append({"image": image, "status": "error", "message": str(e)})
        client.close()
        return outcomes

    def run_auto_install(self, component: str = "docker") -> dict:
        """
        在受支持的平台（Ubuntu/Debian）上自动执行安装命令。
        其他平台仅返回安装指引，不执行任何操作。
        """
        if self.platform_id != "ubuntu_debian":
            return {
                "status": "skipped",
                "message": f"当前平台 {self.platform_id} 不支持自动安装，请参考以下命令手动安装",
                "command": self._get_install_command(component),
            }

        command = self._get_install_command(component)
        if not command:
            return {
                "status": "skipped",
                "message": "未找到对应的自动安装命令",
                "command": None,
            }

        try:
            subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return {
                "status": "ok",
                "message": f"自动安装 {component} 成功，请刷新页面重新检查状态",
                "command": command,
            }
        except subprocess.CalledProcessError as e:
            return {
                "status": "error",
                "message": f"自动安装失败: {e.stderr}",
                "command": command,
            }
