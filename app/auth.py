from datetime import datetime

import bcrypt
from flask import Blueprint, request, jsonify, redirect, url_for, render_template
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login_page():
    """登录页面"""
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
            login_user(user, remember=True)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("views.index"))
        error = "用户名或密码错误"
        status_code = 401
    else:
        status_code = 200

    return render_template("login.html", error=error), status_code


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login_page"))


@auth_bp.route("/api/v1/login", methods=["POST"])
def api_login():
    """API 登录接口（供 CLI 和前端 AJAX 使用）"""
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
        return jsonify({"error": "用户名或密码错误"}), 401

    login_user(user, remember=True)
    return jsonify({"user_id": user.id, "username": user.username, "is_admin": user.is_admin})


@auth_bp.route("/api/v1/logout", methods=["POST"])
@login_required
def api_logout():
    logout_user()
    return jsonify({"message": "已登出"})


@auth_bp.route("/api/v1/users/me", methods=["GET"])
@login_required
def get_current_user():
    """获取当前登录用户信息"""
    return jsonify({
        "id": current_user.id,
        "username": current_user.username,
        "is_admin": current_user.is_admin,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    })


@auth_bp.route("/api/v1/users/me/password", methods=["PUT"])
@login_required
def change_password():
    """修改当前用户密码"""
    data = request.get_json(silent=True) or {}
    old_password = data.get("old_password")
    new_password = data.get("new_password")

    if not old_password or not new_password:
        return jsonify({"error": "旧密码和新密码不能为空"}), 400

    if len(new_password) < 8:
        return jsonify({"error": "新密码长度至少为 8 位"}), 400

    if not bcrypt.checkpw(old_password.encode("utf-8"), current_user.password_hash.encode("utf-8")):
        return jsonify({"error": "旧密码错误"}), 401

    current_user.password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    db.session.commit()
    return jsonify({"message": "密码修改成功"})


@auth_bp.route("/api/v1/users", methods=["GET"])
@login_required
def list_users():
    """用户列表（仅管理员）"""
    if not current_user.is_admin:
        return jsonify({"error": "无权访问"}), 403

    users = User.query.all()
    return jsonify([{
        "id": u.id,
        "username": u.username,
        "is_admin": u.is_admin,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    } for u in users])


@auth_bp.route("/api/v1/users/<int:user_id>/reset-password", methods=["POST"])
@login_required
def admin_reset_password(user_id):
    """管理员重置指定用户密码"""
    if not current_user.is_admin:
        return jsonify({"error": "无权访问"}), 403

    user = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}
    new_password = data.get("new_password")

    if not new_password:
        # 未提供密码则自动生成随机密码
        import secrets
        new_password = secrets.token_urlsafe(16)

    if len(new_password) < 8:
        return jsonify({"error": "密码长度至少为 8 位"}), 400

    user.password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    db.session.commit()
    return jsonify({"message": "密码重置成功", "new_password": new_password})
