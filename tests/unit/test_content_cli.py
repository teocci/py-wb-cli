"""Tests for the ``wb content`` CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from wb.cli.app import app
from wb.domain.content import (
    STATUS_CHANGED,
    STATUS_TOO_LONG,
    CardUpdateResult,
    ProductCard,
)

runner = CliRunner()

CONTENT_FACTORY = 'wb.services._factory.create_content_service'


def _card(nm_id: int = 1, description: str = 'desc') -> ProductCard:
    return ProductCard(
        nm_id=nm_id, vendor_code=f'vc{nm_id}', brand='B', title='Title',
        description=description,
    )


class TestHelp:
    def test_root(self):
        result = runner.invoke(app, ['content', '--help'])
        assert result.exit_code == 0
        for sub in ('list', 'get', 'export', 'apply', 'set-description'):
            assert sub in result.output


class TestList:
    @patch(CONTENT_FACTORY)
    def test_json_output(self, mock_factory):
        svc = MagicMock()
        svc.list_cards.return_value = [_card(1, 'hello')]
        mock_factory.return_value = svc

        result = runner.invoke(app, ['--json', 'content', 'list'])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data[0]['nmID'] == 1
        assert data[0]['descriptionLength'] == 5

    @patch(CONTENT_FACTORY)
    def test_table_output(self, mock_factory):
        svc = MagicMock()
        svc.list_cards.return_value = [_card(7, 'desc')]
        mock_factory.return_value = svc

        result = runner.invoke(app, ['content', 'list'])
        assert result.exit_code == 0, result.output
        assert '7' in result.output


class TestGet:
    @patch(CONTENT_FACTORY)
    def test_plain_text_prints_description(self, mock_factory):
        svc = MagicMock()
        svc.get_card.return_value = _card(1, 'the full description')
        mock_factory.return_value = svc

        result = runner.invoke(app, ['content', 'get', '--nm', '1'])
        assert result.exit_code == 0, result.output
        assert 'the full description' in result.output

    @patch(CONTENT_FACTORY)
    def test_not_found_exits_nonzero(self, mock_factory):
        svc = MagicMock()
        svc.get_card.return_value = None
        mock_factory.return_value = svc

        result = runner.invoke(app, ['content', 'get', '--nm', '999'])
        assert result.exit_code != 0


class TestExport:
    @patch(CONTENT_FACTORY)
    def test_writes_file(self, mock_factory, tmp_path):
        svc = MagicMock()
        svc.export_descriptions.return_value = [
            {'nmID': 1, 'vendorCode': 'vc1', 'title': 'T', 'description': 'd'},
        ]
        mock_factory.return_value = svc
        out = tmp_path / 'desc.json'

        result = runner.invoke(app, ['content', 'export', '--out', str(out)])
        assert result.exit_code == 0, result.output
        written = json.loads(out.read_text(encoding='utf-8'))
        assert written[0]['nmID'] == 1


class TestApply:
    @patch(CONTENT_FACTORY)
    def test_dry_run_passes_flag_and_does_not_prompt(self, mock_factory, tmp_path):
        svc = MagicMock()
        svc.apply_updates.return_value = (
            [CardUpdateResult(1, 'vc1', 3, 8, STATUS_CHANGED)], [],
        )
        mock_factory.return_value = svc
        edit = tmp_path / 'edit.json'
        edit.write_text(json.dumps([{'nmID': 1, 'description': 'new text'}]), encoding='utf-8')

        result = runner.invoke(app, ['--json', 'content', 'apply', '--file', str(edit), '--dry-run'])
        assert result.exit_code == 0, result.output
        assert svc.apply_updates.call_args.kwargs['dry_run'] is True
        data = json.loads(result.output)
        assert data['dryRun'] is True
        assert data['results'][0]['status'] == STATUS_CHANGED

    @patch(CONTENT_FACTORY)
    def test_apply_writes_with_yes(self, mock_factory, tmp_path):
        svc = MagicMock()
        svc.apply_updates.return_value = (
            [CardUpdateResult(1, 'vc1', 3, 8, STATUS_CHANGED)], [],
        )
        mock_factory.return_value = svc
        edit = tmp_path / 'edit.json'
        edit.write_text(json.dumps([{'nmID': 1, 'description': 'new text'}]), encoding='utf-8')

        result = runner.invoke(app, ['content', 'apply', '--file', str(edit), '--yes'])
        assert result.exit_code == 0, result.output
        assert svc.apply_updates.call_args.kwargs['dry_run'] is False

    @patch(CONTENT_FACTORY)
    def test_errors_cause_nonzero_exit(self, mock_factory, tmp_path):
        svc = MagicMock()
        svc.apply_updates.return_value = (
            [CardUpdateResult(1, 'vc1', 3, 8, STATUS_CHANGED)],
            ['nmID 1 (vc1): bad description'],
        )
        mock_factory.return_value = svc
        edit = tmp_path / 'edit.json'
        edit.write_text(json.dumps([{'nmID': 1, 'description': 'new'}]), encoding='utf-8')

        result = runner.invoke(app, ['content', 'apply', '--file', str(edit), '--yes'])
        assert result.exit_code != 0

    def test_malformed_file_is_validation_error(self, tmp_path):
        edit = tmp_path / 'bad.json'
        edit.write_text(json.dumps({'not': 'a list'}), encoding='utf-8')
        with patch(CONTENT_FACTORY) as mock_factory:
            mock_factory.return_value = MagicMock()
            result = runner.invoke(app, ['content', 'apply', '--file', str(edit), '--yes'])
        assert result.exit_code != 0


class TestSetDescription:
    @patch(CONTENT_FACTORY)
    def test_text_dry_run(self, mock_factory):
        svc = MagicMock()
        svc.set_description.return_value = (CardUpdateResult(1, 'vc1', 3, 4, STATUS_CHANGED), [])
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'content', 'set-description', '--nm', '1', '--text', 'new!', '--dry-run',
        ])
        assert result.exit_code == 0, result.output
        assert svc.set_description.call_args.kwargs['dry_run'] is True

    @patch(CONTENT_FACTORY)
    def test_requires_exactly_one_source(self, mock_factory):
        mock_factory.return_value = MagicMock()
        # neither --text nor --file
        result = runner.invoke(app, ['content', 'set-description', '--nm', '1', '--yes'])
        assert result.exit_code != 0

    @patch(CONTENT_FACTORY)
    def test_reads_from_file(self, mock_factory, tmp_path):
        svc = MagicMock()
        svc.set_description.return_value = (CardUpdateResult(1, 'vc1', 3, 5, STATUS_CHANGED), [])
        mock_factory.return_value = svc
        desc = tmp_path / 'one.txt'
        desc.write_text('fresh', encoding='utf-8')

        result = runner.invoke(app, [
            'content', 'set-description', '--nm', '1', '--file', str(desc), '--dry-run',
        ])
        assert result.exit_code == 0, result.output
        assert svc.set_description.call_args.args[1] == 'fresh'

    @patch(CONTENT_FACTORY)
    def test_too_long_status_surfaced(self, mock_factory):
        svc = MagicMock()
        svc.set_description.return_value = (CardUpdateResult(1, 'vc1', 3, 6000, STATUS_TOO_LONG), [])
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'content', 'set-description', '--nm', '1', '--text', 'x', '--dry-run',
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data['results'][0]['status'] == STATUS_TOO_LONG
