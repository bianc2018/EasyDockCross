from flask import Blueprint, render_template_string
from flask_login import login_required

views_bp = Blueprint("views", __name__)


@views_bp.route("/")
@login_required
def index():
    return render_template_string(INDEX_HTML)


INDEX_HTML = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EasyDockCross</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-dark bg-dark">
  <div class="container">
    <a class="navbar-brand" href="#">EasyDockCross</a>
    <div class="collapse navbar-collapse">
      <ul class="navbar-nav ms-auto">
        <li class="nav-item"><a class="nav-link" href="/logout">登出</a></li>
      </ul>
    </div>
  </div>
</nav>
<div class="container mt-5">
  <div class="p-5 mb-4 bg-light rounded-3">
    <div class="container-fluid py-5">
      <h1 class="display-5 fw-bold">EasyDockCross</h1>
      <p class="col-md-8 fs-4">简单的 Docker 交叉构建系统。项目初始化完成，请继续开发后续模块。</p>
      <a class="btn btn-primary btn-lg" href="/api/v1/health" target="_blank">检查 API 健康状态</a>
      <a class="btn btn-outline-secondary btn-lg" href="/api/v1/health/dependencies" target="_blank">查看依赖检查</a>
    </div>
  </div>
</div>
</body>
</html>
"""
