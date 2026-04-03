import pytest
from app.app import create_app
from app.extensions import db
from app.models import User
import bcrypt


@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
    })

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_user(app):
    with app.app_context():
        # create_app 已自动创建 admin 用户；覆盖密码以便测试登录
        user = User.query.filter_by(username="admin").first()
        if user is None:
            user = User(username="admin", is_admin=True)
            db.session.add(user)
        user.password_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode("utf-8")
        db.session.commit()
        return user.id
