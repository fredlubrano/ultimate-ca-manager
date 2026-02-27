"""
OCSP Service - Online Certificate Status Protocol (RFC 6960)
Handles OCSP request parsing and response generation
"""
import base64
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from cryptography import x509
from cryptography.x509 import ocsp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend

from models import db, CA, Certificate, OCSPResponse

logger = logging.getLogger(__name__)

# Map revoke_reason strings to X.509 ReasonFlags
_REASON_MAP = {
    'unspecified': x509.ReasonFlags.unspecified,
    'key_compromise': x509.ReasonFlags.key_compromise,
    'keyCompromise': x509.ReasonFlags.key_compromise,
    'ca_compromise': x509.ReasonFlags.ca_compromise,
    'caCompromise': x509.ReasonFlags.ca_compromise,
    'affiliation_changed': x509.ReasonFlags.affiliation_changed,
    'affiliationChanged': x509.ReasonFlags.affiliation_changed,
    'superseded': x509.ReasonFlags.superseded,
    'cessation_of_operation': x509.ReasonFlags.cessation_of_operation,
    'cessationOfOperation': x509.ReasonFlags.cessation_of_operation,
    'certificate_hold': x509.ReasonFlags.certificate_hold,
    'certificateHold': x509.ReasonFlags.certificate_hold,
    'privilege_withdrawn': x509.ReasonFlags.privilege_withdrawn,
    'privilegeWithdrawn': x509.ReasonFlags.privilege_withdrawn,
    'aa_compromise': x509.ReasonFlags.aa_compromise,
    'aACompromise': x509.ReasonFlags.aa_compromise,
}


class OCSPService:
    """Service for OCSP operations"""
    
    def __init__(self):
        self.backend = default_backend()
    
    def parse_request(self, request_der: bytes) -> Optional[ocsp.OCSPRequest]:
        """
        Parse OCSP request from DER-encoded bytes
        
        Args:
            request_der: DER-encoded OCSP request
            
        Returns:
            OCSPRequest object or None if parsing fails
        """
        try:
            ocsp_request = ocsp.load_der_ocsp_request(request_der)
            return ocsp_request
        except Exception as e:
            logger.error(f"Failed to parse OCSP request: {e}")
            return None
    
    def _load_ca_key(self, ca: CA):
        """Load CA private key, supporting both local and HSM storage"""
        if ca.uses_hsm:
            raise ValueError(
                f"CA {ca.descr} uses HSM - OCSP signing with HSM not yet supported"
            )
        
        if not ca.prv:
            raise ValueError(f"CA {ca.descr} has no private key")
        
        # Decrypt private key (stored encrypted in DB)
        try:
            from security.encryption import decrypt_private_key
            prv_decrypted = decrypt_private_key(ca.prv)
        except ImportError:
            prv_decrypted = ca.prv
        
        ca_key_pem = base64.b64decode(prv_decrypted).decode('utf-8')
        return serialization.load_pem_private_key(
            ca_key_pem.encode(),
            password=None,
            backend=self.backend
        )
    
    def _load_cert(self, certificate: Certificate) -> Optional[x509.Certificate]:
        """Safely load a certificate's X.509 object, returning None if unavailable"""
        if not certificate or not certificate.crt:
            return None
        try:
            crt_pem = base64.b64decode(certificate.crt).decode('utf-8')
            return x509.load_pem_x509_certificate(crt_pem.encode(), self.backend)
        except Exception:
            return None
    
    def generate_response(
        self,
        ca: CA,
        cert_serial: int,
        request_nonce: Optional[bytes] = None
    ) -> Tuple[bytes, str]:
        """
        Generate OCSP response for a certificate
        
        Args:
            ca: CA object
            cert_serial: Certificate serial number
            request_nonce: Optional nonce from request (for replay protection)
            
        Returns:
            Tuple of (DER-encoded response, status string)
        """
        try:
            # Load CA certificate
            ca_crt_pem = base64.b64decode(ca.crt).decode('utf-8')
            ca_cert = x509.load_pem_x509_certificate(ca_crt_pem.encode(), self.backend)
            
            # Load CA private key (with decryption and HSM check)
            ca_key = self._load_ca_key(ca)
            
            # Find certificate in database
            cert_serial_hex = format(cert_serial, 'x')
            certificate = Certificate.query.filter_by(serial=cert_serial_hex).first()
            
            # Determine certificate status
            if not certificate:
                status = ocsp.OCSPCertStatus.UNKNOWN
                cert_status = 'unknown'
                revocation_time = None
                revocation_reason = None
            elif certificate.revoked:
                status = ocsp.OCSPCertStatus.REVOKED
                cert_status = 'revoked'
                revocation_time = certificate.revoked_at or datetime.utcnow()
                revocation_reason = _REASON_MAP.get(
                    certificate.revoke_reason, x509.ReasonFlags.unspecified
                )
            else:
                status = ocsp.OCSPCertStatus.GOOD
                cert_status = 'good'
                revocation_time = None
                revocation_reason = None
            
            # For unknown certs, return UNAUTHORIZED
            if status == ocsp.OCSPCertStatus.UNKNOWN:
                response = ocsp.OCSPResponseBuilder.build_unsuccessful(
                    ocsp.OCSPResponseStatus.UNAUTHORIZED
                )
                return response.public_bytes(serialization.Encoding.DER), cert_status
            
            # Load the actual certificate (may be None if .crt missing)
            cert_x509 = self._load_cert(certificate)
            
            # Build OCSP response
            this_update = datetime.utcnow()
            next_update = this_update + timedelta(hours=24)
            
            builder = ocsp.OCSPResponseBuilder()
            builder = builder.add_response(
                cert=cert_x509 if cert_x509 else ca_cert,  # Fallback to CA cert if cert unavailable
                issuer=ca_cert,
                algorithm=hashes.SHA256(),
                cert_status=status,
                this_update=this_update,
                next_update=next_update,
                revocation_time=revocation_time,
                revocation_reason=revocation_reason
            ).responder_id(
                ocsp.OCSPResponderEncoding.HASH, ca_cert
            )
            
            # Add nonce if provided (replay protection)
            if request_nonce:
                builder = builder.add_extension(
                    x509.OCSPNonce(request_nonce),
                    critical=False
                )
            
            # Sign response with CA key
            response = builder.sign(ca_key, hashes.SHA256())
            response_der = response.public_bytes(serialization.Encoding.DER)
            
            # Cache response
            self._cache_response(
                ca_id=ca.id,
                cert_serial=cert_serial_hex,
                response_der=response_der,
                status=cert_status,
                this_update=this_update,
                next_update=next_update,
                revocation_time=revocation_time,
                revocation_reason=revocation_reason.value if revocation_reason else None
            )
            
            logger.info(f"Generated OCSP response for serial {cert_serial_hex}: {cert_status}")
            return response_der, cert_status
            
        except Exception as e:
            logger.error(f"Failed to generate OCSP response: {e}", exc_info=True)
            error_response = ocsp.OCSPResponseBuilder.build_unsuccessful(
                ocsp.OCSPResponseStatus.INTERNAL_ERROR
            )
            return error_response.public_bytes(serialization.Encoding.DER), 'error'
    
    def _cache_response(
        self,
        ca_id: int,
        cert_serial: str,
        response_der: bytes,
        status: str,
        this_update: datetime,
        next_update: datetime,
        revocation_time: Optional[datetime],
        revocation_reason: Optional[int]
    ):
        """Cache OCSP response in database"""
        try:
            # Check if response already exists
            existing = OCSPResponse.query.filter_by(
                ca_id=ca_id,
                cert_serial=cert_serial
            ).first()
            
            if existing:
                # Update existing
                existing.response_der = response_der
                existing.status = status
                existing.this_update = this_update
                existing.next_update = next_update
                existing.revocation_time = revocation_time
                existing.revocation_reason = revocation_reason
                existing.updated_at = datetime.utcnow()
            else:
                # Create new
                new_response = OCSPResponse(
                    ca_id=ca_id,
                    cert_serial=cert_serial,
                    response_der=response_der,
                    status=status,
                    this_update=this_update,
                    next_update=next_update,
                    revocation_time=revocation_time,
                    revocation_reason=revocation_reason
                )
                db.session.add(new_response)
            
            db.session.commit()
            logger.debug(f"Cached OCSP response for serial {cert_serial}")
            
        except Exception as e:
            logger.error(f"Failed to cache OCSP response: {e}")
            db.session.rollback()
    
    def get_cached_response(self, ca_id: int, cert_serial: str) -> Optional[bytes]:
        """
        Get cached OCSP response if still valid
        
        Args:
            ca_id: CA ID
            cert_serial: Certificate serial number (hex string)
            
        Returns:
            DER-encoded response or None if not cached or expired
        """
        try:
            cached = OCSPResponse.query.filter_by(
                ca_id=ca_id,
                cert_serial=cert_serial
            ).first()
            
            if not cached:
                return None
            
            # Check if still valid
            if cached.next_update and cached.next_update < datetime.utcnow():
                logger.debug(f"Cached OCSP response expired for serial {cert_serial}")
                return None
            
            logger.debug(f"Using cached OCSP response for serial {cert_serial}")
            return cached.response_der
            
        except Exception as e:
            logger.error(f"Failed to retrieve cached OCSP response: {e}")
            return None
    
    def cleanup_expired_responses(self):
        """Remove expired OCSP responses from cache"""
        try:
            expired_count = OCSPResponse.query.filter(
                OCSPResponse.next_update < datetime.utcnow()
            ).delete()
            
            db.session.commit()
            logger.info(f"Cleaned up {expired_count} expired OCSP responses")
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired OCSP responses: {e}")
            db.session.rollback()
