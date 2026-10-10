"""Tests de sécurité des routes administratives."""
from tests.helpers import login, make_user


def test_admin_route_forbidden_for_user(app, client, db):
    user = make_user(db, role="user")
    db.session.commit()
    login(client, user.phone_number)
    resp = client.get("/admin/")
    assert resp.status_code == 403


def test_admin_route_accessible_for_admin(app, client, db):
    admin = make_user(db, role="admin")
    db.session.commit()
    login(client, admin.phone_number)
    resp = client.get("/admin/")
    assert resp.status_code == 200


def test_admin_route_redirects_anonymous(app, client):
    resp = client.get("/admin/")
    assert resp.status_code == 302  # redirection vers la connexion
