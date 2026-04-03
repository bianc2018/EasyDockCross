import shlex
import threading
from pathlib import Path

import docker
from docker.errors import DockerException, ImageNotFound, NotFound

from app.config import Config
from app.extensions import db
from app.models import BuildTask, BuildArtifact
from app.source_manager import SourceManager
from app.utils import PathResolver


class DockerBuildClient:
    """Docker 构建客户端：容器生命周期、日志流、产物收集、缓存挂载"""

    DOCKER_CPU_PERIOD = 100000
    DOCKER_CPU_QUOTA = 100000

    def __init__(self):
        self.resolver = PathResolver()
        self.source_manager = SourceManager()
        try:
            self.client = docker.DockerClient(base_url=self.resolver.get_docker_socket())
            self.client.ping()
        except DockerException as e:
            raise RuntimeError(f"无法连接到 Docker 守护进程: {e}")

    def run_build(
        self,
        task_id: int,
        cancel_event: threading.Event,
    ) -> bool:
        """
        执行单个构建任务。
        返回 True 表示构建成功，False 表示失败或被取消。
        """
        task = BuildTask.query.get(task_id)
        if not task:
            return False

        target = task.target
        project = target.project

        # 1. 准备源码目录
        try:
            source_dir = self.source_manager.prepare(project)
        except Exception as e:
            task.status = "failed"
            task.error_log = f"[系统] 源码准备失败: {e}\n"
            task.end_time = __import__("datetime").datetime.utcnow()
            db.session.commit()
            return False

        # 2. 构建挂载卷列表
        binds = {
            str(source_dir): {
                "bind": "/work/src",
                "mode": "rw",
            }
        }

        # 缓存挂载
        cache_volumes = self._build_cache_volumes(project.id)
        for host_path, container_path in cache_volumes.items():
            binds[str(host_path)] = {"bind": container_path, "mode": "rw"}

        # 产物输出目录挂载
        artifact_host_dir = Config.ARTIFACTS_DIR / str(task.id)
        artifact_host_dir.mkdir(parents=True, exist_ok=True)
        binds[str(artifact_host_dir)] = {"bind": "/work/output", "mode": "rw"}

        # 3. 容器资源配置
        host_config = self.client.api.create_host_config(
            binds=binds,
            mem_limit=Config.DOCKER_MEM_LIMIT,
            cpu_period=self.DOCKER_CPU_PERIOD,
            cpu_quota=self.DOCKER_CPU_QUOTA,
        )

        # 4. 构建命令拆分处理
        command = target.build_command or "echo 'No build command'"
        # 使用 bash -c 执行，方便处理复杂命令
        entrypoint = ["/bin/bash", "-c"]
        cmd = [f"cd /work/src \u0026\u0026 {shlex.quote(command)} \u0026\u0026 cp -r {shlex.quote(target.artifacts_path or '.')} /work/output/"]

        container = None
        try:
            # 5. 拉取镜像（如果本地不存在）
            try:
                self.client.images.get(target.image)
            except ImageNotFound:
                task.output_log = (task.output_log or "") + f"[系统] 本地未找到镜像 {target.image}，开始拉取...\n"
                db.session.commit()
                self.client.images.pull(target.image)

            # 6. 创建并启动容器
            container = self.client.containers.run(
                image=target.image,
                command=cmd,
                entrypoint=entrypoint,
                working_dir="/work/src",
                user="1000:1000",
                environment=target.env_vars or {},
                host_config=host_config,
                detach=True,
                stdout=True,
                stderr=True,
            )
            task.container_id = container.id
            db.session.commit()

            # 7. 实时读取日志
            for line in container.logs(stream=True, follow=True, stdout=True, stderr=True):
                if cancel_event.is_set():
                    container.stop(timeout=30)
                    container.wait()
                    task.status = "cancelled"
                    task.end_time = __import__("datetime").datetime.utcnow()
                    db.session.commit()
                    return False

                text = line.decode("utf-8", errors="replace")
                task.output_log = (task.output_log or "") + text
                db.session.commit()

            # 8. 等待容器结束
            result = container.wait()
            exit_code = result.get("StatusCode", -1)

            if exit_code != 0:
                task.status = "failed"
                task.error_log = (task.error_log or "") + f"[系统] 构建容器退出码: {exit_code}\n"
                task.end_time = __import__("datetime").datetime.utcnow()
                db.session.commit()
                return False

            # 9. 收集产物
            self._collect_artifacts(task, artifact_host_dir)

            task.status = "success"
            task.end_time = __import__("datetime").datetime.utcnow()
            db.session.commit()
            return True

        except Exception as e:
            task.status = "failed"
            task.error_log = (task.error_log or "") + f"[系统] Docker 构建异常: {e}\n"
            task.end_time = __import__("datetime").datetime.utcnow()
            db.session.commit()
            return False

        finally:
            # 10. 清理容器
            if container is not None:
                try:
                    container.remove(force=True)
                except NotFound:
                    pass
                except Exception:
                    pass

    def _build_cache_volumes(self, project_id: int) -> dict:
        """返回项目级缓存挂载映射 {host_path: container_path}"""
        cache_base = Config.CACHE_BASE_DIR / str(project_id)
        cache_base.mkdir(parents=True, exist_ok=True)
        return {
            str(cache_base / "pip"): "/root/.cache/pip",
            str(cache_base / "npm"): "/root/.npm",
            str(cache_base / "ccache"): "/ccache",
        }

    def _collect_artifacts(self, task: BuildTask, artifact_host_dir: Path):
        """扫描产物目录并记录到数据库"""
        # 清理已有产物记录
        BuildArtifact.query.filter_by(build_task_id=task.id).delete()

        if not artifact_host_dir.exists():
            return

        for fpath in artifact_host_dir.rglob("*"):
            if fpath.is_file():
                size = fpath.stat().st_size
                artifact = BuildArtifact(
                    build_task_id=task.id,
                    file_path=str(fpath.relative_to(artifact_host_dir)),
                    file_size=size,
                    download_url=f"/api/v1/artifacts/{task.id}/download/{fpath.relative_to(artifact_host_dir)}",
                )
                db.session.add(artifact)
        db.session.commit()

    def stream_logs(self, container_id: str):
        """流式读取容器日志生成器（供 WebSocket/SSE 使用）"""
        try:
            container = self.client.containers.get(container_id)
            for line in container.logs(stream=True, follow=True, stdout=True, stderr=True):
                yield line.decode("utf-8", errors="replace")
        except NotFound:
            yield "[系统] 容器已不存在\n"
        except Exception as e:
            yield f"[系统] 日志流异常: {e}\n"
