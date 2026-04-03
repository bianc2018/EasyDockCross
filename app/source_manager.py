import shutil
import subprocess
from pathlib import Path

from app.config import Config
from app.models import Project


class SourceManager:
    """源码管理器：准备构建所需的源码目录"""

    def __init__(self):
        self.base_dir = Config.DATA_DIR / "sources"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def prepare(self, project: Project) -> Path:
        """根据项目配置准备源码目录，返回本地路径"""
        if project.source_type == "git":
            return self._prepare_git(project)
        elif project.source_type == "svn":
            return self._prepare_svn(project)
        elif project.source_type == "upload":
            upload_dir = Config.UPLOADS_DIR / str(project.id)
            if not upload_dir.exists():
                raise FileNotFoundError(f"项目上传的源码目录不存在: {upload_dir}")
            return upload_dir
        else:
            raise ValueError(f"不支持的源码类型: {project.source_type}")

    def _prepare_git(self, project: Project) -> Path:
        target_dir = self.base_dir / str(project.id)
        if not project.source_url:
            raise ValueError("Git 仓库地址不能为空")

        if (target_dir / ".git").exists():
            # 更新已有仓库
            subprocess.run(
                ["git", "-C", str(target_dir), "pull", "origin", project.source_branch or "main"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
        else:
            # 全新克隆
            target_dir.mkdir(parents=True, exist_ok=True)
            cmd = [
                "git", "clone",
                "-b", project.source_branch or "main",
                project.source_url,
                str(target_dir),
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return target_dir

    def _prepare_svn(self, project: Project) -> Path:
        target_dir = self.base_dir / str(project.id)
        if not project.source_url:
            raise ValueError("SVN 仓库地址不能为空")

        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["svn", "checkout", project.source_url, str(target_dir)],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        return target_dir
