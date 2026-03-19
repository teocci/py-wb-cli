"""Token validation against Wildberries API."""

from __future__ import annotations

import logging

import httpx

from wb.core.constants import PING_PATH, PROMOTION_BASE_URL
from wb.core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

# Official connection check endpoint per WB API docs
_PING_PATH = PING_PATH


def validate_promotion_token(token: str, timeout: float = 10.0) -> bool:
    """Validate a promotion token by hitting a lightweight endpoint.

    Args:
        token: The WB API token to validate.
        timeout: Request timeout in seconds.

    Returns:
        True if the token is valid.

    Raises:
        AuthenticationError: If the token is rejected.
    """
    try:
        response = httpx.get(
            f'{PROMOTION_BASE_URL}{_PING_PATH}',
            headers={'Authorization': token},
            timeout=timeout,
        )
        if response.status_code == 401:
            raise AuthenticationError('Token rejected by WB API (HTTP 401)')
        if response.status_code == 200:
            logger.info('Promotion token validated successfully')
            return True
        logger.warning(
            'Unexpected status %d during token validation',
            response.status_code,
        )
        return True
    except httpx.HTTPError as exc:
        raise AuthenticationError(
            f'Failed to validate token: {exc}'
        ) from exc
