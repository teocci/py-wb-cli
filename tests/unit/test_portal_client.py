"""Tests for wb.client.portal — PortalClient and PortalSession."""

import httpx
import pytest
import respx

from wb.client.portal import PortalClient, PortalSession
from wb.core.constants import (
    EP_PORTAL_AUTH_TOKEN,
    EP_PORTAL_BIDS,
    EP_PORTAL_BIDS_CPC,
    EP_PORTAL_TABLE_LIST,
    EP_PORTAL_TOKENS_JRPC,
    PORTAL_AUTH_HEADER,
    SELLER_CONTENT_BASE_URL,
    SELLER_PORTAL_BASE_URL,
    WB_CMP_BASE_URL,
)
from wb.core.exceptions import ApiError, AuthenticationError, ValidationError
from wb.domain.enums import PaymentType
from wb.domain.models import (
    PortalBidRecommendation,
    ReachTier,
    parse_portal_bids_response,
)

AUTH_URL = f'{SELLER_PORTAL_BASE_URL}{EP_PORTAL_AUTH_TOKEN}'
TOKENS_URL = f'{SELLER_CONTENT_BASE_URL}{EP_PORTAL_TOKENS_JRPC}'
PRODUCTS_URL = f'{SELLER_CONTENT_BASE_URL}{EP_PORTAL_TABLE_LIST}'
BIDS_CPC_URL = f'{WB_CMP_BASE_URL}{EP_PORTAL_BIDS_CPC}'
BIDS_URL = f'{WB_CMP_BASE_URL}{EP_PORTAL_BIDS}'


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


# ── PortalClient.fetch_bid_recommendations (F-21) ────────────────────


CPC_UNIFIED_FIXTURE = {
    'recommendations': [{
        'id': 183813043,
        'min': 100,
        'reach_max':    {'bid': 0,    'min': 0, 'budget': 0,      'shows': 0, 'clicks': 0},
        'reach_medium': {'bid': 0,    'min': 0, 'budget': 0,      'shows': 0, 'clicks': 0},
        'reach_min':    {'bid': 0,    'min': 0, 'budget': 0,      'shows': 0, 'clicks': 0},
    }],
    'search': [{
        'id': 183813043,
        'min': 181,
        'reach_max':    {'bid': 0,    'min': 0, 'budget': 0,      'shows': 0, 'clicks': 0},
        'reach_medium': {'bid': 0,    'min': 0, 'budget': 0,      'shows': 0, 'clicks': 0},
        'reach_min':    {'bid': 1500, 'min': 0, 'budget': 315000, 'shows': 0, 'clicks': 30},
    }],
}


CPM_MANUAL_FIXTURE = {
    'combined': [{
        'id': 183813043,
        'min': 12000,
        'reach_max':    {'bid': 0,     'min': 39000, 'budget': 0,      'shows': 0,    'clicks': 0},
        'reach_medium': {'bid': 21600, 'min': 0,     'budget': 106600, 'shows': 4944, 'clicks': 115},
        'reach_min':    {'bid': 20300, 'min': 0,     'budget': 59000,  'shows': 2915, 'clicks': 51},
    }],
}


class TestPortalClientFetchBidRecommendations:
    """Tests for PortalClient.fetch_bid_recommendations() (F-21)."""

    def test_cpc_hits_bids_cpc_path(self):
        """CPC payment type targets the /bids-cpc endpoint and omits payment_type from query."""
        with respx.mock:
            route = respx.get(BIDS_CPC_URL).mock(
                return_value=httpx.Response(200, json=CPC_UNIFIED_FIXTURE),
            )

            client = PortalClient(authorizev3='key', cookie='c=1')
            raw = client.fetch_bid_recommendations(
                [183813043], PaymentType.CPC, bid_type=2,
            )

        assert raw == CPC_UNIFIED_FIXTURE
        request = route.calls[0].request
        assert request.url.path == EP_PORTAL_BIDS_CPC
        assert request.url.params['nms'] == '183813043'
        assert request.url.params['bid_type'] == '2'
        assert 'payment_type' not in request.url.params

    def test_cpm_hits_bids_path_and_includes_payment_type_param(self):
        """CPM payment type targets the /bids endpoint and adds payment_type=cpm."""
        with respx.mock:
            route = respx.get(BIDS_URL).mock(
                return_value=httpx.Response(200, json=CPM_MANUAL_FIXTURE),
            )

            client = PortalClient(authorizev3='key', cookie='c=1')
            raw = client.fetch_bid_recommendations(
                [183813043], PaymentType.CPM, bid_type=1,
            )

        assert raw == CPM_MANUAL_FIXTURE
        request = route.calls[0].request
        assert request.url.path == EP_PORTAL_BIDS
        assert request.url.params['payment_type'] == 'cpm'
        assert request.url.params['bid_type'] == '1'

    def test_accepts_string_payment_type(self):
        """payment_type='cpc' works without needing the enum."""
        with respx.mock:
            respx.get(BIDS_CPC_URL).mock(
                return_value=httpx.Response(200, json=CPC_UNIFIED_FIXTURE),
            )

            client = PortalClient(authorizev3='key', cookie='c=1')
            raw = client.fetch_bid_recommendations(
                [1, 2, 3], 'cpc', bid_type=2,
            )

        assert raw == CPC_UNIFIED_FIXTURE

    def test_multi_nm_passes_comma_separated_nms(self):
        """nm_ids list serializes to a comma-separated `nms` query param."""
        with respx.mock:
            route = respx.get(BIDS_CPC_URL).mock(
                return_value=httpx.Response(200, json={'combined': []}),
            )

            client = PortalClient(authorizev3='key', cookie='c=1')
            client.fetch_bid_recommendations([10, 20, 30], PaymentType.CPC, 1)

            assert route.calls[0].request.url.params['nms'] == '10,20,30'

    def test_empty_nm_ids_raises_validation(self):
        """An empty nm_ids list short-circuits to ValidationError."""
        client = PortalClient(authorizev3='key', cookie='c=1')
        with pytest.raises(ValidationError, match='nm_ids is empty'):
            client.fetch_bid_recommendations([], PaymentType.CPC, 2)

    def test_401_raises_auth_error(self):
        """Portal returning 401 raises AuthenticationError."""
        with respx.mock:
            respx.get(BIDS_CPC_URL).mock(return_value=httpx.Response(401))

            client = PortalClient(authorizev3='expired', cookie='c=1')
            with pytest.raises(AuthenticationError, match='401'):
                client.fetch_bid_recommendations([1], PaymentType.CPC, 2)

    def test_sends_authorizev3_and_cookie_headers(self):
        """fetch_bid_recommendations includes authorizev3 + cookie just like POST endpoints."""
        with respx.mock:
            route = respx.get(BIDS_CPC_URL).mock(
                return_value=httpx.Response(200, json={'combined': []}),
            )

            client = PortalClient(authorizev3='my-jwt', cookie='wbauid=123')
            client.fetch_bid_recommendations([1], PaymentType.CPC, 2)

            request = route.calls[0].request
            assert request.headers[PORTAL_AUTH_HEADER] == 'my-jwt'
            assert request.headers['cookie'] == 'wbauid=123'
            # cmp.wildberries.ru endpoints should use a same-origin referer.
            assert request.headers['origin'] == WB_CMP_BASE_URL


# ── parse_portal_bids_response (F-21) ────────────────────────────────


class TestParsePortalBidsResponse:
    """Tests for the shape-flexible parser in wb.domain.models."""

    def test_unified_cpc_yields_two_records(self):
        """Unified CPC envelope produces one record per (NM, placement)."""
        records = parse_portal_bids_response(CPC_UNIFIED_FIXTURE, payment_type='cpc')

        placements = sorted(r.placement for r in records)
        assert placements == ['recommendations', 'search']
        assert all(r.nm_id == 183813043 for r in records)
        assert all(r.payment_type == 'cpc' for r in records)

        search = next(r for r in records if r.placement == 'search')
        assert search.min_bid == 181
        assert search.reach_min.bid == 1500
        assert search.reach_min.clicks == 30

    def test_manual_cpm_yields_single_combined_record(self):
        """Manual-bid CPM envelope (`combined` key) produces one record per NM."""
        records = parse_portal_bids_response(CPM_MANUAL_FIXTURE, payment_type='cpm')

        assert len(records) == 1
        record = records[0]
        assert record.placement == 'combined'
        assert record.payment_type == 'cpm'
        assert record.min_bid == 12000
        assert record.reach_medium.bid == 21600
        assert record.reach_medium.clicks == 115

    def test_unknown_placement_key_passes_through(self):
        """Future placement names (e.g. `cart`) are not filtered out."""
        raw = {'cart': [{'id': 1, 'min': 50}]}

        records = parse_portal_bids_response(raw, payment_type='cpc')

        assert len(records) == 1
        assert records[0].placement == 'cart'

    def test_flat_array_fallback(self):
        """A flat top-level array is tolerated for robustness; placement is None."""
        raw = [{'id': 1, 'min': 100}, {'id': 2, 'min': 200}]

        records = parse_portal_bids_response(raw, payment_type='cpm')

        assert [r.placement for r in records] == [None, None]
        assert [r.nm_id for r in records] == [1, 2]

    def test_empty_payload_returns_empty_list(self):
        """Empty dict / list / unexpected shape yields no records."""
        assert parse_portal_bids_response({}, payment_type='cpc') == []
        assert parse_portal_bids_response([], payment_type='cpc') == []
        assert parse_portal_bids_response('garbage', payment_type='cpc') == []  # type: ignore[arg-type]

    def test_missing_reach_tiers_default_to_zeroed_tier(self):
        """A per-NM entry without reach_* keys still parses cleanly."""
        raw = {'combined': [{'id': 99, 'min': 7}]}

        records = parse_portal_bids_response(raw, payment_type='cpc')

        assert len(records) == 1
        rec = records[0]
        assert rec.reach_max == ReachTier()
        assert rec.reach_medium == ReachTier()
        assert rec.reach_min == ReachTier()


class TestPortalBidRecommendationFromPortal:
    """Tests for the dataclass factory."""

    def test_minimal_entry(self):
        """from_portal tolerates a sparse entry by defaulting missing fields."""
        rec = PortalBidRecommendation.from_portal(
            {'id': 42}, payment_type='cpc', placement='search',
        )

        assert rec.nm_id == 42
        assert rec.payment_type == 'cpc'
        assert rec.placement == 'search'
        assert rec.min_bid == 0
        assert rec.reach_max == ReachTier()

    def test_full_entry(self):
        """from_portal copies every documented field."""
        entry = CPM_MANUAL_FIXTURE['combined'][0]

        rec = PortalBidRecommendation.from_portal(
            entry, payment_type='cpm', placement='combined',
        )

        assert rec.nm_id == 183813043
        assert rec.min_bid == 12000
        assert rec.reach_max.min == 39000
        assert rec.reach_medium.budget == 106600


class TestReachTierFromPortal:
    """Tests for the inner ReachTier factory."""

    def test_none_yields_zeroed_tier(self):
        assert ReachTier.from_portal(None) == ReachTier()

    def test_missing_keys_default_to_zero(self):
        assert ReachTier.from_portal({}) == ReachTier()

    def test_partial_dict(self):
        tier = ReachTier.from_portal({'bid': 1500, 'clicks': 30})
        assert tier.bid == 1500
        assert tier.clicks == 30
        assert tier.budget == 0  # missing keys still zero
