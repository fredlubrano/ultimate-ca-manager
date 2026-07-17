"""Template usage_count must reflect live Certificate.template_id rows."""
from tests.conftest import get_json


def test_template_usage_count_live(app, auth_client, create_cert):
    r = auth_client.post(
        "/api/v2/templates",
        json={
            "name": "Usage Count Lab",
            "description": "lab",
            "template_type": "web_server",
            "key_type": "RSA-2048",
            "digest": "sha256",
            "validity_days": 365,
        },
    )
    assert r.status_code in (200, 201), r.get_data(as_text=True)
    tpl = get_json(r).get("data") or get_json(r)
    tpl_id = tpl["id"]

    r = auth_client.get(f"/api/v2/templates/{tpl_id}")
    assert r.status_code == 200
    data = get_json(r).get("data") or get_json(r)
    assert data.get("usage_count") == 0

    # Attach a certificate to the template (issuance digest path is a separate PR)
    with app.app_context():
        from models import Certificate, db

        cert = create_cert(cn="usage.example.test")
        row = db.session.get(Certificate, cert["id"])
        row.template_id = tpl_id
        db.session.commit()

    r = auth_client.get(f"/api/v2/templates/{tpl_id}")
    assert r.status_code == 200
    data = get_json(r).get("data") or get_json(r)
    assert data.get("usage_count") == 1
