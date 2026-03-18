"""Token validation against Wildberries API."""

from __future__ import annotations

import logging

import httpx

from wb.core.constants import PROMOTION_BASE_URL
from wb.core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

# A lightweight endpoint to test if the promotion token works
_PING_PATH = '/adv/v1/promotion/count'


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
