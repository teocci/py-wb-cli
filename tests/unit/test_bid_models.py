"""Tests for the F-19 bid domain dataclasses.

Covers RecommendedBid, MinimumBid, and CurrentBid — each parsed from the
real WB endpoint shapes documented in docs/swagger/08-promotion.yaml.
"""

from __future__ import annotations

from wb.domain.models import CurrentBid, MinimumBid, RecommendedBid


class TestRecommendedBidFromApi:
    """Parses the /v0/bids/recommendations response object."""

    def test_full_swagger_example(self) -> None:
        data = {
            'advertId': 987654321,
            'nmId': 123456789,
            'base': {
                'competitiveBid': {'bidKopecks': 39500},
                'leadersBid': {'bidKopecks': 66900},
                'top2': {'bidKopecks': 0},
            },
            'normQueries': [
                {
                    'normQuery': 'shirt',
                    'reachMax': {'bidKopecks': 50500},
                },
            ],
        }
        bid = RecommendedBid.from_api(data, campaign_id=987654321)
        assert bid.campaign_id == 987654321
        assert bid.nm_id == 123456789
        assert bid.competitive == 39500
        assert bid.leaders == 66900
        assert bid.top2 == 0
        assert bid.error is None

    def test_missing_base_fields_default_to_zero(self) -> None:
        bid = RecommendedBid.from_api({'nmId': 7, 'base': {}}, campaign_id=1)
        assert bid.nm_id == 7
        assert bid.competitive == 0
        assert bid.leaders == 0
        assert bid.top2 == 0

    def test_null_base_handled(self) -> None:
        bid = RecommendedBid.from_api(
            {'nmId': 7, 'base': None}, campaign_id=1,
        )
        assert bid.competitive == 0


class TestMinimumBidFromApi:
    """Parses one entry from /v1/bids/min response's bids[] array."""

    def test_full_swagger_example(self) -> None:
        data = {
            'nm_id': 12345678,
            'bids': [
                {'type': 'combined', 'value': 155},
                {'type': 'search', 'value': 250},
                {'type': 'recommendation', 'value': 270},
            ],
        }
        bid = MinimumBid.from_api(data, campaign_id=42)
        assert bid.campaign_id == 42
        assert bid.nm_id == 12345678
        assert bid.combined == 155
        assert bid.search == 250
        assert bid.recommendation == 270

    def test_partial_placements_default_to_zero(self) -> None:
        data = {'nm_id': 1, 'bids': [{'type': 'search', 'value': 100}]}
        bid = MinimumBid.from_api(data, campaign_id=1)
        assert bid.search == 100
        assert bid.combined == 0
        assert bid.recommendation == 0

    def test_null_bids_handled(self) -> None:
        bid = MinimumBid.from_api({'nm_id': 1, 'bids': None}, campaign_id=1)
        assert bid.combined == 0


class TestCurrentBidFromNmSetting:
    """Parses one nm_settings[] entry from /api/advert/v2/adverts."""

    def test_full_example(self) -> None:
        nm = {
            'nm_id': 987654321,
            'bids_kopecks': {'recommendations': 11200, 'search': 11200},
            'subject': {'id': 54, 'name': 'rings'},
        }
        bid = CurrentBid.from_nm_setting(nm, campaign_id=42)
        assert bid.campaign_id == 42
        assert bid.nm_id == 987654321
        assert bid.search == 11200
        assert bid.recommendations == 11200

    def test_zero_bids(self) -> None:
        nm = {
            'nm_id': 1,
            'bids_kopecks': {'recommendations': 0, 'search': 0},
        }
        bid = CurrentBid.from_nm_setting(nm, campaign_id=1)
        assert bid.search == 0
        assert bid.recommendations == 0

    def test_missing_bids_kopecks(self) -> None:
        bid = CurrentBid.from_nm_setting({'nm_id': 7}, campaign_id=1)
        assert bid.nm_id == 7
        assert bid.search == 0
        assert bid.recommendations == 0
