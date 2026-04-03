from datetime import datetime
from flask_login import UserMixin
from app.extensions import db


class User(UserMixin, db.Model):
    """用户表"""
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    projects = db.relationship("Project", backref="owner", lazy="dynamic")

    def __repr__(self):
        return f"<User {self.username}>"


class Project(db.Model):
    """项目表"""
    __tablename__ = "project"
    __table_args__ = (db.UniqueConstraint("name", "user_id", name="uix_project_name_user"),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 源码来源配置
    source_type = db.Column(db.String(20), default="git")  # git / svn / upload
    source_url = db.Column(db.Text, nullable=True)
    source_branch = db.Column(db.String(80), default="main")
    source_credentials = db.Column(db.Text, nullable=True)  # JSON 格式存储凭证

    # 触发方式配置
    triggers = db.Column(db.JSON, default=dict)

    # 预设模板
    preset_key = db.Column(db.String(80), nullable=True)

    # 关联
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    targets = db.relationship("BuildTarget", backref="project", lazy="dynamic", cascade="all, delete-orphan")
    build_groups = db.relationship("BuildGroup", backref="project", lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project {self.name}>"


class BuildTarget(db.Model):
    """构建目标表（多目标支持）"""
    __tablename__ = "build_target"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)

    output_type = db.Column(db.String(20), default="binary")  # binary / docker
    os = db.Column(db.String(20), nullable=True)  # linux / windows / macos
    distro = db.Column(db.String(40), nullable=True)  # debian / ubuntu / alpine
    arch = db.Column(db.String(20), nullable=True)  # x86_64 / arm64 / armv7

    image = db.Column(db.String(255), nullable=False)
    build_command = db.Column(db.Text, nullable=False)
    build_tool = db.Column(db.String(20), nullable=True)  # cmake / xmake / make / null
    env_vars = db.Column(db.JSON, default=dict)
    artifacts_path = db.Column(db.String(255), nullable=True)

    tasks = db.relationship("BuildTask", backref="target", lazy="dynamic")

    def __repr__(self):
        return f"<BuildTarget {self.name}>"


class BuildGroup(db.Model):
    """构建任务组（一次构建包含多个目标）"""
    __tablename__ = "build_group"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    trigger_type = db.Column(db.String(20), default="manual")  # manual / webhook / cron
    status = db.Column(db.String(20), default="pending")  # pending / running / success / failed / cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    tasks = db.relationship("BuildTask", backref="build_group", lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BuildGroup {self.id} {self.status}>"


class BuildTask(db.Model):
    """单个构建任务"""
    __tablename__ = "build_task"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    target_id = db.Column(db.Integer, db.ForeignKey("build_target.id"), nullable=False)
    build_group_id = db.Column(db.Integer, db.ForeignKey("build_group.id"), nullable=False)

    status = db.Column(db.String(20), default="pending")  # pending / running / success / failed / cancelled
    container_id = db.Column(db.String(255), nullable=True)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    output_log = db.Column(db.Text, nullable=True)
    error_log = db.Column(db.Text, nullable=True)

    artifacts = db.relationship("BuildArtifact", backref="build_task", lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BuildTask {self.id} {self.status}>"


class BuildArtifact(db.Model):
    """构建产物表"""
    __tablename__ = "build_artifact"

    id = db.Column(db.Integer, primary_key=True)
    build_task_id = db.Column(db.Integer, db.ForeignKey("build_task.id"), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    file_size = db.Column(db.BigInteger, default=0)
    download_url = db.Column(db.String(512), nullable=True)

    def __repr__(self):
        return f"<BuildArtifact {self.file_path}>"


class CustomImage(db.Model):
    """自定义镜像表"""
    __tablename__ = "custom_image"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    base_image = db.Column(db.String(255), nullable=False)

    config_yaml = db.Column(db.Text, nullable=False)
    generated_dockerfile = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(20), default="building")  # building / ready / failed
    image_id = db.Column(db.String(255), nullable=True)
    build_log = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<CustomImage {self.name}>"


class DependencyCheck(db.Model):
    """系统依赖检查记录表"""
    __tablename__ = "dependency_check"

    id = db.Column(db.Integer, primary_key=True)
    component = db.Column(db.String(80), nullable=False)  # docker / python 等
    status = db.Column(db.String(20), nullable=False)  # ok / missing / error
    version = db.Column(db.String(80), nullable=True)
    message = db.Column(db.Text, nullable=True)
    install_command = db.Column(db.Text, nullable=True)
    checked_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DependencyCheck {self.component} {self.status}>"
