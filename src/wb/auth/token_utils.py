'''JWT payload extraction for WB API tokens.

WB API tokens are unsigned-readable JWTs. The payload claims encode the
seller account (``oid``), expiration (``exp``), and a test-token flag
(``t``). We never verify the signature — read-only claim extraction is
enough to auto-populate profile metadata at registration time.
'''

from __future__ import annotations

import base64
import json
import logging

logger = logging.getLogger(__name__)


def decode_jwt_payload(token: str) -> dict:
    '''Decode the middle (payload) segment of a JWT. No signature check.

    Args:
        token: Raw JWT string (``header.payload.signature``).

    Returns:
        Parsed payload dict, or empty dict if the token is malformed or
        undecodable. Never raises.
    '''
    if not token:
        return {}
    parts = token.split('.')
    if len(parts) != 3:
        return {}
    payload = parts[1]
    payload += '=' * (-len(payload) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, json.JSONDecodeError) as exc:
        logger.debug('JWT payload decode failed: %s', exc)
        return {}


def extract_token_claims(token: str) -> dict:
    '''Extract the WB-relevant claims from a token, normalized.

    Args:
        token: Raw JWT string.

    Returns:
        Dict with keys:
            - ``seller_id``: ``str | None`` — from JWT ``oid`` (stringified).
            - ``expires_at``: ``int | None`` — from JWT ``exp`` (unix ts).
            - ``is_test``: ``bool`` — from JWT ``t`` (defaults False).
    '''
    payload = decode_jwt_payload(token)
    oid = payload.get('oid')
    return {
        'seller_id': str(oid) if oid is not None else None,
        'expires_at': payload.get('exp'),
        'is_test': bool(payload.get('t', False)),
    }
