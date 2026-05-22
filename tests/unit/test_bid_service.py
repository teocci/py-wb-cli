"""Tests for wb.services.bids.BidService.

These tests exercise the F-19 rewrite: real WB endpoint shapes for the
three read commands plus pre-validation against terminal-state campaigns
and non-CPM billing.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wb.core.exceptions import ApiError, ValidationError
from wb.domain.models import CurrentBid, MinimumBid, RecommendedBid
from wb.services.bids import BidService


def _campaign_dict(
        *,
        campaign_id: int = 42,
        status: int = 9,
        payment_type: str = 'cpm',
        nm_settings: list[dict] | None = None,
) -> dict:
    """Build a /api/advert/v2/adverts entry suitable for tests."""
    return {
        'id': campaign_id,
        'status': status,
        'type': 9,
        'settings': {'name': 'Test', 'payment_type': payment_type},
        'nm_settings': nm_settings if nm_settings is not None else [
            {'nm_id': 10, 'bids_kopecks': {'search': 200, 'recommendations': 250}},
            {'nm_id': 20, 'bids_kopecks': {'search': 300, 'recommendations': 350}},
        ],
        'timestamps': {},
    }


def _recommend_response(nm_id: int) -> dict:
    """Build a /v0/bids/recommendations response matching the swagger example."""
    return {
        'advertId': 42,
        'nmId': nm_id,
        'base': {
            'competitiveBid': {'bidKopecks': nm_id * 10},
            'leadersBid': {'bidKopecks': nm_id * 20},
            'top2': {'bidKopecks': nm_id * 30},
        },
        'normQueries': [],
    }


@pytest.fixture()
def mock_client() -> MagicMock:
    """Create a mock PromotionClient."""
    return MagicMock()


@pytest.fixture()
def service(mock_client: MagicMock) -> BidService:
    """Create a BidService with a mocked client."""
    return BidService(client=mock_client)


class TestGetRecommendedBids:
    """Tests for BidService.get_recommended_bids."""

    def test_loops_over_campaign_nms(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """Without --nm: one call to get_recommended_bid per nm_id."""
        mock_client.get_campaign.return_value = _campaign_dict()
        mock_client.get_recommended_bid.side_effect = [
            _recommend_response(10), _recommend_response(20),
        ]

        result = service.get_recommended_bids(campaign_id=42)

        assert len(result) == 2
        assert all(isinstance(b, RecommendedBid) for b in result)
        assert result[0].campaign_id == 42
        assert result[0].nm_id == 10
        assert result[0].competitive == 100
        assert result[0].leaders == 200
        assert result[0].top2 == 300
        assert result[0].error is None
        assert result[1].nm_id == 20
        assert result[1].competitive == 200
        mock_client.get_recommended_bid.assert_any_call(42, 10)
        mock_client.get_recommended_bid.assert_any_call(42, 20)
        assert mock_client.get_recommended_bid.call_count == 2

    def test_nm_scopes_to_single_call(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """With --nm: exactly one call, regardless of campaign size."""
        mock_client.get_campaign.return_value = _campaign_dict()
        mock_client.get_recommended_bid.return_value = _recommend_response(20)

        result = service.get_recommended_bids(campaign_id=42, nm_id=20)

        assert len(result) == 1
        assert result[0].nm_id == 20
        assert result[0].competitive == 200
        mock_client.get_recommended_bid.assert_called_once_with(42, 20)

    def test_per_nm_400_is_soft_failure(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """Per-NM 400 records an error entry without aborting the loop."""
        mock_client.get_campaign.return_value = _campaign_dict()
        mock_client.get_recommended_bid.side_effect = [
            None, _recommend_response(20),
        ]

        result = service.get_recommended_bids(campaign_id=42)

        assert len(result) == 2
        assert result[0].nm_id == 10
        assert result[0].competitive == 0
        assert result[0].error is not None
        assert result[1].nm_id == 20
        assert result[1].competitive == 200
        assert result[1].error is None

    def test_per_nm_other_error_records_status_code(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """Per-NM ApiError records the HTTP code but does not raise."""
        mock_client.get_campaign.return_value = _campaign_dict(
            nm_settings=[{'nm_id': 10}],
        )
        mock_client.get_recommended_bid.side_effect = ApiError(
            'boom', status_code=403, response_body='nope',
        )

        result = service.get_recommended_bids(campaign_id=42)

        assert len(result) == 1
        assert result[0].error == 'HTTP 403'

    def test_missing_campaign_raises(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """get_campaign returning None surfaces as ValidationError."""
        mock_client.get_campaign.return_value = None

        with pytest.raises(ValidationError, match='not found'):
            service.get_recommended_bids(campaign_id=99)

    def test_terminal_status_raises(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """ARCHIVED campaigns are rejected before any bid call."""
        mock_client.get_campaign.return_value = _campaign_dict(status=7)

        with pytest.raises(ValidationError, match='terminal state'):
            service.get_recommended_bids(campaign_id=42)
        mock_client.get_recommended_bid.assert_not_called()

    def test_non_cpm_raises(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """CPC campaigns get a clear CPM-only error."""
        mock_client.get_campaign.return_value = _campaign_dict(
            payment_type='cpc',
        )

        with pytest.raises(ValidationError, match='CPM campaigns'):
            service.get_recommended_bids(campaign_id=42)
        mock_client.get_recommended_bid.assert_not_called()

    def test_empty_campaign_raises(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """Campaign with no nm_settings raises when --nm is not provided."""
        mock_client.get_campaign.return_value = _campaign_dict(nm_settings=[])

        with pytest.raises(ValidationError, match='no items'):
            service.get_recommended_bids(campaign_id=42)


class TestGetMinimumBids:
    """Tests for BidService.get_minimum_bids."""

    def test_calls_min_endpoint_with_payment_type(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """get_minimum_bids forwards nm_ids and payment_type to the client."""
        mock_client.get_campaign.return_value = _campaign_dict()
        mock_client.get_minimum_bids.return_value = [
            {
                'nm_id': 10,
                'bids': [
                    {'type': 'combined', 'value': 150},
                    {'type': 'search', 'value': 200},
                    {'type': 'recommendation', 'value': 250},
                ],
            },
        ]

        result = service.get_minimum_bids(campaign_id=42)

        assert len(result) == 1
        assert isinstance(result[0], MinimumBid)
        assert result[0].nm_id == 10
        assert result[0].combined == 150
        assert result[0].search == 200
        assert result[0].recommendation == 250
        mock_client.get_minimum_bids.assert_called_once_with(
            42,
            [10, 20],
            'cpm',
            ['combined', 'search', 'recommendation'],
        )

    def test_empty_campaign_returns_empty(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """Campaign with no nm_settings yields an empty list, no API call."""
        mock_client.get_campaign.return_value = _campaign_dict(nm_settings=[])

        result = service.get_minimum_bids(campaign_id=42)

        assert result == []
        mock_client.get_minimum_bids.assert_not_called()

    def test_terminal_status_raises(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """Deleted campaigns can't yield minimum bids."""
        mock_client.get_campaign.return_value = _campaign_dict(status=-1)

        with pytest.raises(ValidationError, match='terminal state'):
            service.get_minimum_bids(campaign_id=42)

    def test_batches_large_campaign(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """Campaigns with >100 NMs trigger multiple batched calls."""
        nm_settings = [
            {'nm_id': i, 'bids_kopecks': {'search': 0, 'recommendations': 0}}
            for i in range(150)
        ]
        mock_client.get_campaign.return_value = _campaign_dict(
            nm_settings=nm_settings,
        )
        mock_client.get_minimum_bids.return_value = []

        service.get_minimum_bids(campaign_id=42)

        assert mock_client.get_minimum_bids.call_count == 2
        first_args = mock_client.get_minimum_bids.call_args_list[0].args
        second_args = mock_client.get_minimum_bids.call_args_list[1].args
        assert len(first_args[1]) == 100
        assert len(second_args[1]) == 50

    def test_non_cpm_campaign_forwards_payment_type(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """CPC campaigns are allowed for minimum bids (endpoint accepts both)."""
        mock_client.get_campaign.return_value = _campaign_dict(
            payment_type='cpc',
        )
        mock_client.get_minimum_bids.return_value = []

        service.get_minimum_bids(campaign_id=42)

        call_args = mock_client.get_minimum_bids.call_args.args
        assert call_args[2] == 'cpc'


class TestGetItemBids:
    """Tests for BidService.get_item_bids (current bids from campaign info)."""

    def test_returns_current_bids_from_campaign(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """Reads bids_kopecks straight from nm_settings — no extra API call."""
        mock_client.get_campaign.return_value = _campaign_dict()

        result = service.get_item_bids(campaign_id=42)

        assert len(result) == 2
        assert all(isinstance(b, CurrentBid) for b in result)
        assert result[0].nm_id == 10
        assert result[0].search == 200
        assert result[0].recommendations == 250
        assert result[1].nm_id == 20
        assert result[1].search == 300
        # Verify no spurious bid endpoint calls
        mock_client.get_recommended_bid.assert_not_called()
        mock_client.get_minimum_bids.assert_not_called()

    def test_empty_nm_settings_yields_empty(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """Campaign with no items returns an empty list."""
        mock_client.get_campaign.return_value = _campaign_dict(nm_settings=[])

        result = service.get_item_bids(campaign_id=42)

        assert result == []

    def test_missing_campaign_raises(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """get_campaign returning None surfaces as ValidationError."""
        mock_client.get_campaign.return_value = None

        with pytest.raises(ValidationError, match='not found'):
            service.get_item_bids(campaign_id=99)
