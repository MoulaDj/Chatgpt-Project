import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import app

def test_health_endpoint():
    client = app.app.test_client()
    resp = client.get("/__health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
