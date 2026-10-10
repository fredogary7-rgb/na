"""Tests d'authentification."""
from app.models import User

from tests.helpers import login, register


def test_registration_creates_user(app, client, db):
    resp = register(client)
    assert resp.status_code == 200
    user = User.query.filter_by(phone_number="+22997000002").first()
    assert user is not None
    assert user.full_name == "New User"
    # Le mot de passe n'est pas stocké en clair.
    assert user.password_hash != "password123"
    assert user.check_password("password123")


def test_phone_uniqueness(app, client, db):
    register(client)
    register(client)  # même numéro
    assert User.query.filter_by(phone_number="+22997000002").count() == 1


def test_login_success(app, client, db):
    from tests.helpers import make_user

    make_user(db)
    db.session.commit()
    resp = login(client)
    assert resp.status_code == 200


def test_login_wrong_password(app, client, db):
    from tests.helpers import make_user

    make_user(db)
    db.session.commit()
    resp = login(client, password="wrong-password")
    assert resp.status_code == 200
    # Ne doit pas être connecté.
    assert b"Identifiants incorrects" in resp.data
