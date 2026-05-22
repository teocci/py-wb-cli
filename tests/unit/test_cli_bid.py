"""Tests for bid CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from wb.cli.app import app
from wb.core.exceptions import ValidationError
from wb.domain.models import CurrentBid, MinimumBid, RecommendedBid

runner = CliRunner()

FACTORY_PATH = 'wb.services._factory.create_bid_service'


def _make_recommended_bid(
        campaign_id: int = 42,
        nm_id: int = 555,
) -> RecommendedBid:
    """Create a RecommendedBid instance matching the F-19 dataclass shape."""
    return RecommendedBid(
        campaign_id=campaign_id,
        nm_id=nm_id,
        competitive=300,
        leaders=450,
        top2=600,
    )


def _make_minimum_bid(
        campaign_id: int = 42, nm_id: int = 555,
) -> MinimumBid:
    return MinimumBid(
        campaign_id=campaign_id, nm_id=nm_id,
        combined=120, search=200, recommendation=250,
    )


def _make_current_bid(
        campaign_id: int = 42, nm_id: int = 555,
) -> CurrentBid:
    return CurrentBid(
        campaign_id=campaign_id, nm_id=nm_id,
        search=180, recommendations=220,
    )


@pytest.fixture()
def mock_svc() -> MagicMock:
    """Return a MagicMock pretending to be BidService."""
    return MagicMock()


class TestBidRecommend:
    """Tests for the 'bid recommend' command."""

    def test_bid_recommend_help(self) -> None:
        """Help flag exits cleanly with usage information."""
        result = runner.invoke(app, ['bid', 'recommend', '--help'])
        assert result.exit_code == 0
        assert 'recommended' in result.output.lower()

    @patch(FACTORY_PATH)
    def test_bid_recommend_json(self, mock_factory: MagicMock) -> None:
        """JSON output exposes competitive/leaders/top2 per item."""
        svc = MagicMock()
        svc.get_recommended_bids.return_value = [_make_recommended_bid()]
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['--json', 'bid', 'recommend', '--campaign', '42'],
        )
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]['nm_id'] == 555
        assert parsed[0]['competitive'] == 300
        assert parsed[0]['leaders'] == 450
        assert parsed[0]['top2'] == 600
        assert parsed[0]['error'] is None
        svc.get_recommended_bids.assert_called_once_with(42, nm_id=None)

    @patch(FACTORY_PATH)
    def test_bid_recommend_with_nm_scopes_to_one(
            self, mock_factory: MagicMock,
    ) -> None:
        """--nm forwards to the service so only one item is queried."""
        svc = MagicMock()
        svc.get_recommended_bids.return_value = [_make_recommended_bid()]
        mock_factory.return_value = svc

        result = runner.invoke(
            app,
            ['--json', 'bid', 'recommend', '--campaign', '42', '--nm', '555'],
        )
        assert result.exit_code == 0
        svc.get_recommended_bids.assert_called_once_with(42, nm_id=555)

    @patch(FACTORY_PATH)
    def test_bid_recommend_non_cpm_raises_validation_error(
            self, mock_factory: MagicMock,
    ) -> None:
        """ValidationError from the service propagates with exit code 2.

        The global JSON-error formatting happens in ``__main__.main()`` which
        ``CliRunner`` does not invoke, so we verify the exception type and
        exit code directly — matching the pattern used in test_cli_stock_runway.
        """
        svc = MagicMock()
        svc.get_recommended_bids.side_effect = ValidationError(
            '`bid recommend` works only for CPM campaigns (campaign 42 uses cpc)'
        )
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['--json', 'bid', 'recommend', '--campaign', '42'],
        )
        assert result.exit_code != 0
        assert isinstance(result.exception, ValidationError)
        assert 'CPM' in str(result.exception)

    @patch(FACTORY_PATH)
    def test_bid_recommend_empty(self, mock_factory: MagicMock) -> None:
        """Empty recommendations show success message."""
        svc = MagicMock()
        svc.get_recommended_bids.return_value = []
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['--json', 'bid', 'recommend', '--campaign', '42'],
        )
        assert result.exit_code == 0
        assert 'No bid recommendations' in result.output


class TestBidMinimum:
    """Tests for the 'bid minimum' command."""

    @patch(FACTORY_PATH)
    def test_bid_minimum_json(self, mock_factory: MagicMock) -> None:
        """JSON output exposes combined/search/recommendation per item."""
        svc = MagicMock()
        svc.get_minimum_bids.return_value = [_make_minimum_bid()]
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['--json', 'bid', 'minimum', '--campaign', '42'],
        )
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]['nm_id'] == 555
        assert parsed[0]['combined'] == 120
        assert parsed[0]['search'] == 200
        assert parsed[0]['recommendation'] == 250


class TestBidGetItems:
    """Tests for the 'bid get-items' command."""

    @patch(FACTORY_PATH)
    def test_bid_get_items_json(self, mock_factory: MagicMock) -> None:
        """JSON output exposes per-item search/recommendations bids."""
        svc = MagicMock()
        svc.get_item_bids.return_value = [_make_current_bid()]
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['--json', 'bid', 'get-items', '--campaign', '42'],
        )
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]['nm_id'] == 555
        assert parsed[0]['search'] == 180
        assert parsed[0]['recommendations'] == 220

BID_WRITE_FACTORY = 'wb.services._factory.create_bid_service'
AUDIT_FACTORY = 'wb.services._factory.create_audit_logger'


def _ok_mutation_result():
    from wb.domain.models import MutationResult
    return MutationResult(success=True, action='set bid', target_id='10', message='Done')


def _dry_mutation_result():
    from wb.domain.models import MutationResult
    return MutationResult(success=True, action='set bid', target_id='10', dry_run=True, message='Would do')


@pytest.fixture()
def mock_audit():
    with patch(AUDIT_FACTORY) as m:
        m.return_value = MagicMock()
        yield m


class TestBidSetItemsInline:
    """Tests for 'bid set-items' with --bids inline JSON option."""

    @patch(BID_WRITE_FACTORY)
    def test_inline_bids_works(self, mock_factory, mock_audit, tmp_path):
        svc = MagicMock()
        svc.set_item_bids.return_value = [_ok_mutation_result()]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'bid', 'set-items',
            '--campaign', '10',
            '--bids', '[{"nm_id": 123, "bid_kopecks": 450}]',
            '--yes',
        ])
        assert result.exit_code == 0
        svc.set_item_bids.assert_called_once()

    @patch(BID_WRITE_FACTORY)
    def test_file_option_still_works(self, mock_factory, mock_audit, tmp_path):
        svc = MagicMock()
        svc.set_item_bids.return_value = [_ok_mutation_result()]
        mock_factory.return_value = svc

        bid_file = tmp_path / 'bids.json'
        bid_file.write_text(json.dumps([{'nm_id': 1, 'bid_kopecks': 100}]))

        result = runner.invoke(app, [
            'bid', 'set-items',
            '--campaign', '10',
            '--file', str(bid_file),
            '--yes',
        ])
        assert result.exit_code == 0

    def test_neither_file_nor_bids_fails(self):
        result = runner.invoke(app, [
            'bid', 'set-items', '--campaign', '10', '--yes',
        ])
        assert result.exit_code != 0

    def test_both_file_and_bids_fails(self, tmp_path):
        bid_file = tmp_path / 'bids.json'
        bid_file.write_text(json.dumps([{'nm_id': 1, 'bid_kopecks': 100}]))

        result = runner.invoke(app, [
            'bid', 'set-items',
            '--campaign', '10',
            '--file', str(bid_file),
            '--bids', '[{"nm_id": 1, "bid_kopecks": 100}]',
            '--yes',
        ])
        assert result.exit_code != 0

    def test_invalid_inline_json_fails(self):
        result = runner.invoke(app, [
            'bid', 'set-items',
            '--campaign', '10',
            '--bids', 'not valid json',
        ])
        assert result.exit_code != 0

    @patch(BID_WRITE_FACTORY)
    def test_inline_bids_dry_run(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.set_item_bids.return_value = [_dry_mutation_result()]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'bid', 'set-items',
            '--campaign', '10',
            '--bids', '[{"nm_id": 1, "bid_kopecks": 100}]',
            '--dry-run', '--yes',
        ])
        assert result.exit_code == 0
        svc.set_item_bids.assert_called_once()
        call_kwargs = svc.set_item_bids.call_args
        assert call_kwargs[1].get('dry_run') is True or call_kwargs[0][2] is True

    @patch(BID_WRITE_FACTORY)
    def test_inline_bids_json_output(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.set_item_bids.return_value = [_ok_mutation_result()]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'bid', 'set-items',
            '--campaign', '10',
            '--bids', '[{"nm_id": 1, "bid_kopecks": 100}]',
            '--yes',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]['success'] is True

    def test_file_not_found_fails(self):
        result = runner.invoke(app, [
            'bid', 'set-items',
            '--campaign', '10',
            '--file', '/nonexistent/path/bids.json',
        ])
        assert result.exit_code != 0
