"""
Discovery Service
Scans network targets for TLS certificates and matches against UCM inventory.
"""
import socket
import ssl
import hashlib
import ipaddress
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization

from models import db, Certificate, DiscoveredCertificate

logger = logging.getLogger(__name__)


class DiscoveryService:
    """Service for discovering certificates on the network."""

    def __init__(self, max_workers: int = 20, timeout: int = 5):
        self.max_workers = max_workers
        self.timeout = timeout

    # ------------------------------------------------------------------
    # TLS scanning
    # ------------------------------------------------------------------

    def probe_tls(self, host: str, port: int = 443) -> Dict:
        """Connect to host:port via TLS and return certificate info dict (or error dict)."""
        result = {'target': host, 'port': port}
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            with socket.create_connection((host, port), timeout=self.timeout) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as tls:
                    der = tls.getpeercert(binary_form=True)
                    if not der:
                        result['error'] = 'No certificate returned'
                        return result

                    cert = x509.load_der_x509_certificate(der)
                    pem = cert.public_bytes(serialization.Encoding.PEM).decode()
                    fp = hashlib.sha256(der).hexdigest().upper()

                    result.update({
                        'subject': cert.subject.rfc4514_string(),
                        'issuer': cert.issuer.rfc4514_string(),
                        'serial_number': format(cert.serial_number, 'X'),
                        'not_before': cert.not_valid_before_utc.isoformat(),
                        'not_after': cert.not_valid_after_utc.isoformat(),
                        'fingerprint_sha256': fp,
                        'pem_certificate': pem,
                    })
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            result['error'] = str(e)
        except Exception as e:
            logger.debug(f"TLS probe {host}:{port} failed: {e}")
            result['error'] = str(e)
        return result

    def scan_targets(self, targets: List[str], ports: List[int] = None) -> List[Dict]:
        """Scan list of host strings (optionally with :port) on given ports."""
        if ports is None:
            ports = [443]
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {}
            for raw in targets:
                host, custom_port = self._parse_target(raw)
                scan_ports = [custom_port] if custom_port else ports
                for p in scan_ports:
                    f = pool.submit(self.probe_tls, host, p)
                    futures[f] = (host, p)
            for future in as_completed(futures):
                results.append(future.result())
        return results

    def scan_subnet(self, cidr: str, ports: List[int] = None) -> List[Dict]:
        """Scan every host in a CIDR subnet."""
        network = ipaddress.ip_network(cidr, strict=False)
        targets = [str(ip) for ip in network.hosts()]
        return self.scan_targets(targets, ports)

    # ------------------------------------------------------------------
    # Persistence — save/update discovered certificates
    # ------------------------------------------------------------------

    def save_results(self, results: List[Dict]) -> Dict:
        """Persist scan results into discovered_certificates table. Returns summary."""
        saved = 0
        updated = 0
        errors = 0
        now = datetime.now(timezone.utc)

        for r in results:
            if 'error' in r and 'pem_certificate' not in r:
                # Failed probe — record the error for target tracking
                existing = DiscoveredCertificate.query.filter_by(
                    target=r['target'], port=r['port']
                ).first()
                if existing:
                    existing.last_seen = now
                    existing.scan_error = r['error']
                    updated += 1
                else:
                    dc = DiscoveredCertificate(
                        target=r['target'], port=r['port'],
                        pem_certificate='', status='error',
                        scan_error=r['error'],
                        first_seen=now, last_seen=now,
                    )
                    db.session.add(dc)
                    errors += 1
                continue

            fp = r['fingerprint_sha256']

            # Match against UCM inventory
            ucm_cert = Certificate.query.filter(
                Certificate.serial_number == r.get('serial_number')
            ).first()
            # Fallback: try matching by computing thumbprint on known certs
            # For now serial_number match is sufficient
            status = 'known' if ucm_cert else 'unknown'
            ucm_id = ucm_cert.id if ucm_cert else None

            existing = DiscoveredCertificate.query.filter_by(
                target=r['target'], port=r['port']
            ).first()

            if existing:
                existing.subject = r.get('subject')
                existing.issuer = r.get('issuer')
                existing.serial_number = r.get('serial_number')
                existing.not_before = _parse_iso(r.get('not_before'))
                existing.not_after = _parse_iso(r.get('not_after'))
                existing.fingerprint_sha256 = fp
                existing.pem_certificate = r['pem_certificate']
                existing.status = status
                existing.ucm_certificate_id = ucm_id
                existing.last_seen = now
                existing.scan_error = None
                updated += 1
            else:
                dc = DiscoveredCertificate(
                    target=r['target'], port=r['port'],
                    subject=r.get('subject'),
                    issuer=r.get('issuer'),
                    serial_number=r.get('serial_number'),
                    not_before=_parse_iso(r.get('not_before')),
                    not_after=_parse_iso(r.get('not_after')),
                    fingerprint_sha256=fp,
                    pem_certificate=r['pem_certificate'],
                    status=status,
                    ucm_certificate_id=ucm_id,
                    first_seen=now, last_seen=now,
                )
                db.session.add(dc)
                saved += 1

        db.session.commit()
        return {'saved': saved, 'updated': updated, 'errors': errors}

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_all(self, limit: int = 500) -> List[Dict]:
        """Return all discovered certificates, newest first."""
        rows = DiscoveredCertificate.query.filter(
            DiscoveredCertificate.status != 'error'
        ).order_by(
            DiscoveredCertificate.last_seen.desc()
        ).limit(limit).all()
        return [r.to_dict() for r in rows]

    def get_unknown(self) -> List[Dict]:
        rows = DiscoveredCertificate.query.filter_by(status='unknown').order_by(
            DiscoveredCertificate.last_seen.desc()
        ).all()
        return [r.to_dict() for r in rows]

    def get_expired(self) -> List[Dict]:
        now = datetime.now(timezone.utc)
        rows = DiscoveredCertificate.query.filter(
            DiscoveredCertificate.not_after < now,
            DiscoveredCertificate.status != 'error',
        ).order_by(
            DiscoveredCertificate.not_after.asc()
        ).all()
        return [r.to_dict() for r in rows]

    def get_expiring_soon(self, days: int = 30) -> List[Dict]:
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days)
        rows = DiscoveredCertificate.query.filter(
            DiscoveredCertificate.not_after > now,
            DiscoveredCertificate.not_after <= cutoff,
            DiscoveredCertificate.status != 'error',
        ).order_by(
            DiscoveredCertificate.not_after.asc()
        ).all()
        return [r.to_dict() for r in rows]

    def get_stats(self) -> Dict:
        """Return summary statistics."""
        total = DiscoveredCertificate.query.filter(
            DiscoveredCertificate.status != 'error'
        ).count()
        known = DiscoveredCertificate.query.filter_by(status='known').count()
        unknown = DiscoveredCertificate.query.filter_by(status='unknown').count()
        now = datetime.now(timezone.utc)
        expired = DiscoveredCertificate.query.filter(
            DiscoveredCertificate.not_after < now,
            DiscoveredCertificate.status != 'error',
        ).count()
        errors = DiscoveredCertificate.query.filter_by(status='error').count()
        return {
            'total': total,
            'known': known,
            'unknown': unknown,
            'expired': expired,
            'errors': errors,
        }

    def delete(self, disc_id: int) -> bool:
        row = DiscoveredCertificate.query.get(disc_id)
        if not row:
            return False
        db.session.delete(row)
        db.session.commit()
        return True

    def delete_all(self) -> int:
        count = DiscoveredCertificate.query.delete()
        db.session.commit()
        return count

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_target(raw: str) -> Tuple[str, Optional[int]]:
        """Parse 'host' or 'host:port' string."""
        raw = raw.strip()
        if not raw:
            return ('', None)
        if raw.startswith('['):
            # IPv6 [::1]:port
            if ']:' in raw:
                host, port_s = raw.rsplit(':', 1)
                return (host.strip('[]'), int(port_s))
            return (raw.strip('[]'), None)
        if ':' in raw:
            parts = raw.rsplit(':', 1)
            try:
                return (parts[0], int(parts[1]))
            except ValueError:
                return (raw, None)
        return (raw, None)


def _parse_iso(val) -> Optional[datetime]:
    """Parse ISO datetime string to datetime object."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(val.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None
