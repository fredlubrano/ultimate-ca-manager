"""Regression: certificate notBefore backdated for clock skew (#207)."""
from datetime import timedelta

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from utils.datetime_utils import (
    DEFAULT_CERT_NOT_BEFORE_SKEW_MINUTES,
    cert_not_before,
    utc_now,
)

BASE = '/api/v2/certificates'


class TestCertNotBeforeSkew:
    def test_default_skew_is_fifteen_minutes(self):
        now = utc_now()
        nb = cert_not_before()
        delta = now - nb
        assert timedelta(minutes=14, seconds=50) <= delta <= timedelta(minutes=15, seconds=10)
        assert DEFAULT_CERT_NOT_BEFORE_SKEW_MINUTES == 15

    def test_custom_skew_clamped_to_non_negative(self):
        now = utc_now()
        assert cert_not_before(0) == now or abs((now - cert_not_before(0)).total_seconds()) < 2
        assert utc_now() - cert_not_before(5) >= timedelta(minutes=4, seconds=50)

    def test_issued_certificate_not_before_backdated(self, auth_client, create_cert):
        cert = create_cert(cn='notbefore-skew.example.com')
        cert_id = cert.get('id', cert.get('cert_id'))
        r = auth_client.get(f'{BASE}/{cert_id}/export?format=pem')
        assert r.status_code == 200
        pem = r.data.decode('utf-8')
        x509_cert = x509.load_pem_x509_certificate(pem.encode(), default_backend())
        nb = x509_cert.not_valid_before_utc.replace(tzinfo=None)
        now = utc_now()
        assert nb < now
        assert now - nb >= timedelta(minutes=14)
        assert now - nb <= timedelta(minutes=16)
