import os
import secrets
from datetime import datetime

import bcrypt
from flask import Flask

from app.config import get_config
from app.extensions import db, login_manager, migrate
from app.models import User


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"),
        static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "static"),
    )

    config_class = get_config()
    app.config.from_object(config_class)
    config_class.init_directories()

    # 初始化扩展
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login_page"
    login_manager.login_message = "请先登录"
    login_manager.remember_cookie_duration = app.config.get("REMEMBER_COOKIE_DURATION")
    login_manager.remember_cookie_secure = app.config.get("REMEMBER_COOKIE_SECURE", False)
    login_manager.remember_cookie_httponly = app.config.get("REMEMBER_COOKIE_HTTPONLY", True)
    login_manager.remember_cookie_samesite = app.config.get("REMEMBER_COOKIE_SAMESITE", "Lax")

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # 注册蓝图（延迟导入避免循环依赖）
    from app.auth import auth_bp
    from app.api import api_bp
    from app.project import project_bp
    from app.build import build_bp, scheduler
    from app.image_manager import image_bp
    from app.views import views_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    app.register_blueprint(project_bp, url_prefix="/api/v1")
    app.register_blueprint(build_bp, url_prefix="/api/v1")
    app.register_blueprint(image_bp, url_prefix="/api/v1")
    app.register_blueprint(views_bp)

    scheduler.init_app(app)

    with app.app_context():
        db.create_all()
        _seed_admin_user(app)

    return app


def _seed_admin_user(app: Flask):
    """首次启动时自动创建 admin 用户并输出随机密码到 stdout"""
    admin = User.query.filter_by(username="admin").first()
    if admin is None:
        password = secrets.token_urlsafe(16)
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        admin = User(
            username="admin",
            password_hash=password_hash,
            is_admin=True,
            created_at=datetime.utcnow(),
        )
        db.session.add(admin)
        db.session.commit()

        # 在多进程部署场景下可能打印多次，但 MVP 阶段单进程可接受
        print("=" * 60)
        print("EasyDockCross 首次启动，已创建默认管理员账号")
        print(f"用户名: admin")
        print(f"密码:   {password}")
        print("=" * 60)
