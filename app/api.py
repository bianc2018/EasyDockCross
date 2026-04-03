from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app.dependency_check import DockerDependencyChecker

api_bp = Blueprint("api", __name__)


@api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "EasyDockCross"})


@api_bp.route("/health/dependencies", methods=["GET"])
def health_dependencies():
    """获取依赖检查结果"""
    checker = DockerDependencyChecker()
    results = checker.check_all()
    return jsonify(results)


@api_bp.route("/health/dependencies/install", methods=["POST"])
def auto_install():
    """触发自动安装（当前仅支持 Ubuntu/Debian 的 Docker）"""
    data = request.get_json(silent=True) or {}
    component = data.get("component", "docker")
    checker = DockerDependencyChecker()
    result = checker.run_auto_install(component)
    return jsonify(result)


@api_bp.route("/health/images/predownload", methods=["POST"])
def predownload_images():
    """触发预下载常用镜像"""
    checker = DockerDependencyChecker()
    outcomes = checker.predownload_images()
    return jsonify({"results": outcomes})


# ===========================
# 以下路由为占位，后续 TASK 逐步实现
# ===========================

@api_bp.route("/projects", methods=["GET"])
@login_required
def list_projects():
    return jsonify({"message": "TODO: 项目列表", "user": current_user.username})


@api_bp.route("/builds", methods=["GET"])
@login_required
def list_builds():
    return jsonify({"message": "TODO: 构建列表"})
