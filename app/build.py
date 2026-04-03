import threading
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
from sqlalchemy import update
from sqlalchemy.orm import contains_eager

from app.config import Config
from app.docker_client import DockerBuildClient
from app.extensions import db
from app.models import BuildArtifact, BuildGroup, BuildTask, BuildTarget, Project

build_bp = Blueprint("build", __name__)


def _group_to_dict(group: BuildGroup) -> dict:
    return {
        "id": group.id,
        "project_id": group.project_id,
        "trigger_type": group.trigger_type,
        "status": group.status,
        "created_at": group.created_at.isoformat() if group.created_at else None,
        "completed_at": group.completed_at.isoformat() if group.completed_at else None,
    }


def _task_to_dict(task: BuildTask) -> dict:
    return {
        "id": task.id,
        "project_id": task.project_id,
        "target_id": task.target_id,
        "build_group_id": task.build_group_id,
        "status": task.status,
        "container_id": task.container_id,
        "start_time": task.start_time.isoformat() if task.start_time else None,
        "end_time": task.end_time.isoformat() if task.end_time else None,
        "output_log": task.output_log,
        "error_log": task.error_log,
    }


def _update_group_status(group_id: int):
    """根据组内所有任务状态聚合更新 BuildGroup 状态"""
    group = BuildGroup.query.get(group_id)
    if not group:
        return

    tasks = BuildTask.query.filter_by(build_group_id=group_id).all()
    if not tasks:
        group.status = "success"
        group.completed_at = datetime.utcnow()
        db.session.commit()
        return

    statuses = {t.status for t in tasks}

    if "running" in statuses:
        group.status = "running"
        db.session.commit()
        return

    if "pending" in statuses:
        # 还有未开始的，但可能没有正在运行的
        if group.status != "running":
            group.status = "pending"
        db.session.commit()
        return

    # 到这里，所有任务都处于结束态
    if "failed" in statuses:
        group.status = "failed"
    elif "cancelled" in statuses:
        group.status = "cancelled"
    else:
        group.status = "success"

    if not group.completed_at:
        group.completed_at = datetime.utcnow()
    db.session.commit()


class BuildScheduler:
    """构建调度器：控制并发、超时、队列、状态聚合"""

    def __init__(self, app=None):
        self.app = app
        self.max_concurrent = 3
        self.timeout_seconds = 7200
        self._semaphore = threading.Semaphore(self.max_concurrent)
        self._task_threads: dict[int, threading.Thread] = {}
        self._cancel_events: dict[int, threading.Event] = {}
        self._lock = threading.Lock()

    def init_app(self, app):
        self.app = app
        self.max_concurrent = app.config.get("MAX_CONCURRENT_BUILDS", 3)
        self.timeout_seconds = app.config.get("BUILD_TIMEOUT_SECONDS", 7200)
        self._semaphore = threading.Semaphore(self.max_concurrent)

    def submit_group(self, group_id: int) -> bool:
        """手动提交一个 BuildGroup 开始调度"""
        group = BuildGroup.query.get(group_id)
        if not group:
            return False

        tasks = BuildTask.query.filter_by(build_group_id=group_id, status="pending").all()
        if not tasks:
            _update_group_status(group_id)
            return True

        # 为每个 task 启动后台线程，semaphore 控制并发
        for task in tasks:
            t = threading.Thread(target=self._run_task_wrapper, args=(task.id,), daemon=True)
            t.start()
            with self._lock:
                self._task_threads[task.id] = t
        return True

    def _run_task_wrapper(self, task_id: int):
        """获取信号量后执行任务"""
        acquired = self._semaphore.acquire()
        try:
            self._execute_task(task_id)
        finally:
            if acquired:
                self._semaphore.release()
            with self._lock:
                self._task_threads.pop(task_id, None)
                self._cancel_events.pop(task_id, None)

    def _execute_task(self, task_id: int):
        """单个构建任务执行逻辑"""
        with self.app.app_context():
            # 原子性状态更新：只更新仍处于 pending 的任务
            result = db.session.execute(
                update(BuildTask)
                .where(BuildTask.id == task_id, BuildTask.status == "pending")
                .values(status="running", start_time=datetime.utcnow())
            )
            db.session.commit()
            if result.rowcount == 0:
                return

            task = BuildTask.query.get(task_id)
            if not task:
                return

            cancel_event = threading.Event()
            with self._lock:
                self._cancel_events[task_id] = cancel_event

            _update_group_status(task.build_group_id)

            # 启动超时 Timer
            timer = threading.Timer(self.timeout_seconds, self._timeout_task, args=(task_id,))
            timer.start()

            success = False
            try:
                # Docker 真实构建（TASK-006 已实现）
                success = self._run_docker_build(task_id, cancel_event)
            finally:
                timer.cancel()
                task = BuildTask.query.get(task_id)
                if task and task.status == "running":
                    # 异常情况：docker_client 没有正确结束状态
                    task.status = "failed" if not success else "success"
                    task.end_time = datetime.utcnow()
                    db.session.commit()
                _update_group_status(task.build_group_id)

    def _run_docker_build(self, task_id: int, cancel_event: threading.Event) -> bool:
        """调用 DockerBuildClient 执行真实构建"""
        client = DockerBuildClient()
        return client.run_build(task_id, cancel_event)

    def _timeout_task(self, task_id: int):
        """超时处理：强制将任务标记为 failed"""
        with self.app.app_context():
            task = BuildTask.query.get(task_id)
            if task and task.status == "running":
                task.status = "failed"
                task.end_time = datetime.utcnow()
                task.error_log = (task.error_log or "") + "[系统] 构建超时（超过 2 小时）\n"
                db.session.commit()
                self._signal_cancel(task_id)
                _update_group_status(task.build_group_id)

    def cancel_task(self, task_id: int) -> bool:
        """取消指定构建任务"""
        task = BuildTask.query.get(task_id)
        if not task:
            return False
        if task.status in ("success", "failed", "cancelled"):
            return False

        if task.status == "pending":
            task.status = "cancelled"
            task.end_time = datetime.utcnow()
            db.session.commit()
            _update_group_status(task.build_group_id)
            return True

        if task.status == "running":
            task.status = "cancelled"
            task.end_time = datetime.utcnow()
            db.session.commit()
            self._signal_cancel(task_id)
            _update_group_status(task.build_group_id)
            return True

        return False

    def _signal_cancel(self, task_id: int):
        with self._lock:
            event = self._cancel_events.get(task_id)
            if event:
                event.set()


# 全局调度器实例
scheduler = BuildScheduler()


# ===========================
# Build APIs
# ===========================

@build_bp.route("/projects/<int:project_id>/build", methods=["POST"])
@login_required
def trigger_build(project_id):
    """手动触发构建"""
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "无权访问"}), 403

    data = request.get_json(silent=True) or {}
    target_ids = data.get("target_ids", [])

    if not target_ids:
        # 默认构建所有 target
        targets = BuildTarget.query.filter_by(project_id=project_id).all()
        target_ids = [t.id for t in targets]

    if not target_ids:
        return jsonify({"error": "项目下没有可用的构建目标"}), 400

    group = BuildGroup(
        project_id=project_id,
        trigger_type="manual",
        status="pending",
    )
    db.session.add(group)
    db.session.commit()

    for tid in target_ids:
        task = BuildTask(
            project_id=project_id,
            target_id=tid,
            build_group_id=group.id,
            status="pending",
        )
        db.session.add(task)
    db.session.commit()

    scheduler.submit_group(group.id)
    return jsonify(_group_to_dict(group)), 201


@build_bp.route("/builds", methods=["GET"])
@login_required
def list_builds():
    """获取所有构建组列表（带项目名称）"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    project_id = request.args.get("project_id", type=int)

    query = (
        BuildGroup.query
        .join(Project, BuildGroup.project_id == Project.id)
        .options(contains_eager(BuildGroup.project))
    )
    if not current_user.is_admin:
        query = query.filter(Project.user_id == current_user.id)
    if project_id:
        query = query.filter(BuildGroup.project_id == project_id)
    query = query.order_by(BuildGroup.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    items = []
    for g in pagination.items:
        items.append({
            "id": g.id,
            "project_id": g.project_id,
            "project_name": g.project.name if g.project else "",
            "trigger_type": g.trigger_type,
            "status": g.status,
            "created_at": g.created_at.isoformat() if g.created_at else None,
            "completed_at": g.completed_at.isoformat() if g.completed_at else None,
        })
    return jsonify({
        "items": items,
        "total": pagination.total,
        "pages": pagination.pages,
        "page": page,
        "per_page": per_page,
    })


@build_bp.route("/builds/<int:group_id>", methods=["GET"])
@login_required
def get_build_group(group_id):
    group = BuildGroup.query.get_or_404(group_id)
    result = _group_to_dict(group)
    result["tasks"] = [_task_to_dict(t) for t in BuildTask.query.filter_by(build_group_id=group_id).all()]
    return jsonify(result)


@build_bp.route("/builds/<int:group_id>/tasks", methods=["GET"])
@login_required
def get_build_group_tasks(group_id):
    tasks = BuildTask.query.filter_by(build_group_id=group_id).all()
    return jsonify([_task_to_dict(t) for t in tasks])


@build_bp.route("/builds/<int:task_id>/cancel", methods=["POST"])
@login_required
def cancel_build(task_id):
    task = BuildTask.query.get_or_404(task_id)
    ok = scheduler.cancel_task(task_id)
    if not ok:
        return jsonify({"error": "任务已结束或无法取消"}), 400
    return jsonify({"message": "已取消构建任务"})


@build_bp.route("/builds/<int:task_id>/log", methods=["GET"])
@login_required
def get_build_log(task_id):
    task = BuildTask.query.get_or_404(task_id)
    return jsonify({
        "output_log": task.output_log or "",
        "error_log": task.error_log or "",
    })


def init_ws(sock):
    """注册 WebSocket 路由（避免循环导入）"""

    @sock.route("/ws/builds/<int:group_id>/log")
    def ws_build_log(ws, group_id):
        """WebSocket 日志流：推送 build group 下任务的日志增量"""
        from flask_login import current_user as ws_user
        import time

        if not ws_user.is_authenticated:
            ws.send("[系统] 未登录\n")
            ws.close()
            return

        group = BuildGroup.query.get(group_id)
        if not group:
            ws.send("[系统] 未找到构建组\n")
            ws.close()
            return

        project = Project.query.get(group.project_id)
        if not project or (project.user_id != ws_user.id and not ws_user.is_admin):
            ws.send("[系统] 无权访问\n")
            ws.close()
            return

        last_len = 0
        while True:
            tasks = BuildTask.query.filter_by(build_group_id=group_id).all()
            if not tasks:
                ws.send("[系统] 未找到构建任务\n")
                break

            full_log = ""
            for task in tasks:
                full_log += task.output_log or ""
                full_log += task.error_log or ""

            if len(full_log) > last_len:
                ws.send(full_log[last_len:])
                last_len = len(full_log)

            # 如果所有任务都已结束，发送完剩余日志后关闭
            if all(t.status in ("success", "failed", "cancelled") for t in tasks):
                break

            try:
                time.sleep(1)
            except Exception:
                break
        ws.close()


@build_bp.route("/artifacts/<int:task_id>/download/<path:filename>")
@login_required
def download_artifact(task_id, filename):
    """下载构建产物"""
    task = BuildTask.query.get_or_404(task_id)
    project = Project.query.get(task.project_id)
    if not project or (project.user_id != current_user.id and not current_user.is_admin):
        return jsonify({"error": "无权访问"}), 403

    artifact = BuildArtifact.query.filter_by(build_task_id=task_id, file_path=filename).first_or_404()
    directory = Config.ARTIFACTS_DIR / str(task_id)
    return send_from_directory(str(directory), filename, as_attachment=True)
