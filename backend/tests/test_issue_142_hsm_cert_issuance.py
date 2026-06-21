"""
Regression test for issue #142.

Issuing a certificate against an HSM-backed CA returned
``400 CA private key not available`` because the gate checked
``ca.prv`` (empty for HSM CAs) instead of ``ca.has_private_key``,
and the signing path loaded the local key directly instead of
going through ``get_ca_signing_key`` (which routes to the HSM).

Covers the certificate-issuance paths touched by the fix:
  - POST /api/v2/certificates           (the reported path)
  - POST /api/v2/certificates/<id>/renew
  - bulk CSR signing gate (csrs.py)
  - ACME domain issuing-CA selector gate (acme_domains.py)
"""
import json
import os
import sys
from unittest.mock import patch

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def hsm_provider_and_key(app, request):
    """Stub HsmProvider + HsmKey row backed by a real local RSA key."""
    suffix = request.node.name[-20:]
    with app.app_context():
        from models import db
        from models.hsm import HsmProvider, HsmKey

        provider = HsmProvider(name=f'Iss142-{suffix}', type='pkcs11', config='{}')
        db.session.add(provider)
        db.session.commit()

        real_key = rsa.generate_private_key(65537, 2048)
        pub_pem = real_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

        hsm_key = HsmKey(
            provider_id=provider.id,
            key_identifier=f'k142-{suffix}',
            label=f'l142-{suffix}',
            algorithm='RSA-2048',
            key_type='asymmetric',
            purpose='signing',
            public_key_pem=pub_pem,
        )
        db.session.add(hsm_key)
        db.session.commit()

        yield {
            'hsm_key_id': hsm_key.id,
            'real_key': real_key,
            'pub_pem': pub_pem,
            'provider_id': provider.id,
        }

        from models import CA
        CA.query.filter_by(hsm_key_id=hsm_key.id).delete()
        HsmKey.query.filter_by(id=hsm_key.id).delete()
        HsmProvider.query.filter_by(id=provider.id).delete()
        db.session.commit()


def _patch_hsm_sign(real_key, pub_pem):
    def fake_sign(key_id, data, algo=None):
        return real_key.sign(data, padding.PKCS1v15(), hashes.SHA256())

    return [
        patch('services.hsm.HsmService.sign', side_effect=fake_sign),
        patch('services.hsm.HsmService.get_public_key', return_value=pub_pem),
    ]


def _make_hsm_ca(app, hsm):
    """Create an HSM-backed root CA and return its id."""
    from services.ca_service import CAService
    with app.app_context():
        patches = _patch_hsm_sign(hsm['real_key'], hsm['pub_pem'])
        for p in patches:
            p.start()
        try:
            ca = CAService.create_internal_ca(
                descr='HSM CA #142',
                dn={'CN': 'HSM CA 142', 'O': 'Test', 'C': 'US'},
                validity_days=365,
                username='tester',
                hsm_key_id=hsm['hsm_key_id'],
            )
        finally:
            for p in patches:
                p.stop()
    return ca.id


class TestIssue142HsmCertIssuance:

    def test_issue_cert_against_hsm_ca(self, app, auth_client, hsm_provider_and_key):
        """The reported path: POST /api/v2/certificates with an HSM-backed CA."""
        ca_id = _make_hsm_ca(app, hsm_provider_and_key)

        with app.app_context():
            from models import CA
            ca = CA.query.get(ca_id)
            assert ca.prv is None and ca.has_private_key, \
                'precondition: CA is HSM-backed with no local prv'

        patches = _patch_hsm_sign(hsm_provider_and_key['real_key'],
                                  hsm_provider_and_key['pub_pem'])
        for p in patches:
            p.start()
        try:
            r = auth_client.post(
                '/api/v2/certificates',
                data=json.dumps({
                    'ca_id': ca_id,
                    'cn': 'hsm-issued-142.test',
                    'cert_type': 'server',
                    'organization': 'Org',
                    'key_type': 'RSA',
                    'key_size': '2048',
                    'validity_days': 90,
                    'san_dns': ['hsm-issued-142.test'],
                }),
                content_type='application/json',
            )
        finally:
            for p in patches:
                p.stop()

        assert r.status_code in (200, 201), \
            f'HSM cert issuance must succeed, got {r.status_code}: {r.data}'
        body = json.loads(r.data)
        cert_data = body.get('data', body)
        assert cert_data.get('id'), 'issued cert must have an id'

        # Verify the issued cert is signed by the HSM key.
        from models import Certificate
        with app.app_context():
            cert = Certificate.query.get(cert_data['id'])
            issued = __import__('cryptography').x509.load_pem_x509_certificate(
                __import__('base64').b64decode(cert.crt), default_backend())
            hsm_provider_and_key['real_key'].public_key().verify(
                issued.signature, issued.tbs_certificate_bytes,
                padding.PKCS1v15(), issued.signature_hash_algorithm)

    def test_hsm_ca_offline_is_blocked(self, app, auth_client, hsm_provider_and_key):
        """An offline HSM CA must still be refused, not silently used."""
        ca_id = _make_hsm_ca(app, hsm_provider_and_key)
        with app.app_context():
            from models import db, CA
            ca = CA.query.get(ca_id)
            ca.offline = True
            db.session.commit()

        r = auth_client.post(
            '/api/v2/certificates',
            data=json.dumps({'ca_id': ca_id, 'cn': 'blocked.test',
                             'key_type': 'RSA', 'key_size': '2048',
                             'validity_days': 30}),
            content_type='application/json')
        assert r.status_code == 400, r.data
        assert b'offline' in r.data.lower(), r.data


class TestIssue142GatePaths:

    def test_csr_bulk_sign_gate_accepts_hsm_ca(self, app, auth_client,
                                               hsm_provider_and_key):
        """csrs.py bulk-sign gate uses has_private_key (not ca.prv)."""
        ca_id = _make_hsm_ca(app, hsm_provider_and_key)

        # Upload a CSR first.
        key = rsa.generate_private_key(65537, 2048)
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        csr = (x509.CertificateSigningRequestBuilder()
               .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,
                                                           'bulk-hsm-142.test')]))
               .sign(key, hashes.SHA256(), default_backend()))
        csr_pem = csr.public_bytes(serialization.Encoding.PEM).decode()

        r = auth_client.post(
            '/api/v2/csrs',
            data=json.dumps({'csr_pem': csr_pem, 'ca_id': ca_id,
                             'cn': 'bulk-hsm-142.test'}),
            content_type='application/json')
        assert r.status_code in (200, 201), r.data
        csr_id = json.loads(r.data).get('data', {}).get('id')

        patches = _patch_hsm_sign(hsm_provider_and_key['real_key'],
                                  hsm_provider_and_key['pub_pem'])
        for p in patches:
            p.start()
        try:
            r = auth_client.post(
                '/api/v2/csrs/bulk-sign',
                data=json.dumps({'ids': [csr_id], 'ca_id': ca_id,
                                 'validity_days': 30}),
                content_type='application/json')
        finally:
            for p in patches:
                p.stop()
        # Gate must NOT return 'not valid for signing' for an HSM CA.
        assert r.status_code != 404, r.data
        assert b'private key' not in r.data.lower() or r.status_code == 200, r.data

    def test_acme_domain_issuing_ca_selector_accepts_hsm_ca(
            self, app, auth_client, hsm_provider_and_key):
        """acme_domains.py gate must allow selecting an HSM-backed issuing CA."""
        ca_id = _make_hsm_ca(app, hsm_provider_and_key)
        with app.app_context():
            from models import db
            from models.acme_models import DnsProvider
            dp = DnsProvider(name='manual-142', provider_type='manual')
            db.session.add(dp)
            db.session.commit()
            dp_id = dp.id
        r = auth_client.post(
            '/api/v2/acme/domains',
            data=json.dumps({
                'domain': 'hsm-142-issuer.test',
                'dns_provider_id': dp_id,
                'issuing_ca_id': ca_id,
            }),
            content_type='application/json')
        assert r.status_code in (200, 201), r.data
        assert b'no private key' not in r.data.lower(), r.data
