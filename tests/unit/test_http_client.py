"""Tests for wb.client.http — WbHttpClient with mocked HTTP via respx."""

import httpx
import pytest
import respx

from wb.client.http import WbHttpClient
from wb.core.exceptions import (
    ApiError,
    AuthenticationError,
    RateLimitError,
    UpstreamError,
)

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

    def test_rate_limit_captures_response_body(self):
        """429 exception carries the raw response body for downstream triage."""
        body = '{"title":"too many requests","detail":"Limited by global limiter, per seller abc"}'
        with respx.mock:
            respx.get(f'{BASE_URL}/test').mock(
                return_value=httpx.Response(429, text=body)
            )
            with WbHttpClient(BASE_URL, 'token', max_retries=0) as client:
                with pytest.raises(RateLimitError) as exc_info:
                    client.get('/test')
                assert exc_info.value.response_body == body

    def test_seller_global_429_uses_patient_schedule(self, monkeypatch):
        """Seller-scope 429 (body contains 'global limiter') uses 5/15 s backoff."""
        import wb.client.http as http_mod

        sleeps: list[float] = []
        monkeypatch.setattr(http_mod.time, 'sleep', lambda s: sleeps.append(s))
        monkeypatch.setattr(http_mod.random, 'uniform', lambda a, b: 0.0)

        body = '{"title":"too many requests","detail":"Limited by global limiter, per seller abc"}'
        with respx.mock:
            respx.get(f'{BASE_URL}/test').mock(
                side_effect=[
                    httpx.Response(429, text=body),
                    httpx.Response(429, text=body),
                    httpx.Response(200, json={}),
                ]
            )
            with WbHttpClient(BASE_URL, 'token', max_retries=2) as client:
                client.get('/test')

        assert len(sleeps) == 2
        assert sleeps[0] >= 5.0
        assert sleeps[1] >= 15.0

    def test_plain_429_uses_short_schedule(self, monkeypatch):
        """Per-endpoint 429 (no 'global limiter') uses 1/2 s backoff as before."""
        import wb.client.http as http_mod

        sleeps: list[float] = []
        monkeypatch.setattr(http_mod.time, 'sleep', lambda s: sleeps.append(s))
        monkeypatch.setattr(http_mod.random, 'uniform', lambda a, b: 0.0)

        with respx.mock:
            respx.get(f'{BASE_URL}/test').mock(
                side_effect=[
                    httpx.Response(429, text='{"error":"rate limited"}'),
                    httpx.Response(429, text='{"error":"rate limited"}'),
                    httpx.Response(200, json={}),
                ]
            )
            with WbHttpClient(BASE_URL, 'token', max_retries=2) as client:
                client.get('/test')

        assert len(sleeps) == 2
        assert sleeps[0] < 5.0
        assert sleeps[1] < 10.0

    def test_retry_after_header_overrides_patient_schedule(self, monkeypatch):
        """Explicit Retry-After always wins, even on a seller-global 429."""
        import wb.client.http as http_mod

        sleeps: list[float] = []
        monkeypatch.setattr(http_mod.time, 'sleep', lambda s: sleeps.append(s))
        monkeypatch.setattr(http_mod.random, 'uniform', lambda a, b: 0.0)

        body = '{"detail":"Limited by global limiter, per seller abc"}'
        with respx.mock:
            respx.get(f'{BASE_URL}/test').mock(
                side_effect=[
                    httpx.Response(429, text=body, headers={'Retry-After': '120'}),
                    httpx.Response(200, json={}),
                ]
            )
            with WbHttpClient(BASE_URL, 'token', max_retries=1) as client:
                client.get('/test')

        assert sleeps == [120.0]

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
        """500 raises ApiError (UpstreamError subclass) with status code and body."""
        with respx.mock:
            respx.get(f'{BASE_URL}/test').mock(
                return_value=httpx.Response(500, text='server error')
            )
            with WbHttpClient(BASE_URL, 'token', max_retries=0) as client:
                with pytest.raises(ApiError) as exc_info:
                    client.get('/test')
                assert exc_info.value.status_code == 500

    # ── Retry classification: 5xx → UpstreamError, 429 → RateLimitError ──

    @pytest.mark.parametrize('status', [500, 502, 503, 504])
    def test_5xx_retries_exhausted_raise_upstream_error(
            self, status, monkeypatch,
    ):
        """5xx after all retries surfaces as UpstreamError (exit 6), not RATE_LIMITED."""
        import wb.client.http as http_mod
        monkeypatch.setattr(http_mod.time, 'sleep', lambda *_: None)
        with respx.mock:
            route = respx.get(f'{BASE_URL}/test').mock(
                return_value=httpx.Response(status, text='boom')
            )
            with WbHttpClient(BASE_URL, 'token', max_retries=2) as client:
                with pytest.raises(UpstreamError) as exc_info:
                    client.get('/test')
                assert exc_info.value.status_code == status
                assert exc_info.value.error_code == 'UPSTREAM_ERROR'
                # 3 attempts total = 1 initial + 2 retries.
                assert route.call_count == 3

    def test_429_retries_exhausted_still_raise_rate_limit_error(
            self, monkeypatch,
    ):
        """429 retry exhaustion keeps the original RATE_LIMITED surface."""
        import wb.client.http as http_mod
        monkeypatch.setattr(http_mod.time, 'sleep', lambda *_: None)
        with respx.mock:
            respx.get(f'{BASE_URL}/test').mock(
                return_value=httpx.Response(429, headers={'Retry-After': '0'}),
            )
            with WbHttpClient(BASE_URL, 'token', max_retries=1) as client:
                with pytest.raises(RateLimitError):
                    client.get('/test')

    def test_mixed_5xx_then_final_429_raises_rate_limit(self, monkeypatch):
        """User's reported pattern: several 5xx retries, final attempt returns 429."""
        import wb.client.http as http_mod
        monkeypatch.setattr(http_mod.time, 'sleep', lambda *_: None)
        with respx.mock:
            respx.get(f'{BASE_URL}/test').mock(
                side_effect=[
                    httpx.Response(502),
                    httpx.Response(502),
                    httpx.Response(502),
                    httpx.Response(429, headers={'Retry-After': '0'}),
                ]
            )
            with WbHttpClient(BASE_URL, 'token', max_retries=3) as client:
                with pytest.raises(RateLimitError):
                    client.get('/test')

    def test_mixed_5xx_with_final_5xx_raises_upstream(self, monkeypatch):
        """Pure 5xx storm surfaces as UpstreamError, not RATE_LIMITED."""
        import wb.client.http as http_mod
        monkeypatch.setattr(http_mod.time, 'sleep', lambda *_: None)
        with respx.mock:
            respx.get(f'{BASE_URL}/test').mock(
                side_effect=[
                    httpx.Response(502),
                    httpx.Response(503),
                    httpx.Response(502),
                    httpx.Response(504, text='gateway timeout'),
                ]
            )
            with WbHttpClient(BASE_URL, 'token', max_retries=3) as client:
                with pytest.raises(UpstreamError) as exc_info:
                    client.get('/test')
                assert exc_info.value.status_code == 504

    def test_5xx_recovers_on_retry(self, monkeypatch):
        """Transient 5xx followed by 200 succeeds without raising."""
        import wb.client.http as http_mod
        monkeypatch.setattr(http_mod.time, 'sleep', lambda *_: None)
        with respx.mock:
            respx.get(f'{BASE_URL}/test').mock(
                side_effect=[
                    httpx.Response(502),
                    httpx.Response(200, json={'ok': True}),
                ]
            )
            with WbHttpClient(BASE_URL, 'token', max_retries=2) as client:
                assert client.get('/test') == {'ok': True}

    def test_5xx_uses_upstream_delay_schedule(self, monkeypatch):
        """5xx backoff uses longer UPSTREAM delay (>= 5s base), not 1s base."""
        import wb.client.http as http_mod

        sleeps: list[float] = []
        monkeypatch.setattr(http_mod.time, 'sleep', lambda s: sleeps.append(s))
        # Freeze jitter so lower bound is predictable.
        monkeypatch.setattr(http_mod.random, 'uniform', lambda a, b: 0.0)

        with respx.mock:
            respx.get(f'{BASE_URL}/test').mock(
                side_effect=[
                    httpx.Response(502),
                    httpx.Response(502),
                    httpx.Response(200, json={}),
                ]
            )
            with WbHttpClient(BASE_URL, 'token', max_retries=2) as client:
                client.get('/test')

        # First 5xx retry delay should be ~5s (UPSTREAM_RETRY_BASE_DELAY).
        # Second should be ~15s (base * multiplier).
        assert len(sleeps) == 2
        assert sleeps[0] >= 5.0
        assert sleeps[1] >= 15.0

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
