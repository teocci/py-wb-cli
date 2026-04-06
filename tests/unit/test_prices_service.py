"""Tests for wb.services.prices.PricesService and ProductPrice domain model."""

from unittest.mock import MagicMock

import pytest

from wb.domain.models import ProductPrice, ProductPriceSize
from wb.services.prices import PricesService


# ── Test helpers ──────────────────────────────────────────────────────────────

def _make_goods_item(
        nm_id: int = 100,
        vendor_code: str = 'VENDOR-1',
        discount: int = 20,
        club_discount: int = 0,
        price: float = 1000.0,
        discounted_price: float = 800.0,
        currency: str = 'RUB',
) -> dict:
    """Build a minimal listGoods item dict matching the Prices API shape."""
    return {
        'nmID': nm_id,
        'vendorCode': vendor_code,
        'currencyIsoCode4217': currency,
        'discount': discount,
        'clubDiscount': club_discount,
        'editableSizePrice': False,
        'sizes': [{
            'sizeID': nm_id * 10,
            'price': price,
            'discountedPrice': discounted_price,
            'clubDiscountedPrice': discounted_price,
            'techSizeName': '0',
        }],
    }


def _one_page(*items) -> dict:
    """Wrap items in a standard API response envelope."""
    return {'data': {'listGoods': list(items)}}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def mock_client():
    """Create a mock PricesClient."""
    return MagicMock()


@pytest.fixture()
def service(mock_client):
    """Create a PricesService with mock client."""
    return PricesService(mock_client)


# ── PricesService.get_prices() ────────────────────────────────────────────────

class TestGetPrices:
    """Tests for PricesService.get_prices()."""

    def test_returns_all_products_when_no_filters(self, service, mock_client):
        mock_client.list_goods.return_value = _one_page(
            _make_goods_item(nm_id=1),
            _make_goods_item(nm_id=2),
        )
        result = service.get_prices()
        assert len(result) == 2
        assert all(isinstance(p, ProductPrice) for p in result)

    def test_filters_by_nm_ids(self, service, mock_client):
        mock_client.list_goods.return_value = _one_page(
            _make_goods_item(nm_id=10),
            _make_goods_item(nm_id=20),
            _make_goods_item(nm_id=30),
        )
        result = service.get_prices(nm_ids=[10, 30])
        assert {p.nm_id for p in result} == {10, 30}

    def test_filters_by_min_discount(self, service, mock_client):
        mock_client.list_goods.return_value = _one_page(
            _make_goods_item(nm_id=1, discount=10),
            _make_goods_item(nm_id=2, discount=25),
            _make_goods_item(nm_id=3, discount=50),
        )
        result = service.get_prices(min_discount=25)
        assert len(result) == 2
        assert all(p.discount >= 25 for p in result)

    def test_combines_nm_id_and_min_discount_filters(self, service, mock_client):
        mock_client.list_goods.return_value = _one_page(
            _make_goods_item(nm_id=1, discount=5),
            _make_goods_item(nm_id=2, discount=30),
            _make_goods_item(nm_id=3, discount=30),
        )
        result = service.get_prices(nm_ids=[1, 2], min_discount=20)
        assert len(result) == 1
        assert result[0].nm_id == 2

    def test_result_sorted_by_nm_id(self, service, mock_client):
        mock_client.list_goods.return_value = _one_page(
            _make_goods_item(nm_id=300),
            _make_goods_item(nm_id=100),
            _make_goods_item(nm_id=200),
        )
        result = service.get_prices()
        assert [p.nm_id for p in result] == [100, 200, 300]

    def test_returns_empty_list_when_no_goods(self, service, mock_client):
        mock_client.list_goods.return_value = _one_page()
        result = service.get_prices()
        assert result == []

    def test_handles_null_list_goods(self, service, mock_client):
        mock_client.list_goods.return_value = {'data': {}}
        result = service.get_prices()
        assert result == []

    def test_handles_missing_data_key(self, service, mock_client):
        mock_client.list_goods.return_value = {}
        result = service.get_prices()
        assert result == []


# ── Pagination ─────────────────────────────────────────────────────────────────

class TestAutoPagination:
    """Tests for PricesService._fetch_all_pages() pagination logic."""

    def test_single_page_when_underfull(self, service, mock_client):
        """A page with fewer than 1000 items terminates pagination immediately."""
        mock_client.list_goods.return_value = _one_page(
            *[_make_goods_item(nm_id=i) for i in range(5)]
        )
        service.get_prices()
        assert mock_client.list_goods.call_count == 1

    def test_two_pages_when_first_is_full(self, service, mock_client):
        """A full first page triggers a second API call."""
        full_page = [_make_goods_item(nm_id=i) for i in range(1000)]
        partial_page = [_make_goods_item(nm_id=i + 1000) for i in range(50)]
        mock_client.list_goods.side_effect = [
            {'data': {'listGoods': full_page}},
            {'data': {'listGoods': partial_page}},
        ]
        result = service.get_prices()
        assert mock_client.list_goods.call_count == 2
        assert len(result) == 1050

    def test_offset_increments_by_page_limit(self, service, mock_client):
        """Second call uses offset=1000."""
        full_page = [_make_goods_item(nm_id=i) for i in range(1000)]
        mock_client.list_goods.side_effect = [
            {'data': {'listGoods': full_page}},
            {'data': {'listGoods': []}},
        ]
        service.get_prices()
        second_kwargs = mock_client.list_goods.call_args_list[1][1]
        assert second_kwargs.get('offset') == 1000

    def test_stops_on_empty_page(self, service, mock_client):
        """An empty first page makes exactly one call and returns no items."""
        mock_client.list_goods.return_value = {'data': {'listGoods': []}}
        result = service.get_prices()
        assert mock_client.list_goods.call_count == 1
        assert result == []


# ── ProductPriceSize model ────────────────────────────────────────────────────

class TestProductPriceSize:
    """Tests for ProductPriceSize.from_api()."""

    def test_maps_all_fields(self):
        data = {
            'sizeID': 999,
            'price': 1190.0,
            'discountedPrice': 868.7,
            'clubDiscountedPrice': 850.0,
            'techSizeName': 'XL',
        }
        size = ProductPriceSize.from_api(data)
        assert size.size_id == 999
        assert size.price == 1190.0
        assert size.discounted_price == 868.7
        assert size.club_discounted_price == 850.0
        assert size.tech_size_name == 'XL'

    def test_defaults_for_missing_fields(self):
        size = ProductPriceSize.from_api({})
        assert size.size_id == 0
        assert size.price == 0.0
        assert size.tech_size_name == '0'


# ── ProductPrice model ────────────────────────────────────────────────────────

class TestProductPrice:
    """Tests for ProductPrice.from_api() and convenience properties."""

    def test_from_api_maps_fields(self):
        data = _make_goods_item(nm_id=42, vendor_code='TEST-SKU', discount=27)
        price = ProductPrice.from_api(data)
        assert price.nm_id == 42
        assert price.vendor_code == 'TEST-SKU'
        assert price.discount == 27
        assert price.currency_iso == 'RUB'
        assert price.club_discount == 0
        assert price.editable_size_price is False

    def test_base_price_property(self):
        data = _make_goods_item(price=1190.0)
        assert ProductPrice.from_api(data).base_price == 1190.0

    def test_final_price_property(self):
        data = _make_goods_item(discounted_price=868.7)
        assert ProductPrice.from_api(data).final_price == 868.7

    def test_club_price_property(self):
        data = {
            'nmID': 1, 'vendorCode': 'X', 'currencyIsoCode4217': 'RUB',
            'discount': 27, 'clubDiscount': 5, 'editableSizePrice': False,
            'sizes': [{
                'sizeID': 10, 'price': 1190.0,
                'discountedPrice': 868.7, 'clubDiscountedPrice': 825.0,
                'techSizeName': '0',
            }],
        }
        assert ProductPrice.from_api(data).club_price == 825.0

    def test_empty_sizes_give_zero_prices(self):
        data = {
            'nmID': 1, 'vendorCode': 'X', 'currencyIsoCode4217': 'RUB',
            'discount': 0, 'clubDiscount': 0, 'editableSizePrice': False,
            'sizes': [],
        }
        price = ProductPrice.from_api(data)
        assert price.base_price == 0.0
        assert price.final_price == 0.0
        assert price.club_price == 0.0

    def test_multi_size_properties_use_first_size(self):
        data = {
            'nmID': 1, 'vendorCode': 'X', 'currencyIsoCode4217': 'RUB',
            'discount': 10, 'clubDiscount': 0, 'editableSizePrice': True,
            'sizes': [
                {'sizeID': 1, 'price': 500.0, 'discountedPrice': 450.0,
                 'clubDiscountedPrice': 450.0, 'techSizeName': 'S'},
                {'sizeID': 2, 'price': 600.0, 'discountedPrice': 540.0,
                 'clubDiscountedPrice': 540.0, 'techSizeName': 'M'},
            ],
        }
        price = ProductPrice.from_api(data)
        assert price.base_price == 500.0
        assert price.final_price == 450.0
        assert len(price.sizes) == 2
