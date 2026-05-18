import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import app


def setup_module(module):
    app.app.config["WTF_CSRF_ENABLED"] = False
    with app.app.app_context():
        app.db.drop_all()
        app.db.create_all()
        app._seed_if_empty()


def test_health_endpoint():
    client = app.app.test_client()
    resp = client.get("/__health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["employees"] >= 1


def test_create_leave_request_and_reserve_balance():
    client = app.app.test_client()
    with app.app.app_context():
        employee = app.Employee.query.filter_by(email="yassine@company.com").first()
        assert employee is not None
        before_reserved = employee.leave_reserved

    resp = client.post(
        "/requests/new",
        data={
            "employee_id": employee.id,
            "request_type": "LEAVE",
            "start_date": "2026-06-01",
            "end_date": "2026-06-02",
            "quantity": "2",
            "reason": "Test congé",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app.app_context():
        employee = app.Employee.query.get(employee.id)
        assert employee.leave_reserved == before_reserved + 2
        req = app.LeaveRequest.query.order_by(app.LeaveRequest.id.desc()).first()
        assert req.status == "PENDING_FUNCTIONAL"


def test_approval_flow_to_hr_stage_consumes_balance():
    client = app.app.test_client()
    with app.app.app_context():
        employee = app.Employee.query.filter_by(email="yassine@company.com").first()
        req = app.LeaveRequest(
            employee_id=employee.id,
            request_type="LEAVE",
            start_date=app.date(2026, 7, 1),
            end_date=app.date(2026, 7, 1),
            quantity=1,
            status="PENDING_FUNCTIONAL",
        )
        ok, _ = app.reserve_balance(employee, "LEAVE", 1)
        assert ok
        before_balance = employee.leave_balance
        app.db.session.add(req)
        app.db.session.commit()
        req_id = req.id

    resp = client.post(f"/requests/{req_id}/functional/approve", follow_redirects=True)
    assert resp.status_code == 200
    resp = client.post(f"/requests/{req_id}/hierarchical/approve", follow_redirects=True)
    assert resp.status_code == 200

    with app.app.app_context():
        req = app.LeaveRequest.query.get(req_id)
        employee = app.Employee.query.get(req.employee_id)
        assert req.status == "PENDING_HR"
        assert employee.leave_balance == before_balance - 1
