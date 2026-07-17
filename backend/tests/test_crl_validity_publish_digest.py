"""
CRL validity / publish / digest (discussion #207).

- Full CRL validity vs publish schedule + next_publish
- Configurable CRL signature digest
- Scheduler prefers next_publish when set
- Auth gates for the /config endpoints
"""

import json
import os
import sys
from datetime import timedelta

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from tests.conftest import assert_success
from utils.datetime_utils import utc_now

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CONTENT_JSON = "application/json"


def _post_json(client, url, data):
    return client.post(url, data=json.dumps(data), content_type=CONTENT_JSON)


class TestCrlValidityPublishDigest:
    def test_config_and_next_publish(self, app, auth_client, create_ca):
        ca = create_ca(cn="CRL Config CA")
        ca_id = ca["id"]

        r = auth_client.get(f"/api/v2/crl/{ca_id}/config")
        cfg = assert_success(r)
        assert cfg["crl_validity_days"] == 7
        assert cfg["crl_publish_interval_hours"] == 168
        assert cfg["crl_digest"] == "sha256"

        r = _post_json(
            auth_client,
            f"/api/v2/crl/{ca_id}/config",
            {
                "crl_validity_days": 14,
                "crl_publish_interval_hours": 24,
                "crl_digest": "sha384",
            },
        )
        updated = assert_success(r)
        assert updated["crl_validity_days"] == 14
        assert updated["crl_publish_interval_hours"] == 24
        assert updated["crl_digest"] == "sha384"

        with app.app_context():
            from models import CA, db

            row = db.session.get(CA, ca_id)
            row.cdp_enabled = True
            db.session.commit()

        r = auth_client.post(f"/api/v2/crl/{ca_id}/regenerate")
        meta = assert_success(r)
        assert meta.get("next_publish")
        assert meta.get("next_update")

        this_update = meta["this_update"].replace("Z", "")
        next_update = meta["next_update"].replace("Z", "")
        next_publish = meta["next_publish"].replace("Z", "")
        from datetime import datetime

        tu = datetime.fromisoformat(this_update)
        nu = datetime.fromisoformat(next_update)
        np = datetime.fromisoformat(next_publish)
        assert abs((nu - tu).days - 14) <= 1
        assert abs((np - tu).total_seconds() / 3600 - 24) < 1

        r = auth_client.get(f"/api/v2/crl/{ca_id}")
        data = assert_success(r)
        crl = x509.load_pem_x509_crl(data["crl_pem"].encode(), default_backend())
        assert isinstance(crl.signature_hash_algorithm, hashes.SHA384)

    def test_scheduler_uses_next_publish(self, app, auth_client, create_ca):
        ca = create_ca(cn="CRL Publish Due CA")
        ca_id = ca["id"]
        with app.app_context():
            from models import CA, db

            row = db.session.get(CA, ca_id)
            row.cdp_enabled = True
            row.crl_validity_days = 30
            row.crl_publish_interval_hours = 1
            db.session.commit()

        assert_success(auth_client.post(f"/api/v2/crl/{ca_id}/regenerate"))

        with app.app_context():
            from models.crl import CRLMetadata
            from services.crl_scheduler_task import CRLSchedulerTask

            latest = (
                CRLMetadata.query.filter_by(ca_id=ca_id, is_delta=False)
                .order_by(CRLMetadata.crl_number.desc())
                .first()
            )
            latest.next_publish = utc_now() - timedelta(minutes=1)
            from models import db

            db.session.commit()
            should, reason = CRLSchedulerTask.should_regenerate_crl(ca_id)
            assert should is True
            assert "publish due" in (reason or "").lower()


class TestCrlConfigAuthGates:
    def test_config_requires_auth(self, client, create_ca, auth_client):
        ca = create_ca(cn="CRL Config Auth CA")
        r = client.get(f"/api/v2/crl/{ca['id']}/config")
        assert r.status_code == 401
        r = client.post(
            f"/api/v2/crl/{ca['id']}/config",
            data=json.dumps({"crl_digest": "sha256"}),
            content_type=CONTENT_JSON,
        )
        assert r.status_code == 401
