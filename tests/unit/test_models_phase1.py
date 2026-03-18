"""Tests for Phase 1 domain model from_api() methods and new models."""

import pytest

from wb.domain.models import (
    AccountBalance,
    BudgetSnapshot,
    CampaignStats,
    ClusterStats,
    ItemBid,
    ProductCard,
    RecommendedBid,
    SearchCluster,
)


class TestProductCardFromApi:
    """Tests for ProductCard.from_api()."""

    def test_full_payload(self):
        data = {
            'nmId': 12345,
            'name': 'Test Product',
            'subjectId': 100,
            'subjectName': 'Perfume',
        }
        card = ProductCard.from_api(data)
        assert card.nm_id == 12345
        assert card.name == 'Test Product'
        assert card.subject_id == 100
        assert card.subject_name == 'Perfume'

    def test_minimal_payload(self):
        data = {'nmId': 99}
        card = ProductCard.from_api(data)
        assert card.nm_id == 99
        assert card.name == ''
        assert card.subject_id == 0
        assert card.subject_name == ''


class TestItemBidFromApi:
    """Tests for ItemBid.from_api()."""

    def test_full_payload(self):
        data = {
            'nmId': 555,
            'bid': 200,
            'recommendedBid': 300,
            'minimumBid': 100,
        }
        bid = ItemBid.from_api(data)
        assert bid.nm_id == 555
        assert bid.bid == 200
        assert bid.recommended_bid == 300
        assert bid.minimum_bid == 100

    def test_minimal_payload(self):
        data = {'nmId': 1}
        bid = ItemBid.from_api(data)
        assert bid.nm_id == 1
        assert bid.bid == 0
        assert bid.recommended_bid == 0
        assert bid.minimum_bid == 0


class TestSearchClusterFromApi:
    """Tests for SearchCluster.from_api()."""

    def test_active_cluster(self):
        data = {
            'id': 10,
            'keyword': 'perfume women',
            'count': 42,
            'bid': 150,
            'recommendedBid': 200,
        }
        cluster = SearchCluster.from_api(data, is_active=True)
        assert cluster.cluster_id == 10
        assert cluster.cluster_name == 'perfume women'
        assert cluster.count == 42
        assert cluster.is_active is True
        assert cluster.bid == 150
        assert cluster.recommended_bid == 200

    def test_inactive_cluster(self):
        data = {'id': 20, 'keyword': 'cologne men'}
        cluster = SearchCluster.from_api(data, is_active=False)
        assert cluster.cluster_id == 20
        assert cluster.is_active is False

    def test_defaults(self):
        data = {}
        cluster = SearchCluster.from_api(data)
        assert cluster.cluster_id == 0
        assert cluster.cluster_name == ''
        assert cluster.count == 0
        assert cluster.bid == 0


class TestBudgetSnapshotFromApi:
    """Tests for BudgetSnapshot.from_api()."""

    def test_full_payload(self):
        data = {'total': 50000, 'dailyBudget': 5000, 'balance': 30000}
        snap = BudgetSnapshot.from_api(data, campaign_id=111)
        assert snap.campaign_id == 111
        assert snap.total == 50000
        assert snap.daily == 5000
        assert snap.balance == 30000

    def test_zero_defaults(self):
        data = {}
        snap = BudgetSnapshot.from_api(data, campaign_id=0)
        assert snap.total == 0
        assert snap.daily == 0
        assert snap.balance == 0


class TestCampaignStatsFromApi:
    """Tests for CampaignStats.from_api()."""

    def test_full_payload(self):
        data = {
            'advertId': 999,
            'views': 10000,
            'clicks': 500,
            'ctr': 5.0,
            'orders': 50,
            'sum': 25000,
            'cpc': 50.0,
            'cpm': 2500.0,
        }
        stats = CampaignStats.from_api(data)
        assert stats.campaign_id == 999
        assert stats.views == 10000
        assert stats.clicks == 500
        assert stats.ctr == 5.0
        assert stats.orders == 50
        assert stats.spend == 25000
        assert stats.cpc == 50.0
        assert stats.cpm == 2500.0

    def test_empty_payload(self):
        stats = CampaignStats.from_api({})
        assert stats.campaign_id == 0
        assert stats.views == 0
        assert stats.spend == 0


class TestClusterStatsFromApi:
    """Tests for ClusterStats.from_api()."""

    def test_full_payload(self):
        data = {
            'id': 77,
            'keyword': 'eau de parfum',
            'views': 3000,
            'clicks': 120,
            'ctr': 4.0,
            'orders': 15,
            'sum': 6000,
        }
        stats = ClusterStats.from_api(data)
        assert stats.cluster_id == 77
        assert stats.cluster_name == 'eau de parfum'
        assert stats.views == 3000
        assert stats.clicks == 120
        assert stats.orders == 15
        assert stats.spend == 6000

    def test_empty_payload(self):
        stats = ClusterStats.from_api({})
        assert stats.cluster_id == 0
        assert stats.cluster_name == ''


class TestAccountBalance:
    """Tests for AccountBalance model and from_api()."""

    def test_from_api(self):
        data = {'balance': 100000, 'net': 85000, 'bonus': 15000}
        bal = AccountBalance.from_api(data)
        assert bal.balance == 100000
        assert bal.net == 85000
        assert bal.bonus == 15000

    def test_from_api_defaults(self):
        bal = AccountBalance.from_api({})
        assert bal.balance == 0
        assert bal.net == 0
        assert bal.bonus == 0

    def test_default_construction(self):
        bal = AccountBalance()
        assert bal.balance == 0


class TestRecommendedBid:
    """Tests for RecommendedBid model and from_api()."""

    def test_from_api(self):
        data = {'nmId': 777, 'cpm': 350, 'minCpm': 100}
        bid = RecommendedBid.from_api(data, campaign_id=42)
        assert bid.campaign_id == 42
        assert bid.nm_id == 777
        assert bid.recommended == 350
        assert bid.minimum == 100

    def test_from_api_defaults(self):
        bid = RecommendedBid.from_api({}, campaign_id=1)
        assert bid.nm_id == 0
        assert bid.recommended == 0
        assert bid.minimum == 0
