"""Fixtures pytest pour NAMARA."""
import pytest

from app import create_app
from app.extensions import db as _db


@pytest.fixture()
def app(tmp_path):
    db_path = tmp_path / "namara_test.db"
    app = create_app("testing")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["SERVER_NAME"] = "localhost"
    with app.app_context():
        _db.create_all()
    yield app
    with app.app_context():
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    with app.app_context():
        yield _db
