"""
Discovered Certificate Model
Stores certificates found through network scanning.
"""
from datetime import datetime, timezone
from models import db


class DiscoveredCertificate(db.Model):
    """Certificate discovered via TLS network scan."""

    __tablename__ = 'discovered_certificates'

    id = db.Column(db.Integer, primary_key=True)
    target = db.Column(db.String(1024), nullable=False)
    port = db.Column(db.Integer, nullable=False, default=443)
    subject = db.Column(db.Text)
    issuer = db.Column(db.Text)
    serial_number = db.Column(db.String(100))
    not_before = db.Column(db.DateTime)
    not_after = db.Column(db.DateTime)
    fingerprint_sha256 = db.Column(db.String(64), index=True)
    pem_certificate = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(32), nullable=False, default='unknown')  # unknown, known, error
    ucm_certificate_id = db.Column(db.Integer, db.ForeignKey('certificates.id', ondelete='SET NULL'))
    first_seen = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    scan_error = db.Column(db.Text)

    # Relationship
    ucm_certificate = db.relationship('Certificate', backref='discovered_instances')

    __table_args__ = (
        db.UniqueConstraint('target', 'port', name='uq_disc_cert_target_port'),
    )

    def __repr__(self):
        return f'<DiscoveredCertificate {self.target}:{self.port}>'

    @property
    def is_expired(self):
        if not self.not_after:
            return False
        return datetime.now(timezone.utc) > self.not_after.replace(tzinfo=timezone.utc)

    @property
    def days_until_expiry(self):
        if not self.not_after:
            return None
        delta = self.not_after.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
        return delta.days

    def to_dict(self):
        return {
            'id': self.id,
            'target': self.target,
            'port': self.port,
            'subject': self.subject,
            'issuer': self.issuer,
            'serial_number': self.serial_number,
            'not_before': self.not_before.isoformat() if self.not_before else None,
            'not_after': self.not_after.isoformat() if self.not_after else None,
            'fingerprint_sha256': self.fingerprint_sha256,
            'status': self.status,
            'ucm_certificate_id': self.ucm_certificate_id,
            'first_seen': self.first_seen.isoformat() if self.first_seen else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'is_expired': self.is_expired,
            'days_until_expiry': self.days_until_expiry,
            'scan_error': self.scan_error,
        }
