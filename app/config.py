import os
from datetime import timedelta
from pathlib import Path


class Config:
    """Flask 应用配置"""

    # 基础
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")
    FLASK_ENV = os.environ.get("FLASK_ENV", "production")

    # 数据目录
    DATA_DIR = Path(os.environ.get("DATA_DIR", "/var/lib/easydockcross"))
    if os.environ.get("DATA_DIR") is None:
        DATA_DIR = Path(__file__).resolve().parent.parent / "data"

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 数据库
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{DATA_DIR / 'easydockcross.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Docker
    DOCKER_SOCKET = os.environ.get("DOCKER_SOCKET", "unix:///var/run/docker.sock")
    DOCKER_MEM_LIMIT = os.environ.get("DOCKER_MEM_LIMIT", "2g")

    # 构建限制
    MAX_CONCURRENT_BUILDS = int(os.environ.get("MAX_CONCURRENT_BUILDS", "3"))
    BUILD_TIMEOUT_SECONDS = int(os.environ.get("BUILD_TIMEOUT_SECONDS", "7200"))
    BUILD_QUEUE_MAX_SIZE = int(os.environ.get("BUILD_QUEUE_MAX_SIZE", "100"))

    # 保留策略
    LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", "30"))
    ARTIFACT_RETENTION_DAYS = int(os.environ.get("ARTIFACT_RETENTION_DAYS", "30"))
    MAX_BUILDS_PER_PROJECT = int(os.environ.get("MAX_BUILDS_PER_PROJECT", "50"))

    # 会话
    REMEMBER_COOKIE_DURATION = timedelta(hours=24)
    REMEMBER_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # 上传限制
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB

    # 预设模板目录
    PRESETS_DIR = Path(__file__).resolve().parent.parent / "presets"

    # 缓存目录
    CACHE_BASE_DIR = DATA_DIR / "cache"
    ARTIFACTS_DIR = DATA_DIR / "artifacts"
    UPLOADS_DIR = DATA_DIR / "uploads"
    LOGS_DIR = DATA_DIR / "logs"

    @classmethod
    def init_directories(cls):
        """确保所有工作目录存在"""
        for d in [
            cls.DATA_DIR,
            cls.CACHE_BASE_DIR,
            cls.ARTIFACTS_DIR,
            cls.UPLOADS_DIR,
            cls.LOGS_DIR,
        ]:
            d.mkdir(parents=True, exist_ok=True)


class DevelopmentConfig(Config):
    DEBUG = True
    FLASK_ENV = "development"


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False
    FLASK_ENV = "production"


config_map = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

def get_config():
    env = os.environ.get("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)
