import json
import re
import shlex
import shutil
import tempfile
import threading
from datetime import datetime
from pathlib import Path

import docker
from docker.errors import BuildError
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models import CustomImage
from app.utils import PathResolver

image_bp = Blueprint("image", __name__)


def _image_to_dict(image: CustomImage) -> dict:
    return {
        "id": image.id,
        "name": image.name,
        "description": image.description,
        "base_image": image.base_image,
        "config_yaml": image.config_yaml,
        "generated_dockerfile": image.generated_dockerfile,
        "status": image.status,
        "image_id": image.image_id,
        "build_log": image.build_log,
        "created_at": image.created_at.isoformat() if image.created_at else None,
        "updated_at": image.updated_at.isoformat() if image.updated_at else None,
    }


def _validate_dockerfile_input(base_image: str, config: dict) -> None:
    """基础校验，防止 Dockerfile 注入"""
    if not base_image or "\n" in base_image or " " in base_image:
        raise ValueError("基础镜像格式无效")

    for pkg in config.get("system_packages", []):
        if not isinstance(pkg, str) or "\n" in pkg or " " in pkg or any(c in pkg for c in ";|&$`"):
            raise ValueError(f"非法的系统依赖包: {pkg}")

    for tool in config.get("tools", []):
        if not isinstance(tool, str) or "\n" in tool or " " in tool or any(c in tool for c in ";|&$`"):
            raise ValueError(f"非法的开发工具: {tool}")

    env_vars = config.get("env_vars", {})
    for k, v in env_vars.items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(k)):
            raise ValueError(f"非法的环境变量名: {k}")
        if "\n" in str(v):
            raise ValueError(f"环境变量值不能包含换行: {k}")

    pre_build = config.get("pre_build_script", "")
    if "\n" in pre_build:
        raise ValueError("预构建脚本不能包含换行符")


def generate_dockerfile(base_image: str, config: dict) -> str:
    """根据简单模式配置自动生成 Dockerfile"""
    _validate_dockerfile_input(base_image, config)
    lines = [f"FROM {base_image}"]

    # 系统依赖包
    packages = config.get("system_packages", [])
    if packages:
        lines.append(
            f"RUN apt-get update && apt-get install -y {' '.join(packages)} && rm -rf /var/lib/apt/lists/*"
        )

    # 开发工具
    tools = config.get("tools", [])
    if tools:
        lines.append(
            f"RUN apt-get update && apt-get install -y {' '.join(tools)} && rm -rf /var/lib/apt/lists/*"
        )

    # ccache 支持（C++ 构建缓存）
    if config.get("use_ccache", False):
        lines.append(
            "RUN apt-get update && apt-get install -y ccache && rm -rf /var/lib/apt/lists/*"
        )
        lines.append("ENV CCACHE_DIR=/ccache")

    # 环境变量
    env_vars = config.get("env_vars", {})
    for k, v in env_vars.items():
        lines.append(f"ENV {k}={shlex.quote(str(v))}")

    # 预构建脚本
    pre_build = config.get("pre_build_script", "")
    if pre_build.strip():
        lines.append(f"RUN {pre_build.strip()}")

    return "\n".join(lines) + "\n"


@image_bp.route("/images", methods=["GET"])
@login_required
def list_images():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    pagination = CustomImage.query.order_by(CustomImage.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        "items": [_image_to_dict(i) for i in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "page": page,
        "per_page": per_page,
    })


@image_bp.route("/images", methods=["POST"])
@login_required
def create_image():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    base_image = data.get("base_image", "").strip()

    if not name or not base_image:
        return jsonify({"error": "名称和基础镜像不能为空"}), 400

    if CustomImage.query.filter_by(name=name).first():
        return jsonify({"error": "镜像名称已存在"}), 409

    mode = data.get("mode", "simple")
    config = data.get("config", {})

    if mode == "simple":
        dockerfile = generate_dockerfile(base_image, config)
        config_yaml = json.dumps(config, ensure_ascii=False)
    else:
        # 复杂模式：用户直接传入 Dockerfile 文本
        dockerfile = config.get("dockerfile", "")
        config_yaml = json.dumps(config, ensure_ascii=False)

    image = CustomImage(
        name=name,
        description=data.get("description", ""),
        base_image=base_image,
        config_yaml=config_yaml,
        generated_dockerfile=dockerfile,
        status="ready",
    )
    db.session.add(image)
    db.session.commit()
    return jsonify(_image_to_dict(image)), 201


@image_bp.route("/images/<int:image_id>", methods=["GET"])
@login_required
def get_image(image_id):
    image = CustomImage.query.get_or_404(image_id)
    return jsonify(_image_to_dict(image))


@image_bp.route("/images/<int:image_id>", methods=["PUT"])
@login_required
def update_image(image_id):
    image = CustomImage.query.get_or_404(image_id)
    data = request.get_json(silent=True) or {}

    name = data.get("name", "").strip()
    if name:
        existing = CustomImage.query.filter_by(name=name).first()
        if existing and existing.id != image.id:
            return jsonify({"error": "镜像名称已存在"}), 409
        image.name = name

    base_image = data.get("base_image", "").strip()
    if base_image:
        image.base_image = base_image

    image.description = data.get("description", image.description)
    mode = data.get("mode", "simple")
    config = data.get("config", {})

    if mode == "simple":
        image.generated_dockerfile = generate_dockerfile(image.base_image, config)
        image.config_yaml = json.dumps(config, ensure_ascii=False)
    else:
        image.generated_dockerfile = config.get("dockerfile", image.generated_dockerfile)
        image.config_yaml = json.dumps(config, ensure_ascii=False)

    image.status = "ready"
    image.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(_image_to_dict(image))


@image_bp.route("/images/<int:image_id>", methods=["DELETE"])
@login_required
def delete_image(image_id):
    image = CustomImage.query.get_or_404(image_id)
    db.session.delete(image)
    db.session.commit()
    return jsonify({"message": "删除成功"})


@image_bp.route("/images/preview", methods=["POST"])
@login_required
def preview_dockerfile():
    """预览自动生成的 Dockerfile"""
    data = request.get_json(silent=True) or {}
    base_image = data.get("base_image", "").strip()
    config = data.get("config", {})
    if not base_image:
        return jsonify({"error": "基础镜像不能为空"}), 400
    dockerfile = generate_dockerfile(base_image, config)
    return jsonify({"dockerfile": dockerfile})


@image_bp.route("/images/<int:image_id>/build", methods=["POST"])
@login_required
def build_image(image_id):
    """异步构建自定义镜像"""
    image = CustomImage.query.get_or_404(image_id)
    if not image.generated_dockerfile:
        return jsonify({"error": "未生成 Dockerfile"}), 400

    image.status = "building"
    image.build_log = ""
    db.session.commit()

    t = threading.Thread(target=_do_build_image, args=(image.id,), daemon=True)
    t.start()
    return jsonify({"message": "构建已启动", "image_id": image.id})


def _do_build_image(image_id: int):
    """后台线程执行 Docker 镜像构建"""
    from app.app import create_app

    app = create_app()
    with app.app_context():
        image = CustomImage.query.get(image_id)
        if not image:
            return

        resolver = PathResolver()
        try:
            client = docker.DockerClient(base_url=resolver.get_docker_socket())
        except Exception as e:
            image.status = "failed"
            image.build_log = f"[系统] 无法连接 Docker: {e}\n"
            db.session.commit()
            return

        # 创建临时目录写入 Dockerfile
        tmpdir = Path(tempfile.mkdtemp(prefix="edc_image_build_"))
        dockerfile_path = tmpdir / "Dockerfile"
        dockerfile_path.write_text(image.generated_dockerfile, encoding="utf-8")

        try:
            logs = []
            tag_name = image.name.lower().replace(" ", "-").replace("_", "-")
            for line in client.api.build(
                path=str(tmpdir),
                tag=f"easydockcross/{tag_name}:latest",
                rm=True,
                decode=True,
            ):
                if "stream" in line:
                    logs.append(line["stream"])
                elif "errorDetail" in line:
                    logs.append(line["errorDetail"].get("message", ""))

            image.build_log = "".join(logs)
            image.status = "ready"
            db.session.commit()
        except BuildError as e:
            logs = []
            for chunk in e.build_log:
                if isinstance(chunk, dict):
                    logs.append(chunk.get("stream", ""))
                else:
                    logs.append(str(chunk))
            image.build_log = "".join(logs)
            image.status = "failed"
            db.session.commit()
        except Exception as e:
            image.build_log = f"[系统] 构建异常: {e}\n"
            image.status = "failed"
            db.session.commit()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


@image_bp.route("/images/<int:image_id>/build-log", methods=["GET"])
@login_required
def get_build_log(image_id):
    image = CustomImage.query.get_or_404(image_id)
    return jsonify({"status": image.status, "build_log": image.build_log or ""})
