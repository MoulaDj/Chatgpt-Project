import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import app


def setup_module(module):
    """Prepare a fresh database for tests."""
    app.app.config["WTF_CSRF_ENABLED"] = False
    with app.app.app_context():
        app.db.drop_all()
        app.db.create_all()

def test_health_endpoint():
    client = app.app.test_client()
    resp = client.get("/__health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"


def test_create_edit_student_fields():
    client = app.app.test_client()
    # create a student with new fields
    resp = client.post(
        "/students/new",
        data={
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "phone": "",
            "birthdate": "",
            "speciality": "Math",
            "student_class": "1A",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app.app_context():
        s = app.Student.query.filter_by(email="john@example.com").first()
        assert s is not None
        assert s.speciality == "Math"
        assert s.student_class == "1A"
        student_id = s.id

    # edit the student
    resp = client.post(
        f"/students/{student_id}/edit",
        data={
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "phone": "",
            "birthdate": "",
            "speciality": "Physics",
            "student_class": "2B",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app.app_context():
        s = app.Student.query.get(student_id)
        assert s.speciality == "Physics"
        assert s.student_class == "2B"

    resp = client.get(f"/students/{student_id}")
    assert b"Physics" in resp.data
    assert b"2B" in resp.data
