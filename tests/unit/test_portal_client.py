"""Tests for wb.client.portal — PortalClient and PortalSession."""

import httpx
import pytest
import respx

from wb.client.portal import PortalClient, PortalSession
from wb.core.constants import (
    EP_PORTAL_AUTH_TOKEN,
    EP_PORTAL_TABLE_LIST,
    EP_PORTAL_TOKENS_JRPC,
    PORTAL_AUTH_HEADER,
    SELLER_CONTENT_BASE_URL,
    SELLER_PORTAL_BASE_URL,
)
from wb.core.exceptions import ApiError, AuthenticationError, ValidationError

AUTH_URL = f'{SELLER_PORTAL_BASE_URL}{EP_PORTAL_AUTH_TOKEN}'
TOKENS_URL = f'{SELLER_CONTENT_BASE_URL}{EP_PORTAL_TOKENS_JRPC}'
PRODUCTS_URL = f'{SELLER_CONTENT_BASE_URL}{EP_PORTAL_TABLE_LIST}'


# ── PortalSession dataclass ──────────────────────────────────────────


class TestPortalSession:
    """Tests for the PortalSession dataclass."""

    def test_create(self):
        """PortalSession stores token, user_id, and exp."""
        session = PortalSession(token='jwt-abc', user_id=12345, exp=1773884106)

        assert session.token == 'jwt-abc'
        assert session.user_id == 12345
        assert session.exp == 1773884106


# ── PortalClient construction ────────────────────────────────────────


class TestPortalClientInit:
    """Tests for PortalClient constructor validation."""

    def test_requires_cookie(self):
        """PortalClient raises ValidationError if cookie is empty."""
        with pytest.raises(ValidationError, match='cookie is required'):
            PortalClient(authorizev3='key', cookie='')

    def test_requires_cookie_not_none(self):
        """PortalClient raises ValidationError if cookie is None."""
        with pytest.raises(ValidationError):
            PortalClient(authorizev3='key', cookie=None)

    def test_valid_construction(self):
        """PortalClient can be created with both authorizev3 and cookie."""
        client = PortalClient(authorizev3='key', cookie='session=abc')
        assert client is not None


# ── PortalClient.authenticate ────────────────────────────────────────


class TestPortalClientAuthenticate:
    """Tests for PortalClient.authenticate()."""

    def test_authenticate_success(self):
        """Successful portal authentication returns a PortalSession."""
        with respx.mock:
            respx.post(AUTH_URL).mock(return_value=httpx.Response(200, json={
                'id': 'json-rpc_1',
                'jsonrpc': '2.0',
                'result': {
                    'data': {
                        'token': 'session-jwt-token',
                        'userID': 155579335,
                        'exp': 1773884106,
                    },
                },
            }))

            client = PortalClient(authorizev3='auth-v3-key', cookie='c=1')
            session = client.authenticate()

        assert isinstance(session, PortalSession)
        assert session.token == 'session-jwt-token'
        assert session.user_id == 155579335
        assert session.exp == 1773884106

    def test_sends_cookie_and_authorizev3(self):
        """Authentication sends both cookie and authorizev3 headers."""
        with respx.mock:
            route = respx.post(AUTH_URL).mock(return_value=httpx.Response(200, json={
                'id': 'json-rpc_1',
                'jsonrpc': '2.0',
                'result': {'data': {'token': 't', 'userID': 1, 'exp': 0}},
            }))

            client = PortalClient(authorizev3='my-key', cookie='my-cookie')
            client.authenticate()

            request = route.calls[0].request
            assert request.headers[PORTAL_AUTH_HEADER] == 'my-key'
            assert request.headers['cookie'] == 'my-cookie'

    def test_sends_jrpc_payload(self):
        """Authentication sends correct JSON-RPC payload."""
        with respx.mock:
            route = respx.post(AUTH_URL).mock(return_value=httpx.Response(200, json={
                'id': 'json-rpc_1',
                'jsonrpc': '2.0',
                'result': {'data': {'token': 't', 'userID': 1, 'exp': 0}},
            }))

            client = PortalClient(authorizev3='key', cookie='c=1')
            client.authenticate()

            import json
            body = json.loads(route.calls[0].request.content)
            assert body['jsonrpc'] == '2.0'
            assert body['params'] == {}

    def test_401_raises_auth_error(self):
        """Portal returning 401 raises AuthenticationError."""
        with respx.mock:
            respx.post(AUTH_URL).mock(return_value=httpx.Response(401))

            client = PortalClient(authorizev3='bad', cookie='c=1')
            with pytest.raises(AuthenticationError, match='401'):
                client.authenticate()

    def test_500_raises_api_error(self):
        """Portal returning 500 raises ApiError."""
        with respx.mock:
            respx.post(AUTH_URL).mock(return_value=httpx.Response(500, text='err'))

            client = PortalClient(authorizev3='key', cookie='c=1')
            with pytest.raises(ApiError, match='500'):
                client.authenticate()

    def test_unexpected_format_raises_api_error(self):
        """Portal returning unexpected JSON raises ApiError."""
        with respx.mock:
            respx.post(AUTH_URL).mock(return_value=httpx.Response(200, json={
                'id': 'json-rpc_1',
                'jsonrpc': '2.0',
                'result': {'unexpected': True},
            }))

            client = PortalClient(authorizev3='key', cookie='c=1')
            with pytest.raises(ApiError, match='Unexpected'):
                client.authenticate()


# ── PortalClient.generate_token ──────────────────────────────────────


class TestPortalClientGenerateToken:
    """Tests for PortalClient.generate_token()."""

    def test_success(self):
        """Successful token generation returns the token string."""
        with respx.mock:
            respx.post(TOKENS_URL).mock(return_value=httpx.Response(200, json={
                'id': 'json-rpc_1',
                'jsonrpc': '2.0',
                'result': {'token': 'generated-render-token'},
            }))

            client = PortalClient(authorizev3='key', cookie='c=1')
            token = client.generate_token()

        assert token == 'generated-render-token'

    def test_sends_generateToken_method(self):
        """Token generation sends generateToken method in JRPC payload."""
        with respx.mock:
            route = respx.post(TOKENS_URL).mock(return_value=httpx.Response(200, json={
                'id': 'json-rpc_1',
                'jsonrpc': '2.0',
                'result': {'token': 'tok'},
            }))

            client = PortalClient(authorizev3='key', cookie='c=1')
            client.generate_token()

            import json
            body = json.loads(route.calls[0].request.content)
            assert body['method'] == 'generateToken'
            assert body['params'] == {'team': 'render'}

    def test_401_raises_auth_error(self):
        """Expired creds raise AuthenticationError."""
        with respx.mock:
            respx.post(TOKENS_URL).mock(return_value=httpx.Response(401))

            client = PortalClient(authorizev3='key', cookie='c=1')
            with pytest.raises(AuthenticationError):
                client.generate_token()


# ── PortalClient.list_products ───────────────────────────────────────


class TestPortalClientListProducts:
    """Tests for PortalClient.list_products()."""

    def test_returns_card_list(self):
        """list_products returns a list of card dicts."""
        with respx.mock:
            respx.post(PRODUCTS_URL).mock(return_value=httpx.Response(200, json={
                'data': {
                    'cards': [
                        {'nmID': 123, 'title': 'Product A'},
                        {'nmID': 456, 'title': 'Product B'},
                    ],
                },
            }))

            client = PortalClient(authorizev3='key', cookie='c=1')
            cards = client.list_products(page_size=2)

        assert len(cards) == 2
        assert cards[0]['nmID'] == 123
        assert cards[1]['title'] == 'Product B'

    def test_sends_correct_payload(self):
        """list_products sends sort, filter, and cursor in payload."""
        with respx.mock:
            route = respx.post(PRODUCTS_URL).mock(return_value=httpx.Response(200, json={
                'data': {'cards': []},
            }))

            client = PortalClient(authorizev3='key', cookie='c=1')
            client.list_products(page_size=5, search='perfume')

            import json
            body = json.loads(route.calls[0].request.content)
            assert body['cursor']['n'] == 5
            assert body['filter']['search'] == 'perfume'

    def test_empty_response(self):
        """list_products returns empty list when no cards."""
        with respx.mock:
            respx.post(PRODUCTS_URL).mock(return_value=httpx.Response(200, json={
                'data': {'cards': []},
            }))

            client = PortalClient(authorizev3='key', cookie='c=1')
            assert client.list_products() == []

    def test_401_raises_auth_error(self):
        """Expired creds raise AuthenticationError."""
        with respx.mock:
            respx.post(PRODUCTS_URL).mock(return_value=httpx.Response(401))

            client = PortalClient(authorizev3='key', cookie='c=1')
            with pytest.raises(AuthenticationError):
                client.list_products()


# ── JRPC counter ─────────────────────────────────────────────────────


class TestPortalClientJrpcCounter:
    """Tests for JSON-RPC ID incrementing."""

    def test_jrpc_ids_increment(self):
        """Each JRPC request gets an incrementing ID."""
        with respx.mock:
            route = respx.post(AUTH_URL).mock(return_value=httpx.Response(200, json={
                'id': 'json-rpc_1',
                'jsonrpc': '2.0',
                'result': {'data': {'token': 't', 'userID': 1, 'exp': 0}},
            }))

            client = PortalClient(authorizev3='key', cookie='c=1')
            client.authenticate()
            client.authenticate()

            import json
            body1 = json.loads(route.calls[0].request.content)
            body2 = json.loads(route.calls[1].request.content)
            assert body1['id'] == 'json-rpc_1'
            assert body2['id'] == 'json-rpc_2'
