from flask import Blueprint, render_template
from flask_login import login_required

views_bp = Blueprint("views", __name__)


@views_bp.route("/")
@login_required
def index():
    return render_template("dashboard.html")


@views_bp.route("/projects")
@login_required
def projects():
    return render_template("projects.html")


@views_bp.route("/projects/new")
@login_required
def project_new():
    return render_template("project_wizard.html")


@views_bp.route("/projects/<int:project_id>")
@login_required
def project_detail(project_id):
    return render_template("project_detail.html", project_id=project_id)


@views_bp.route("/builds")
@login_required
def builds():
    return render_template("builds.html")


@views_bp.route("/builds/<int:group_id>")
@login_required
def build_detail(group_id):
    return render_template("build_detail.html", group_id=group_id)


@views_bp.route("/images")
@login_required
def images():
    return render_template("images.html")
