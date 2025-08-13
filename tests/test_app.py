import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import app

def reset_db():
    with app.app.app_context():
        app.db.drop_all()
        app.db.create_all()


def test_health_endpoint():
    reset_db()
    client = app.app.test_client()
    resp = client.get("/__health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"


def test_class_form_lists_existing():
    reset_db()
    with app.app.app_context():
        app.db.session.add(app.Class(name="Math"))
        app.db.session.commit()
    client = app.app.test_client()
    resp = client.get("/classes/new")
    assert resp.status_code == 200
    assert b"Math" in resp.data


def test_speciality_form_lists_existing():
    reset_db()
    with app.app.app_context():
        app.db.session.add(app.Speciality(name="Physics"))
        app.db.session.commit()
    client = app.app.test_client()
    resp = client.get("/specialities/new")
    assert resp.status_code == 200
    assert b"Physics" in resp.data
