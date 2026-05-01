"""
SCEP Message Parser - PKCS#7 message parsing and envelope decryption.
"""
import logging
from typing import Dict, Any

import asn1crypto.cms
from Crypto.Cipher import DES3, AES
from cryptography.hazmat.primitives.asymmetric import padding
from pyasn1.codec.der import decoder as pyasn1_decoder
from pyasn1_modules import rfc5652

logger = logging.getLogger(__name__)


def extract_scep_attributes(signed_data) -> Dict[str, Any]:
    """Extract SCEP attributes from the SignerInfo signed attributes."""
    attrs: Dict[str, Any] = {}
    try:
        signer_infos = signed_data['signer_infos']
        if len(signer_infos) > 0:
            signer_info = signer_infos[0]
            signed_attrs = signer_info['signed_attrs']
            for attr in signed_attrs:
                attr_type = attr['type'].native
                attr_values = attr['values']
                if len(attr_values) > 0:
                    value = attr_values[0]
                    if attr_type == '2.16.840.1.113733.1.9.7':  # transactionID
                        attrs['transactionID'] = (
                            value.native.decode('utf-8')
                            if isinstance(value.native, bytes)
                            else value.native
                        )
                    elif attr_type == '2.16.840.1.113733.1.9.2':  # messageType
                        attrs['messageType'] = (
                            int.from_bytes(value.native, 'big')
                            if isinstance(value.native, bytes)
                            else value.native
                        )
                    elif attr_type == '2.16.840.1.113733.1.9.5':  # senderNonce
                        attrs['senderNonce'] = value.native
                    elif attr_type == '1.2.840.113549.1.9.7':  # challengePassword
                        attrs['challengePassword'] = value.native
    except Exception as e:
        logger.error(f"SCEP: Error extracting attributes: {e}")
    return attrs


def decrypt_scep_envelope(encrypted_bytes: bytes, ca_key) -> bytes:
    """
    Decrypt a SCEP EnvelopedData structure using the CA private key.

    Args:
        encrypted_bytes: DER-encoded ContentInfo containing EnvelopedData
        ca_key: CA RSA private key for CEK decryption

    Returns:
        Decrypted plaintext (the CSR DER bytes)

    Raises:
        ValueError: on unsupported algorithm or bad padding
    """
    envdata = asn1crypto.cms.ContentInfo.load(encrypted_bytes)

    if envdata['content_type'].native != 'enveloped_data':
        # Not enveloped — return as-is (shouldn't happen in modern SCEP)
        return encrypted_bytes

    # Parse with pyasn1 to handle BER-encoded constructed OctetString
    content_info_inner, _ = pyasn1_decoder.decode(
        encrypted_bytes, asn1Spec=rfc5652.ContentInfo()
    )
    env_data, _ = pyasn1_decoder.decode(
        bytes(content_info_inner['content']), asn1Spec=rfc5652.EnvelopedData()
    )

    recipient_info = env_data['recipientInfos'][0]
    recipient_ktri = recipient_info.getComponent()
    encrypted_key_bytes = bytes(recipient_ktri['encryptedKey'])

    content_encryption_key = ca_key.decrypt(encrypted_key_bytes, padding.PKCS1v15())

    enc_info = env_data['encryptedContentInfo']
    encrypted_content_bytes = bytes(enc_info['encryptedContent'])
    alg_oid = str(enc_info['contentEncryptionAlgorithm']['algorithm'])
    alg_params = enc_info['contentEncryptionAlgorithm']['parameters']

    if alg_params and alg_params.hasValue():
        from pyasn1.type import univ
        iv_octets, _ = pyasn1_decoder.decode(bytes(alg_params), asn1Spec=univ.OctetString())
        iv = bytes(iv_octets)
    else:
        iv = b'\x00' * 8

    if '1.3.14.3.2.7' in alg_oid:  # DES
        logger.warning("SCEP client using DES encryption — rejected (insecure)")
        raise ValueError("DES encryption is not supported — use AES or 3DES")
    elif '1.2.840.113549.3.7' in alg_oid:  # 3DES
        logger.warning("SCEP client using 3DES encryption — deprecated, prefer AES")
        cipher = DES3.new(content_encryption_key, DES3.MODE_CBC, iv)
        plaintext = cipher.decrypt(encrypted_content_bytes)
        pad_len = plaintext[-1]
        if pad_len < 1 or pad_len > DES3.block_size or not all(
            b == pad_len for b in plaintext[-pad_len:]
        ):
            raise ValueError("Invalid PKCS#7 padding in SCEP message")
        return plaintext[:-pad_len]
    elif '2.16.840.1.101.3.4.1' in alg_oid:  # AES (any variant)
        cipher = AES.new(content_encryption_key, AES.MODE_CBC, iv)
        plaintext = cipher.decrypt(encrypted_content_bytes)
        pad_len = plaintext[-1]
        if pad_len < 1 or pad_len > AES.block_size or not all(
            b == pad_len for b in plaintext[-pad_len:]
        ):
            raise ValueError("Invalid PKCS#7 padding in SCEP message")
        return plaintext[:-pad_len]
    else:
        raise ValueError(f"Unsupported encryption algorithm: {alg_oid}")
