"""Tests for wb.services.clusters.ClusterService (normquery API)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wb.core.exceptions import ValidationError
from wb.domain.models import ClusterBidMutation, ClusterStats, MinusPhraseSet, SearchCluster
from wb.services.clusters import ClusterService


@pytest.fixture()
def mock_client() -> MagicMock:
    """Create a mock PromotionClient."""
    return MagicMock()


@pytest.fixture()
def service(mock_client: MagicMock) -> ClusterService:
    """Create a ClusterService with a mocked client."""
    return ClusterService(client=mock_client)


class TestListClusters:
    """Tests for ClusterService.list_clusters."""

    def test_parses_normquery_list_response(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """list_clusters parses active + excluded from normquery/list."""
        mock_client.get_cluster_list.return_value = {
            'items': [{
                'advertId': 100,
                'nmId': 200,
                'normQueries': {
                    'active': ['sneakers', 'boots'],
                    'excluded': ['sandals'],
                },
            }],
        }

        result = service.list_clusters(campaign_id=100, nm_id=200)

        assert len(result) == 3
        assert all(isinstance(c, SearchCluster) for c in result)
        assert result[0].norm_query == 'sneakers'
        assert result[0].is_active is True
        assert result[1].norm_query == 'boots'
        assert result[1].is_active is True
        assert result[2].norm_query == 'sandals'
        assert result[2].is_active is False
        mock_client.get_cluster_list.assert_called_once_with(
            [{'advertId': 100, 'nmId': 200}]
        )

    def test_empty_response(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """list_clusters returns empty list for empty response."""
        mock_client.get_cluster_list.return_value = {'items': []}

        result = service.list_clusters(campaign_id=100, nm_id=200)

        assert result == []

    def test_null_active_and_excluded(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """list_clusters handles null active/excluded arrays."""
        mock_client.get_cluster_list.return_value = {
            'items': [{
                'advertId': 100,
                'nmId': 200,
                'normQueries': {'active': None, 'excluded': None},
            }],
        }

        result = service.list_clusters(campaign_id=100, nm_id=200)

        assert result == []


class TestGetActiveClusters:
    """Tests for ClusterService.get_active_clusters."""

    def test_filters_active_only(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_active_clusters returns only active clusters."""
        mock_client.get_cluster_list.return_value = {
            'items': [{
                'advertId': 100,
                'nmId': 200,
                'normQueries': {
                    'active': ['sneakers'],
                    'excluded': ['boots'],
                },
            }],
        }

        result = service.get_active_clusters(campaign_id=100, nm_id=200)

        assert len(result) == 1
        assert result[0].norm_query == 'sneakers'
        assert result[0].is_active is True


class TestGetInactiveClusters:
    """Tests for ClusterService.get_inactive_clusters."""

    def test_filters_inactive_only(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_inactive_clusters returns only excluded clusters."""
        mock_client.get_cluster_list.return_value = {
            'items': [{
                'advertId': 100,
                'nmId': 200,
                'normQueries': {
                    'active': ['sneakers'],
                    'excluded': ['boots'],
                },
            }],
        }

        result = service.get_inactive_clusters(campaign_id=100, nm_id=200)

        assert len(result) == 1
        assert result[0].norm_query == 'boots'
        assert result[0].is_active is False


class TestGetClusterBids:
    """Tests for ClusterService.get_cluster_bids."""

    def test_parses_bids_response(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_cluster_bids returns clusters from get-bids response."""
        mock_client.get_cluster_bids.return_value = {
            'bids': [
                {'advert_id': 100, 'nm_id': 200, 'norm_query': 'sneakers', 'bid': 500},
                {'advert_id': 100, 'nm_id': 200, 'norm_query': 'boots', 'bid': 300},
            ],
        }

        result = service.get_cluster_bids(campaign_id=100, nm_id=200)

        assert len(result) == 2
        assert result[0].norm_query == 'sneakers'
        assert result[0].bid == 500
        mock_client.get_cluster_bids.assert_called_once_with(
            [{'advert_id': 100, 'nm_id': 200}]
        )

    def test_empty_bids(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_cluster_bids returns empty when no bids."""
        mock_client.get_cluster_bids.return_value = {'bids': []}

        result = service.get_cluster_bids(campaign_id=100, nm_id=200)

        assert result == []


class TestGetClusterStats:
    """Tests for ClusterService.get_cluster_stats."""

    def test_parses_stats_response(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_cluster_stats returns ClusterStats from normquery/stats."""
        mock_client.get_cluster_stats.return_value = {
            'stats': [{
                'advert_id': 100,
                'nm_id': 200,
                'stats': [
                    {
                        'norm_query': 'sneakers',
                        'views': 1000,
                        'clicks': 50,
                        'ctr': 5.0,
                        'orders': 5,
                        'spend': 250,
                        'avg_pos': 3.2,
                    },
                ],
            }],
        }

        result = service.get_cluster_stats(100, 200, '2025-12-01', '2025-12-31')

        assert len(result) == 1
        assert isinstance(result[0], ClusterStats)
        assert result[0].norm_query == 'sneakers'
        assert result[0].views == 1000


class TestGetMinusPhrases:
    """Tests for ClusterService.get_minus_phrases."""

    def test_parses_minus_response(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_minus_phrases returns MinusPhraseSet from get-minus."""
        mock_client.get_minus_phrases.return_value = {
            'items': [{
                'advert_id': 100,
                'nm_id': 200,
                'norm_queries': ['boots', 'sandals'],
            }],
        }

        result = service.get_minus_phrases(campaign_id=100, nm_id=200)

        assert isinstance(result, MinusPhraseSet)
        assert result.campaign_id == 100
        assert result.nm_id == 200
        assert result.phrases == ['boots', 'sandals']

    def test_empty_response(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_minus_phrases returns empty set when no data."""
        mock_client.get_minus_phrases.return_value = {'items': []}

        result = service.get_minus_phrases(campaign_id=100, nm_id=200)

        assert result.phrases == []


class TestGetClusterStatsDaily:
    """Tests for ClusterService.get_cluster_stats_daily."""

    def test_parses_daily_stats_response(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_cluster_stats_daily parses items[].dailyStats[]."""
        mock_client.get_cluster_stats_daily.return_value = {
            'items': [{
                'advertId': 100,
                'nmId': 200,
                'dailyStats': [
                    {'date': '2025-12-01', 'stat': {'normQuery': 'sneakers', 'views': 100}},
                    {'date': '2025-12-02', 'stat': {'normQuery': 'sneakers', 'views': 150}},
                ],
            }],
        }

        result = service.get_cluster_stats_daily(100, 200, '2025-12-01', '2025-12-02')

        assert len(result) == 2
        assert result[0]['date'] == '2025-12-01'
        assert result[1]['date'] == '2025-12-02'

    def test_empty_response(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_cluster_stats_daily returns empty on no data."""
        mock_client.get_cluster_stats_daily.return_value = {'items': []}

        result = service.get_cluster_stats_daily(100, 200, '2025-12-01', '2025-12-02')

        assert result == []


# ── Write operation tests ────────────────────────────────────────────


def _make_mutation(
    nm_id: int = 200, norm_query: str = 'sneakers', bid: int = 500,
) -> ClusterBidMutation:
    """Build a ClusterBidMutation for testing."""
    return ClusterBidMutation(nm_id=nm_id, norm_query=norm_query, bid=bid)


class TestSetClusterBids:
    """Tests for ClusterService.set_cluster_bids."""

    def test_calls_client_and_returns_result(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """set_cluster_bids calls client with correct payloads."""
        mutations = [_make_mutation()]
        result = service.set_cluster_bids(100, mutations)

        assert result.success is True
        assert result.dry_run is False
        assert '1 cluster bid(s)' in result.message
        mock_client.set_cluster_bids.assert_called_once_with(
            [{'advert_id': 100, 'nm_id': 200, 'norm_query': 'sneakers', 'bid': 500}]
        )

    def test_dry_run_skips_client(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """set_cluster_bids dry_run does not call client."""
        result = service.set_cluster_bids(100, [_make_mutation()], dry_run=True)

        assert result.dry_run is True
        assert result.success is True
        mock_client.set_cluster_bids.assert_not_called()

    def test_empty_mutations_raises(
        self, service: ClusterService,
    ) -> None:
        """set_cluster_bids raises on empty list."""
        with pytest.raises(ValidationError, match='At least one'):
            service.set_cluster_bids(100, [])

    def test_too_many_mutations_raises(
        self, service: ClusterService,
    ) -> None:
        """set_cluster_bids raises when exceeding 100."""
        mutations = [_make_mutation(bid=i + 1) for i in range(101)]
        with pytest.raises(ValidationError, match='Maximum 100'):
            service.set_cluster_bids(100, mutations)

    def test_non_positive_bid_raises(
        self, service: ClusterService,
    ) -> None:
        """set_cluster_bids raises on bid <= 0."""
        with pytest.raises(ValidationError, match='Bid must be positive'):
            service.set_cluster_bids(100, [_make_mutation(bid=0)])

    def test_multiple_mutations(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """set_cluster_bids handles multiple mutations."""
        mutations = [
            _make_mutation(norm_query='sneakers', bid=500),
            _make_mutation(norm_query='boots', bid=300),
        ]
        result = service.set_cluster_bids(100, mutations)

        assert result.success is True
        assert '2 cluster bid(s)' in result.message


class TestDeleteClusterBids:
    """Tests for ClusterService.delete_cluster_bids."""

    def test_calls_client_and_returns_result(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """delete_cluster_bids calls client with correct payloads."""
        mutations = [_make_mutation()]
        result = service.delete_cluster_bids(100, mutations)

        assert result.success is True
        assert result.dry_run is False
        assert 'Deleted 1' in result.message
        mock_client.delete_cluster_bids.assert_called_once()

    def test_dry_run_skips_client(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """delete_cluster_bids dry_run does not call client."""
        result = service.delete_cluster_bids(100, [_make_mutation()], dry_run=True)

        assert result.dry_run is True
        mock_client.delete_cluster_bids.assert_not_called()

    def test_empty_mutations_raises(
        self, service: ClusterService,
    ) -> None:
        """delete_cluster_bids raises on empty list."""
        with pytest.raises(ValidationError, match='At least one'):
            service.delete_cluster_bids(100, [])

    def test_too_many_mutations_raises(
        self, service: ClusterService,
    ) -> None:
        """delete_cluster_bids raises when exceeding 100."""
        mutations = [_make_mutation(bid=i + 1) for i in range(101)]
        with pytest.raises(ValidationError, match='Maximum 100'):
            service.delete_cluster_bids(100, mutations)


class TestSetMinusPhrases:
    """Tests for ClusterService.set_minus_phrases."""

    def test_calls_client_with_payload(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """set_minus_phrases calls client with to_api() output."""
        result = service.set_minus_phrases(100, 200, ['boots', 'sandals'])

        assert result.success is True
        assert result.dry_run is False
        mock_client.set_minus_phrases.assert_called_once_with({
            'advert_id': 100,
            'nm_id': 200,
            'norm_queries': ['boots', 'sandals'],
        })

    def test_dry_run_skips_client(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """set_minus_phrases dry_run does not call client."""
        result = service.set_minus_phrases(100, 200, ['boots'], dry_run=True)

        assert result.dry_run is True
        mock_client.set_minus_phrases.assert_not_called()

    def test_too_many_phrases_raises(
        self, service: ClusterService,
    ) -> None:
        """set_minus_phrases raises when exceeding 1000."""
        phrases = [f'phrase_{i}' for i in range(1001)]
        with pytest.raises(ValidationError, match='Maximum 1000'):
            service.set_minus_phrases(100, 200, phrases)

    def test_empty_phrases_clears(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """set_minus_phrases with empty list clears all."""
        result = service.set_minus_phrases(100, 200, [])

        assert result.success is True
        assert 'clear' in result.message.lower()
        mock_client.set_minus_phrases.assert_called_once_with({
            'advert_id': 100,
            'nm_id': 200,
            'norm_queries': [],
        })


class TestClearMinusPhrases:
    """Tests for ClusterService.clear_minus_phrases."""

    def test_delegates_to_set_with_empty(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """clear_minus_phrases delegates to set_minus_phrases with []."""
        result = service.clear_minus_phrases(100, 200)

        assert result.success is True
        mock_client.set_minus_phrases.assert_called_once_with({
            'advert_id': 100,
            'nm_id': 200,
            'norm_queries': [],
        })

    def test_dry_run(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """clear_minus_phrases supports dry_run."""
        result = service.clear_minus_phrases(100, 200, dry_run=True)

        assert result.dry_run is True
        mock_client.set_minus_phrases.assert_not_called()
