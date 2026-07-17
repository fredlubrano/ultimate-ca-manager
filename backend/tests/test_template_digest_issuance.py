"""Issuance must honor template digest and persist template_id (#207)."""
from tests.conftest import get_json


def test_issue_honors_template_digest_and_template_id(app, auth_client, create_ca):
    ca = create_ca(cn="Digest CA")
    r = auth_client.post(
        "/api/v2/templates",
        json={
            "name": "SHA384 Web",
            "description": "lab",
            "template_type": "web_server",
            "key_type": "RSA-2048",
            "digest": "sha384",
            "validity_days": 90,
        },
    )
    assert r.status_code in (200, 201), r.get_data(as_text=True)
    tpl_id = (get_json(r).get("data") or get_json(r))["id"]

    r = auth_client.post(
        "/api/v2/certificates",
        json={
            "ca_id": ca["id"],
            "cn": "digest.example.test",
            "cert_type": "server",
            "key_type": "rsa",
            "key_size": 2048,
            "validity_days": 30,
            "template_id": tpl_id,
        },
    )
    assert r.status_code in (200, 201), r.get_data(as_text=True)
    body = get_json(r).get("data") or get_json(r)
    cert_id = body.get("id") or body.get("certificate", {}).get("id")
    assert cert_id

    with app.app_context():
        import base64
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        from models import Certificate, db

        row = db.session.get(Certificate, cert_id)
        assert row.template_id == tpl_id
        pem = base64.b64decode(row.crt)
        leaf = x509.load_pem_x509_certificate(pem, default_backend())
        assert leaf.signature_hash_algorithm.name.lower() == "sha384"
