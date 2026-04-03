"""Tests for wb.domain.analytics_models."""

from wb.domain.analytics_models import (
    AggregationLevel,
    CsvReportStatus,
    FunnelHistoryDay,
    ProductFunnelHistory,
    ProductFunnelStats,
    ReportType,
    SearchReportGroup,
    SearchReportProduct,
    SearchTextEntry,
)


class TestReportType:
    """Tests for ReportType enum."""

    def test_detail_history_value(self):
        assert ReportType.DETAIL_HISTORY == 'DETAIL_HISTORY_REPORT'

    def test_all_values_are_strings(self):
        for member in ReportType:
            assert isinstance(member.value, str)

    def test_seven_members(self):
        assert len(ReportType) == 7


class TestAggregationLevel:
    """Tests for AggregationLevel enum."""

    def test_day_and_week(self):
        assert AggregationLevel.DAY == 'day'
        assert AggregationLevel.WEEK == 'week'


class TestProductFunnelStats:
    """Tests for ProductFunnelStats.from_api."""

    def test_from_api_full(self):
        data = {
            'product': {
                'nmId': 123,
                'title': 'Sneakers',
                'vendorCode': 'V123',
                'brandName': 'Nike',
                'subjectId': 10,
                'subjectName': 'Shoes',
            },
            'statistic': {
                'selected': {
                    'openCount': 100,
                    'cartCount': 50,
                    'orderCount': 20,
                    'orderSum': 5000,
                    'buyoutCount': 15,
                    'buyoutSum': 4000,
                    'cancelCount': 2,
                    'cancelSum': 300,
                    'avgPrice': 250,
                    'conversions': {
                        'addToCartPercent': 50.0,
                        'cartToOrderPercent': 40.0,
                        'buyoutPercent': 75.0,
                    },
                },
            },
        }
        result = ProductFunnelStats.from_api(data, currency='USD')

        assert result.nm_id == 123
        assert result.title == 'Sneakers'
        assert result.open_count == 100
        assert result.cart_count == 50
        assert result.cart_conversion == 50.0
        assert result.currency == 'USD'

    def test_from_api_missing_fields(self):
        result = ProductFunnelStats.from_api({})
        assert result.nm_id == 0
        assert result.title == ''
        assert result.open_count == 0

    def test_from_api_missing_conversions(self):
        data = {
            'product': {'nmId': 1},
            'statistic': {'selected': {}},
        }
        result = ProductFunnelStats.from_api(data)
        assert result.cart_conversion == 0.0


class TestFunnelHistoryDay:
    """Tests for FunnelHistoryDay.from_api."""

    def test_from_api(self):
        data = {
            'dt': '2025-12-01',
            'openCount': 50,
            'cartCount': 20,
            'orderCount': 10,
        }
        result = FunnelHistoryDay.from_api(data)
        assert result.dt == '2025-12-01'
        assert result.open_count == 50
        assert result.cart_count == 20

    def test_from_api_empty(self):
        result = FunnelHistoryDay.from_api({})
        assert result.dt == ''
        assert result.open_count == 0


class TestProductFunnelHistory:
    """Tests for ProductFunnelHistory.from_api."""

    def test_from_api_with_history(self):
        data = {
            'product': {'nmId': 456, 'title': 'Boots'},
            'history': [
                {'dt': '2025-12-01', 'openCount': 10},
                {'dt': '2025-12-02', 'openCount': 20},
            ],
            'currency': 'EUR',
        }
        result = ProductFunnelHistory.from_api(data)
        assert result.nm_id == 456
        assert result.title == 'Boots'
        assert len(result.history) == 2
        assert result.history[0].dt == '2025-12-01'
        assert result.currency == 'EUR'

    def test_from_api_empty_history(self):
        result = ProductFunnelHistory.from_api({'product': {'nmId': 1}})
        assert result.history == []


class TestSearchReportProduct:
    """Tests for SearchReportProduct.from_api."""

    def test_from_api(self):
        data = {
            'nmId': 789,
            'vendorCode': 'V789',
            'name': 'Jacket',
            'openCard': 200,
            'addToCart': 80,
            'orders': 30,
            'avgPosition': 3.5,
            'visibility': 65.0,
        }
        result = SearchReportProduct.from_api(data)
        assert result.nm_id == 789
        assert result.open_count == 200
        assert result.avg_position == 3.5

    def test_from_api_defaults(self):
        result = SearchReportProduct.from_api({})
        assert result.nm_id == 0
        assert result.open_count == 0


class TestSearchReportGroup:
    """Tests for SearchReportGroup.from_api."""

    def test_from_api_with_products(self):
        data = {
            'subjectId': 10,
            'subjectName': 'Shoes',
            'brandName': 'Nike',
            'tagId': 5,
            'products': [
                {'nmId': 1, 'openCard': 10},
                {'nmId': 2, 'openCard': 20},
            ],
        }
        result = SearchReportGroup.from_api(data)
        assert result.subject_id == 10
        assert result.brand_name == 'Nike'
        assert len(result.products) == 2
        assert result.products[0].nm_id == 1

    def test_from_api_no_products(self):
        result = SearchReportGroup.from_api({'subjectId': 1})
        assert result.products == []


class TestSearchTextEntry:
    """Tests for SearchTextEntry.from_api."""

    def test_from_api(self):
        data = {
            'text': 'running shoes',
            'frequency': 5000,
            'avgPosition': 2.5,
            'medianPosition': 2.0,
            'openCard': 300,
            'addToCart': 100,
            'orders': 50,
            'visibility': 80.0,
        }
        result = SearchTextEntry.from_api(data)
        assert result.text == 'running shoes'
        assert result.frequency == 5000
        assert result.avg_position == 2.5

    def test_from_api_empty(self):
        result = SearchTextEntry.from_api({})
        assert result.text == ''
        assert result.frequency == 0


class TestCsvReportStatus:
    """Tests for CsvReportStatus.from_api."""

    def test_from_api(self):
        data = {
            'id': 'abc-123',
            'name': 'My Report',
            'status': 'SUCCESS',
            'size': 4096,
            'createdAt': '2025-12-01 10:00:00',
            'startDate': '2025-11-01',
            'endDate': '2025-11-30',
        }
        result = CsvReportStatus.from_api(data)
        assert result.id == 'abc-123'
        assert result.name == 'My Report'
        assert result.status == 'SUCCESS'
        assert result.size == 4096

    def test_from_api_defaults(self):
        result = CsvReportStatus.from_api({})
        assert result.id == ''
        assert result.status == 'WAITING'
