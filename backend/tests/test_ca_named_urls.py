"""Tests for opt-in named protocol URLs (discussion #207, migration 060).

A CA created with namedUrls=true gets an immutable unique slug; CDP/AIA
resolve by slug AND refid; embedded URLs use the slug; default stays refid.
"""
import base64
import json

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.x509.oid import ExtensionOID

from tests.conftest import get_json

CONTENT_JSON = 'application/json'


def _create_ca(auth_client, cn, **extra):
    data = {
        'type': 'root', 'commonName': cn, 'organization': 'Test Org',
        'country': 'US', 'state': 'CA', 'locality': 'Test City',
        'keyType': 'RSA', 'keySize': 2048, 'validityYears': 10,
        'hashAlgorithm': 'sha256',
    }
    data.update(extra)
    r = auth_client.post('/api/v2/cas', data=json.dumps(data),
                         content_type=CONTENT_JSON)
    assert r.status_code in (200, 201), r.data
    body = get_json(r)
    return body.get('data', body)


class TestNamedUrlSlug:

    def test_slug_generated_when_opted_in(self, auth_client):
        ca = _create_ca(auth_client, 'Named Urls Root CA', namedUrls=True)
        assert ca['url_slug'] == 'named-urls-root-ca'

    def test_no_slug_by_default(self, auth_client):
        ca = _create_ca(auth_client, 'Refid Only CA')
        assert ca['url_slug'] is None

    def test_slug_collision_suffixed(self, auth_client):
        ca1 = _create_ca(auth_client, 'Twin Named CA', namedUrls=True)
        ca2 = _create_ca(auth_client, 'Twin-Named CA', namedUrls=True)
        assert ca1['url_slug'] == 'twin-named-ca'
        assert ca2['url_slug'] == 'twin-named-ca-2'

    def test_delta_suffix_reserved(self, auth_client):
        ca = _create_ca(auth_client, 'Weird Delta', namedUrls=True)
        assert not ca['url_slug'].endswith('-delta')


class TestNamedUrlResolution:

    def test_cdp_resolves_by_slug_and_refid(self, auth_client, client):
        ca = _create_ca(auth_client, 'Slug CDP CA', namedUrls=True)
        r = auth_client.post(f"/api/v2/crl/{ca['id']}/regenerate")
        assert r.status_code == 200, r.data

        by_slug = client.get(f"/cdp/{ca['url_slug']}.crl")
        by_refid = client.get(f"/cdp/{ca['refid']}.crl")
        assert by_slug.status_code == 200
        assert by_refid.status_code == 200
        assert by_slug.data == by_refid.data

    def test_aia_resolves_by_slug(self, auth_client, client):
        ca = _create_ca(auth_client, 'Slug AIA CA', namedUrls=True)
        r = client.get(f"/ca/{ca['url_slug']}.pem")
        if r.status_code == 404:
            r = client.get(f"/aia/{ca['url_slug']}.pem")
        assert r.status_code == 200, r.status_code


class TestNamedUrlEmbedded:

    def _issued_cdp_uris(self, app, cert_id):
        with app.app_context():
            from models import Certificate, db
            row = db.session.get(Certificate, cert_id)
            cert = x509.load_pem_x509_certificate(
                base64.b64decode(row.crt), default_backend())
        try:
            ext = cert.extensions.get_extension_for_oid(
                ExtensionOID.CRL_DISTRIBUTION_POINTS)
        except x509.ExtensionNotFound:
            return []
        uris = []
        for dp in ext.value:
            for name in (dp.full_name or []):
                uris.append(name.value)
        return uris

    def test_issued_cert_embeds_slug_url(self, app, auth_client, client):
        ca = _create_ca(auth_client, 'Slug Embed CA', namedUrls=True)
        r = auth_client.post(f"/api/v2/crl/{ca['id']}/auto-regen",
                             data=json.dumps({'enabled': True}),
                             content_type=CONTENT_JSON)
        assert r.status_code == 200, r.data

        r = auth_client.post('/api/v2/certificates', data=json.dumps({
            'cn': 'slug-embed.test', 'ca_id': ca['id'], 'key_type': 'rsa',
            'key_size': 2048, 'validity_days': 90,
        }), content_type=CONTENT_JSON)
        assert r.status_code in (200, 201), r.data

        uris = self._issued_cdp_uris(app, get_json(r)['data']['id'])
        assert uris, 'expected a CDP URI in the issued certificate'
        assert any(ca['url_slug'] in u for u in uris), uris
        assert all(ca['refid'] not in u for u in uris), uris
