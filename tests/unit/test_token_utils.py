"""Tests for wb.auth.token_utils — JWT payload decoding and claim extraction."""

from __future__ import annotations

import base64
import json

import pytest

from wb.auth.token_utils import decode_jwt_payload, extract_token_claims


def make_test_jwt(**claims) -> str:
    """Build a JWT-shaped string with the given payload claims.

    Only the middle (payload) segment matters — extract_token_claims and
    decode_jwt_payload never verify the signature. Header and signature
    are placeholder strings.
    """
    payload_json = json.dumps(claims, separators=(',', ':')).encode('utf-8')
    payload_b64 = base64.urlsafe_b64encode(payload_json).rstrip(b'=').decode('ascii')
    return f'eyJhbGciOiJFUzI1NiJ9.{payload_b64}.sig'


# Synthetic tokens matching the real WB token shape observed in production.
TOKEN_PROD_BASE = make_test_jwt(
    acc=1, ent=1, exp=1790136818,
    id='019d209f-83f1-7c7a-a060-faa7d79dcfef',
    iid=734861740, oid=668554, s=15614,
    sid='407bbe2b-f3f9-404d-906f-99b2ef926815',
    t=False, uid=734861740,
)

TOKEN_TEST = make_test_jwt(
    acc=1, ent=1, exp=9999999999,
    id='abc', iid=1, oid=999, s=1, sid='xyz',
    t=True, uid=1,
)


class TestDecodeJwtPayload:
    """decode_jwt_payload returns the payload dict or {} on failure."""

    def test_decodes_real_wb_token_shape(self):
        payload = decode_jwt_payload(TOKEN_PROD_BASE)
        assert payload['oid'] == 668554
        assert payload['exp'] == 1790136818
        assert payload['t'] is False
        assert payload['uid'] == 734861740

    @pytest.mark.parametrize(
        'bad',
        ['', 'not.a.jwt', 'only.two', 'a.b.c.d.e', '...'],
        ids=['empty', 'no-dots', 'two-parts', 'five-parts', 'just-dots'],
    )
    def test_malformed_token_returns_empty(self, bad):
        assert decode_jwt_payload(bad) == {}

    def test_non_base64_payload_returns_empty(self):
        assert decode_jwt_payload('header.!!!not-base64!!!.sig') == {}

    def test_payload_with_invalid_json_returns_empty(self):
        # Valid base64 but not JSON
        garbage = base64.urlsafe_b64encode(b'\xff\xff\xfenot json').rstrip(b'=').decode('ascii')
        assert decode_jwt_payload(f'h.{garbage}.s') == {}

    def test_padding_recovery(self):
        # Make a token whose payload length isn't a multiple of 4 (no padding)
        token = make_test_jwt(oid=42)
        # Sanity: the second segment shouldn't have '=' padding
        assert '=' not in token.split('.')[1]
        assert decode_jwt_payload(token)['oid'] == 42


class TestExtractTokenClaims:
    """extract_token_claims normalizes payload → seller_id/expires_at/is_test."""

    def test_seller_id_stringified_from_oid(self):
        claims = extract_token_claims(TOKEN_PROD_BASE)
        assert claims['seller_id'] == '668554'
        assert isinstance(claims['seller_id'], str)

    def test_expires_at_from_exp(self):
        assert extract_token_claims(TOKEN_PROD_BASE)['expires_at'] == 1790136818

    def test_is_test_false_when_t_false(self):
        assert extract_token_claims(TOKEN_PROD_BASE)['is_test'] is False

    def test_is_test_true_when_t_true(self):
        assert extract_token_claims(TOKEN_TEST)['is_test'] is True

    def test_test_token_seller_id_still_extracted(self):
        claims = extract_token_claims(TOKEN_TEST)
        assert claims['seller_id'] == '999'

    def test_empty_token_yields_none_claims(self):
        claims = extract_token_claims('garbage')
        assert claims == {'seller_id': None, 'expires_at': None, 'is_test': False}

    def test_token_without_oid_yields_none_seller_id(self):
        token = make_test_jwt(exp=123, t=False)
        claims = extract_token_claims(token)
        assert claims['seller_id'] is None
        assert claims['expires_at'] == 123

    def test_token_without_t_defaults_is_test_false(self):
        token = make_test_jwt(oid=1, exp=2)
        assert extract_token_claims(token)['is_test'] is False
