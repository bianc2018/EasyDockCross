import json
from datetime import datetime

import yaml
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Project, BuildTarget
from app.utils import load_preset_templates

project_bp = Blueprint("project", __name__)


def _project_to_dict(project: Project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "source_type": project.source_type,
        "source_url": project.source_url,
        "source_branch": project.source_branch,
        "triggers": project.triggers or {},
        "preset_key": project.preset_key,
        "user_id": project.user_id,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


def _target_to_dict(target: BuildTarget) -> dict:
    return {
        "id": target.id,
        "project_id": target.project_id,
        "name": target.name,
        "output_type": target.output_type,
        "os": target.os,
        "distro": target.distro,
        "arch": target.arch,
        "image": target.image,
        "build_command": target.build_command,
        "env_vars": target.env_vars or {},
        "artifacts_path": target.artifacts_path,
    }


# ===========================
# Preset Templates
# ===========================

@project_bp.route("/presets", methods=["GET"])
@login_required
def list_presets():
    presets = load_preset_templates(current_app.config["PRESETS_DIR"])
    return jsonify(list(presets.values()))


@project_bp.route("/presets/<key>", methods=["GET"])
@login_required
def get_preset(key):
    presets = load_preset_templates(current_app.config["PRESETS_DIR"])
    preset = presets.get(key)
    if not preset:
        return jsonify({"error": "预设模板不存在"}), 404
    return jsonify(preset)


# ===========================
# Projects CRUD
# ===========================

@project_bp.route("/projects", methods=["GET"])
@login_required
def list_projects():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    query = Project.query.filter_by(user_id=current_user.id).order_by(Project.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "items": [_project_to_dict(p) for p in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "page": page,
        "per_page": per_page,
    })


@project_bp.route("/projects", methods=["POST"])
@login_required
def create_project():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "项目名称不能为空"}), 400

    # 检查重名
    if Project.query.filter_by(name=name, user_id=current_user.id).first():
        return jsonify({"error": "项目名称已存在"}), 409

    project = Project(
        name=name,
        description=data.get("description", "").strip(),
        source_type=data.get("source_type", "git"),
        source_url=data.get("source_url", "").strip(),
        source_branch=data.get("source_branch", "main"),
        source_credentials=data.get("source_credentials"),
        triggers=data.get("triggers") or {},
        preset_key=data.get("preset_key"),
        user_id=current_user.id,
    )
    db.session.add(project)
    db.session.commit()

    # 如果请求中携带了 targets，一并创建
    for t in data.get("targets", []):
        target = BuildTarget(
            project_id=project.id,
            name=t.get("name", "default"),
            output_type=t.get("output_type", "binary"),
            os=t.get("os"),
            distro=t.get("distro"),
            arch=t.get("arch"),
            image=t.get("image", ""),
            build_command=t.get("build_command", ""),
            env_vars=t.get("env_vars") or {},
            artifacts_path=t.get("artifacts_path"),
        )
        db.session.add(target)
    db.session.commit()

    return jsonify(_project_to_dict(project)), 201


@project_bp.route("/projects/<int:project_id>", methods=["GET"])
@login_required
def get_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "无权访问"}), 403
    result = _project_to_dict(project)
    result["targets"] = [_target_to_dict(t) for t in project.targets]
    return jsonify(result)


@project_bp.route("/projects/<int:project_id>", methods=["PUT"])
@login_required
def update_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "无权访问"}), 403

    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if name:
        existing = Project.query.filter_by(name=name, user_id=current_user.id).first()
        if existing and existing.id != project.id:
            return jsonify({"error": "项目名称已存在"}), 409
        project.name = name

    project.description = data.get("description", project.description)
    project.source_type = data.get("source_type", project.source_type)
    project.source_url = data.get("source_url", project.source_url)
    project.source_branch = data.get("source_branch", project.source_branch)
    project.source_credentials = data.get("source_credentials", project.source_credentials)
    project.triggers = data.get("triggers", project.triggers)
    project.preset_key = data.get("preset_key", project.preset_key)
    project.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(_project_to_dict(project))


@project_bp.route("/projects/<int:project_id>", methods=["DELETE"])
@login_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "无权访问"}), 403
    db.session.delete(project)
    db.session.commit()
    return jsonify({"message": "删除成功"})


# ===========================
# Build Targets CRUD
# ===========================

@project_bp.route("/projects/<int:project_id>/targets", methods=["GET"])
@login_required
def list_targets(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "无权访问"}), 403
    return jsonify([_target_to_dict(t) for t in project.targets])


@project_bp.route("/projects/<int:project_id>/targets", methods=["POST"])
@login_required
def create_target(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "无权访问"}), 403

    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    image = data.get("image", "").strip()
    build_command = data.get("build_command", "").strip()
    if not name or not image or not build_command:
        return jsonify({"error": "名称、镜像和构建命令不能为空"}), 400

    target = BuildTarget(
        project_id=project.id,
        name=name,
        output_type=data.get("output_type", "binary"),
        os=data.get("os"),
        distro=data.get("distro"),
        arch=data.get("arch"),
        image=image,
        build_command=build_command,
        env_vars=data.get("env_vars") or {},
        artifacts_path=data.get("artifacts_path"),
    )
    db.session.add(target)
    db.session.commit()
    return jsonify(_target_to_dict(target)), 201


@project_bp.route("/targets/<int:target_id>", methods=["GET"])
@login_required
def get_target(target_id):
    target = BuildTarget.query.get_or_404(target_id)
    if target.project.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "无权访问"}), 403
    return jsonify(_target_to_dict(target))


@project_bp.route("/targets/<int:target_id>", methods=["PUT"])
@login_required
def update_target(target_id):
    target = BuildTarget.query.get_or_404(target_id)
    if target.project.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "无权访问"}), 403

    data = request.get_json(silent=True) or {}
    target.name = data.get("name", target.name)
    target.output_type = data.get("output_type", target.output_type)
    target.os = data.get("os", target.os)
    target.distro = data.get("distro", target.distro)
    target.arch = data.get("arch", target.arch)
    target.image = data.get("image", target.image)
    target.build_command = data.get("build_command", target.build_command)
    target.env_vars = data.get("env_vars", target.env_vars)
    target.artifacts_path = data.get("artifacts_path", target.artifacts_path)
    db.session.commit()
    return jsonify(_target_to_dict(target))


@project_bp.route("/targets/<int:target_id>", methods=["DELETE"])
@login_required
def delete_target(target_id):
    target = BuildTarget.query.get_or_404(target_id)
    if target.project.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "无权访问"}), 403
    db.session.delete(target)
    db.session.commit()
    return jsonify({"message": "删除成功"})


# ===========================
# YAML Import / Export
# ===========================

@project_bp.route("/projects/<int:project_id>/export", methods=["GET"])
@login_required
def export_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "无权访问"}), 403

    data = _project_to_dict(project)
    data["targets"] = [_target_to_dict(t) for t in project.targets]
    # 移除 id / user_id 等运行时字段
    for key in ("id", "user_id", "created_at", "updated_at"):
        data.pop(key, None)
    for t in data.get("targets", []):
        for key in ("id", "project_id"):
            t.pop(key, None)

    yaml_text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    return yaml_text, 200, {"Content-Type": "text/yaml; charset=utf-8"}


@project_bp.route("/projects/import", methods=["POST"])
@login_required
def import_project():
    data = request.get_json(silent=True) or {}
    yaml_text = data.get("yaml") or request.get_data(as_text=True)
    if not yaml_text:
        return jsonify({"error": "YAML 内容不能为空"}), 400

    try:
        payload = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        return jsonify({"error": f"YAML 解析失败: {e}"}), 400

    if not isinstance(payload, dict):
        return jsonify({"error": "YAML 格式不正确"}), 400

    name = payload.get("name", "").strip()
    if not name:
        return jsonify({"error": "项目名称不能为空"}), 400
    if Project.query.filter_by(name=name, user_id=current_user.id).first():
        return jsonify({"error": "项目名称已存在"}), 409

    project = Project(
        name=name,
        description=payload.get("description", ""),
        source_type=payload.get("source_type", "git"),
        source_url=payload.get("source_url", ""),
        source_branch=payload.get("source_branch", "main"),
        source_credentials=payload.get("source_credentials"),
        triggers=payload.get("triggers") or {},
        preset_key=payload.get("preset_key"),
        user_id=current_user.id,
    )
    db.session.add(project)
    db.session.commit()

    for t in payload.get("targets", []):
        target = BuildTarget(
            project_id=project.id,
            name=t.get("name", "default"),
            output_type=t.get("output_type", "binary"),
            os=t.get("os"),
            distro=t.get("distro"),
            arch=t.get("arch"),
            image=t.get("image", ""),
            build_command=t.get("build_command", ""),
            env_vars=t.get("env_vars") or {},
            artifacts_path=t.get("artifacts_path"),
        )
        db.session.add(target)
    db.session.commit()

    return jsonify(_project_to_dict(project)), 201
