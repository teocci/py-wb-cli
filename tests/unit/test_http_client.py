"""Tests for wb.client.http — WbHttpClient with mocked HTTP via respx."""

import httpx
import pytest
import respx

from wb.client.http import WbHttpClient
from wb.core.exceptions import ApiError, AuthenticationError, RateLimitError

BASE_URL = 'https://test-api.example.com'


class TestWbHttpClient:
    """Tests for WbHttpClient request handling and error mapping."""

    # ── Successful responses ──────────────────────────────────────────

    def test_successful_get(self):
        """Successful GET request returns parsed JSON."""
        with respx.mock:
            respx.get(f'{BASE_URL}/test').mock(
                return_value=httpx.Response(200, json={'result': 'ok'})
            )
            with WbHttpClient(BASE_URL, 'test-token') as client:
                result = client.get('/test')
                assert result == {'result': 'ok'}

    def test_successful_get_with_params(self):
        """GET request passes query parameters correctly."""
        with respx.mock:
            route = respx.get(f'{BASE_URL}/items').mock(
                return_value=httpx.Response(200, json={'items': []})
            )
            with WbHttpClient(BASE_URL, 'token') as client:
                result = client.get('/items', params={'page': '1', 'limit': '10'})
                assert result == {'items': []}
                assert route.called

    def test_post_sends_json_body(self):
        """POST sends JSON body correctly."""
        with respx.mock:
            route = respx.post(f'{BASE_URL}/test').mock(
                return_value=httpx.Response(200, json={'created': True})
            )
            with WbHttpClient(BASE_URL, 'token') as client:
                result = client.post('/test', json_body={'name': 'test'})
                assert result == {'created': True}
                assert route.called

    def test_empty_response_returns_none(self):
        """204 No Content returns None."""
        with respx.mock:
            respx.get(f'{BASE_URL}/test').mock(
                return_value=httpx.Response(204)
            )
            with WbHttpClient(BASE_URL, 'token') as client:
                result = client.get('/test')
                assert result is None

    def test_200_with_empty_body_returns_none(self):
        """200 with empty content returns None."""
        with respx.mock:
            respx.get(f'{BASE_URL}/test').mock(
                return_value=httpx.Response(200, content=b'')
            )
            with WbHttpClient(BASE_URL, 'token') as client:
                result = client.get('/test')
                assert result is None

    # ── Authentication errors ─────────────────────────────────────────

    def test_auth_failure_raises(self):
        """401 raises AuthenticationError."""
        with respx.mock:
            respx.get(f'{BASE_URL}/test').mock(
                return_value=httpx.Response(401)
            )
            with WbHttpClient(BASE_URL, 'bad-token') as client:
                with pytest.raises(AuthenticationError, match='Authentication failed'):
                    client.get('/test')

    def test_auth_error_not_retried(self):
        """401 is never retried regardless of max_retries."""
        with respx.mock:
            route = respx.get(f'{BASE_URL}/test').mock(
                return_value=httpx.Response(401)
            )
            with WbHttpClient(BASE_URL, 'bad', max_retries=3) as client:
                with pytest.raises(AuthenticationError):
                    client.get('/test')
                assert route.call_count == 1

    # ── Rate limit errors ─────────────────────────────────────────────

    def test_rate_limit_raises(self):
        """429 raises RateLimitError with retry_after extracted."""
        with respx.mock:
            respx.get(f'{BASE_URL}/test').mock(
                return_value=httpx.Response(429, headers={'Retry-After': '5'})
            )
            with WbHttpClient(BASE_URL, 'token', max_retries=0) as client:
                with pytest.raises(RateLimitError) as exc_info:
                    client.get('/test')
                assert exc_info.value.retry_after == 5.0

    def test_rate_limit_without_retry_after(self):
        """429 without Retry-After header still raises RateLimitError."""
        with respx.mock:
            respx.get(f'{BASE_URL}/test').mock(
                return_value=httpx.Response(429)
            )
            with WbHttpClient(BASE_URL, 'token', max_retries=0) as client:
                with pytest.raises(RateLimitError) as exc_info:
                    client.get('/test')
                assert exc_info.value.retry_after is None

    # ── API errors ────────────────────────────────────────────────────

    @pytest.mark.parametrize(
        'status_code',
        [400, 403, 404, 422],
        ids=['bad-request', 'forbidden', 'not-found', 'unprocessable'],
    )
    def test_non_retryable_api_errors(self, status_code):
        """Non-retryable 4xx errors raise ApiError immediately."""
        with respx.mock:
            route = respx.get(f'{BASE_URL}/test').mock(
                return_value=httpx.Response(status_code, text='error body')
            )
            with WbHttpClient(BASE_URL, 'token', max_retries=3) as client:
                with pytest.raises(ApiError) as exc_info:
                    client.get('/test')
                assert exc_info.value.status_code == status_code
                assert exc_info.value.response_body == 'error body'
                # Non-retryable errors should only be attempted once
                assert route.call_count == 1

    def test_server_error_raises(self):
        """500 raises ApiError with status code and body."""
        with respx.mock:
            respx.get(f'{BASE_URL}/test').mock(
                return_value=httpx.Response(500, text='server error')
            )
            with WbHttpClient(BASE_URL, 'token', max_retries=0) as client:
                with pytest.raises(ApiError) as exc_info:
                    client.get('/test')
                assert exc_info.value.status_code == 500

    # ── Context manager ───────────────────────────────────────────────

    def test_context_manager_closes_client(self):
        """Exiting the context manager closes the underlying httpx client."""
        with WbHttpClient(BASE_URL, 'token') as client:
            inner_client = client._client

        assert inner_client.is_closed

    # ── Authorization header ──────────────────────────────────────────

    def test_sends_authorization_header(self):
        """Requests include the token in the Authorization header."""
        with respx.mock:
            route = respx.get(f'{BASE_URL}/test').mock(
                return_value=httpx.Response(200, json={})
            )
            with WbHttpClient(BASE_URL, 'my-secret-token') as client:
                client.get('/test')

            request = route.calls[0].request
            assert request.headers['authorization'] == 'my-secret-token'

    # ── Trailing slash on base_url ────────────────────────────────────

    def test_base_url_trailing_slash_stripped(self):
        """Trailing slash on base_url is stripped to avoid double slashes."""
        with respx.mock:
            respx.get(f'{BASE_URL}/endpoint').mock(
                return_value=httpx.Response(200, json={'ok': True})
            )
            with WbHttpClient(f'{BASE_URL}/', 'token') as client:
                result = client.get('/endpoint')
                assert result == {'ok': True}

    # ── POST with params ──────────────────────────────────────────────

    def test_post_with_params_and_body(self):
        """POST can send both query params and a JSON body."""
        with respx.mock:
            route = respx.post(f'{BASE_URL}/create').mock(
                return_value=httpx.Response(201, json={'id': 42})
            )
            with WbHttpClient(BASE_URL, 'token') as client:
                result = client.post(
                    '/create',
                    params={'dry_run': 'true'},
                    json_body={'name': 'new-item'},
                )
                assert result == {'id': 42}
                assert route.called
