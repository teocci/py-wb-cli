"""Unit tests for ContentService — the description round-trip + classification."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wb.core.exceptions import ApiError
from wb.domain.content import (
    STATUS_CHANGED,
    STATUS_NOT_FOUND,
    STATUS_TOO_LONG,
    STATUS_UNCHANGED,
    ProductCard,
)
from wb.services.content import ContentService


def _raw_card(nm_id: int = 1, vendor: str = 'vc1', description: str = 'old description') -> dict:
    """A read-shaped card with read-only sub-fields the writer must drop."""
    return {
        'nmID': nm_id, 'vendorCode': vendor, 'brand': 'B', 'title': 'T',
        'description': description,
        'dimensions': {'length': 10, 'width': 5, 'height': 3, 'weightBrutto': 1, 'isValid': True},
        'characteristics': [{'id': 42, 'name': 'Color', 'value': ['red']}],
        'sizes': [{'chrtID': 99, 'techSize': 'S', 'wbSize': '42', 'skus': ['123'], 'price': 100}],
    }


@pytest.fixture
def client():
    return MagicMock()


@pytest.fixture
def svc(client):
    return ContentService(client)


class TestListCards:
    def test_parses_into_product_cards(self, svc, client):
        client.get_cards_list.return_value = [_raw_card(1, 'vc1', 'hello')]
        cards = svc.list_cards()
        assert len(cards) == 1
        assert isinstance(cards[0], ProductCard)
        assert cards[0].description == 'hello'
        assert cards[0].description_length == 5

    def test_nm_ids_filter_keeps_only_requested(self, svc, client):
        client.get_cards_list.return_value = [_raw_card(1, 'vc1'), _raw_card(2, 'vc2')]
        cards = svc.list_cards(nm_ids=[2])
        assert [c.nm_id for c in cards] == [2]

    def test_limit_passed_as_max_cards_when_no_nm_filter(self, svc, client):
        client.get_cards_list.return_value = []
        svc.list_cards(limit=5)
        assert client.get_cards_list.call_args.kwargs['max_cards'] == 5


class TestGetCard:
    def test_returns_exact_match(self, svc, client):
        client.get_cards_list.return_value = [_raw_card(7, 'vc7', 'desc')]
        card = svc.get_card(7)
        assert card is not None and card.nm_id == 7

    def test_returns_none_when_no_exact_match(self, svc, client):
        client.get_cards_list.return_value = [_raw_card(8, 'vc8')]
        assert svc.get_card(7) is None


class TestExport:
    def test_export_shape(self, svc, client):
        client.get_cards_list.return_value = [_raw_card(1, 'vc1', 'd')]
        records = svc.export_descriptions()
        assert records == [{'nmID': 1, 'vendorCode': 'vc1', 'title': 'T', 'description': 'd'}]


class TestApplyUpdates:
    def test_changed_roundtrip_preserves_other_fields(self, svc, client):
        client.get_cards_list.return_value = [_raw_card(1, 'vc1', 'old description')]
        client.update_cards.return_value = {'error': False}
        client.list_errors.return_value = []

        results, errors = svc.apply_updates({1: 'a brand new description'})

        assert results[0].status == STATUS_CHANGED
        assert errors == []
        payload = client.update_cards.call_args.args[0]
        assert len(payload) == 1
        sent = payload[0]
        assert sent['description'] == 'a brand new description'
        # round-trip strips read-only sub-fields, keeps the rest
        assert 'isValid' not in sent['dimensions']
        assert sent['characteristics'] == [{'id': 42, 'value': ['red']}]
        assert sent['sizes'][0]['chrtID'] == 99 and 'skus' in sent['sizes'][0]

    def test_unchanged_is_not_sent(self, svc, client):
        client.get_cards_list.return_value = [_raw_card(1, 'vc1', 'same')]
        results, errors = svc.apply_updates({1: 'same'})
        assert results[0].status == STATUS_UNCHANGED
        client.update_cards.assert_not_called()

    def test_too_long_is_rejected_not_sent(self, svc, client):
        client.get_cards_list.return_value = [_raw_card(1, 'vc1', 'old')]
        results, _ = svc.apply_updates({1: 'x' * 5001})
        assert results[0].status == STATUS_TOO_LONG
        client.update_cards.assert_not_called()

    def test_unknown_nm_id_is_not_found(self, svc, client):
        client.get_cards_list.return_value = [_raw_card(1, 'vc1')]
        results, _ = svc.apply_updates({999: 'whatever'})
        assert results[0].status == STATUS_NOT_FOUND
        client.update_cards.assert_not_called()

    def test_dry_run_classifies_without_writing(self, svc, client):
        client.get_cards_list.return_value = [_raw_card(1, 'vc1', 'old')]
        results, errors = svc.apply_updates({1: 'new'}, dry_run=True)
        assert results[0].status == STATUS_CHANGED
        assert errors == []
        client.update_cards.assert_not_called()
        client.list_errors.assert_not_called()

    def test_post_update_errors_mapped_to_nm_id(self, svc, client):
        client.get_cards_list.return_value = [_raw_card(1, 'vc1', 'old')]
        client.update_cards.return_value = {'error': False}
        client.list_errors.return_value = [
            {'errors': {'vc1': ['bad description'], 'other': ['ignored']}},
        ]
        _, errors = svc.apply_updates({1: 'new'})
        assert errors == ['nmID 1 (vc1): bad description']

    def test_response_error_flag_raises(self, svc, client):
        client.get_cards_list.return_value = [_raw_card(1, 'vc1', 'old')]
        client.update_cards.return_value = {'error': True, 'errorText': 'boom'}
        with pytest.raises(ApiError, match='boom'):
            svc.apply_updates({1: 'new'})

    def test_batches_respect_update_limit(self, svc, client, monkeypatch):
        monkeypatch.setattr('wb.services.content.CONTENT_UPDATE_BATCH_LIMIT', 2)
        client.get_cards_list.return_value = [
            _raw_card(1, 'vc1', 'o1'), _raw_card(2, 'vc2', 'o2'), _raw_card(3, 'vc3', 'o3'),
        ]
        client.update_cards.return_value = {'error': False}
        client.list_errors.return_value = []
        svc.apply_updates({1: 'n1', 2: 'n2', 3: 'n3'})
        assert client.update_cards.call_count == 2


class TestSetDescription:
    def test_changed_writes_once(self, svc, client):
        client.get_cards_list.return_value = [_raw_card(1, 'vc1', 'old')]
        client.update_cards.return_value = {'error': False}
        client.list_errors.return_value = []
        result, errors = svc.set_description(1, 'new')
        assert result.status == STATUS_CHANGED
        assert errors == []
        client.update_cards.assert_called_once()

    def test_unchanged_no_write(self, svc, client):
        client.get_cards_list.return_value = [_raw_card(1, 'vc1', 'same')]
        result, _ = svc.set_description(1, 'same')
        assert result.status == STATUS_UNCHANGED
        client.update_cards.assert_not_called()

    def test_not_found_no_write(self, svc, client):
        client.get_cards_list.return_value = []
        result, _ = svc.set_description(1, 'new')
        assert result.status == STATUS_NOT_FOUND
        client.update_cards.assert_not_called()

    def test_dry_run_no_write(self, svc, client):
        client.get_cards_list.return_value = [_raw_card(1, 'vc1', 'old')]
        result, _ = svc.set_description(1, 'new', dry_run=True)
        assert result.status == STATUS_CHANGED
        client.update_cards.assert_not_called()
