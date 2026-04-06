"""Shared fixtures for integration tests.

Tests are skipped automatically when WB_API_TOKEN is not set.
Load credentials from the project .env file using python-dotenv.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / '.env')


def pytest_collection_modifyitems(items):
    """Skip all integration tests when WB_API_TOKEN is absent."""
    token = os.getenv('WB_API_TOKEN')
    if not token:
        skip = pytest.mark.skip(reason='WB_API_TOKEN not set in .env')
        for item in items:
            if 'integration' in str(item.fspath):
                item.add_marker(skip)


@pytest.fixture(scope='session')
def api_token() -> str:
    """Return the WB API token from environment."""
    token = os.getenv('WB_API_TOKEN', '')
    assert token, 'WB_API_TOKEN must be set'
    return token


@pytest.fixture(scope='session')
def seller_id() -> str | None:
    """Return the optional WB seller ID from environment."""
    return os.getenv('WB_SELLER_ID')
