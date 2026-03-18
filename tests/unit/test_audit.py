"""Tests for wb.storage.audit — AuditEntry and AuditLogger."""

import json

import pytest

from wb.storage.audit import AuditEntry, AuditLogger


# ── AuditEntry ────────────────────────────────────────────────────────


class TestAuditEntry:
    """Tests for the AuditEntry dataclass."""

    @pytest.fixture()
    def sample_entry(self) -> AuditEntry:
        """A fully-populated audit entry for reuse."""
        return AuditEntry(
            timestamp='2025-06-15T12:00:00+00:00',
            profile='seller-1',
            command='campaign pause',
            target_id='camp-42',
            payload={'status': 'paused'},
            response_summary='200 OK',
            retry_count=1,
            result='success',
        )

    def test_to_json_line_valid_json(self, sample_entry):
        """to_json_line produces a string that parses as valid JSON."""
        line = sample_entry.to_json_line()
        parsed = json.loads(line)
        assert parsed['profile'] == 'seller-1'
        assert parsed['command'] == 'campaign pause'

    def test_to_json_line_is_single_line(self, sample_entry):
        """to_json_line output contains no embedded newlines."""
        line = sample_entry.to_json_line()
        assert '\n' not in line

    def test_roundtrip_through_json(self, sample_entry):
        """AuditEntry survives serialization and deserialization."""
        line = sample_entry.to_json_line()
        data = json.loads(line)
        restored = AuditEntry(**data)

        assert restored.timestamp == sample_entry.timestamp
        assert restored.profile == sample_entry.profile
        assert restored.command == sample_entry.command
        assert restored.target_id == sample_entry.target_id
        assert restored.payload == sample_entry.payload
        assert restored.response_summary == sample_entry.response_summary
        assert restored.retry_count == sample_entry.retry_count
        assert restored.result == sample_entry.result

    def test_defaults(self):
        """AuditEntry defaults target_id, payload, etc. to sensible values."""
        entry = AuditEntry(
            timestamp='2025-01-01T00:00:00+00:00',
            profile='p',
            command='cmd',
        )
        assert entry.target_id is None
        assert entry.payload is None
        assert entry.response_summary is None
        assert entry.retry_count == 0
        assert entry.result == 'success'


# ── AuditLogger ───────────────────────────────────────────────────────


class TestAuditLogger:
    """Tests for the AuditLogger file-based logger."""

    def test_log_writes_entry_to_file(self, tmp_path):
        """log() appends a JSONL line to the audit file."""
        logger = AuditLogger(tmp_path)
        logger.log('seller-1', 'campaign list')

        log_file = tmp_path / 'audit.jsonl'
        assert log_file.exists()

        lines = log_file.read_text(encoding='utf-8').strip().splitlines()
        assert len(lines) == 1

        parsed = json.loads(lines[0])
        assert parsed['profile'] == 'seller-1'
        assert parsed['command'] == 'campaign list'

    def test_log_appends_multiple_entries(self, tmp_path):
        """Successive log() calls append separate lines."""
        logger = AuditLogger(tmp_path)
        logger.log('p', 'cmd-a')
        logger.log('p', 'cmd-b')
        logger.log('p', 'cmd-c')

        log_file = tmp_path / 'audit.jsonl'
        lines = log_file.read_text(encoding='utf-8').strip().splitlines()
        assert len(lines) == 3

    def test_log_with_all_fields(self, tmp_path):
        """log() correctly stores optional fields."""
        logger = AuditLogger(tmp_path)
        logger.log(
            'seller-1',
            'bid update',
            target_id='camp-99',
            payload={'bid': 150},
            response_summary='200 OK',
            retry_count=2,
            result='success',
        )

        entries = logger.read_entries()
        assert len(entries) == 1
        entry = entries[0]
        assert entry.target_id == 'camp-99'
        assert entry.payload == {'bid': 150}
        assert entry.retry_count == 2

    def test_read_entries_returns_what_was_written(self, tmp_path):
        """read_entries returns AuditEntry objects matching what was logged."""
        logger = AuditLogger(tmp_path)
        logger.log('p1', 'cmd-1')
        logger.log('p2', 'cmd-2')

        entries = logger.read_entries()
        assert len(entries) == 2
        assert entries[0].profile == 'p1'
        assert entries[1].profile == 'p2'

    @pytest.mark.parametrize(
        'total, limit, expected_count',
        [
            (10, 5, 5),
            (3, 10, 3),
            (5, 5, 5),
            (0, 5, 0),
        ],
        ids=['limit-less-than-total', 'limit-more-than-total', 'limit-equals-total', 'empty'],
    )
    def test_read_entries_respects_limit(self, tmp_path, total, limit, expected_count):
        """read_entries returns at most `limit` entries (most recent)."""
        logger = AuditLogger(tmp_path)
        for i in range(total):
            logger.log('p', f'cmd-{i}')

        entries = logger.read_entries(limit=limit)
        assert len(entries) == expected_count

    def test_read_entries_returns_most_recent_when_limited(self, tmp_path):
        """When limited, read_entries returns the last (most recent) entries."""
        logger = AuditLogger(tmp_path)
        for i in range(10):
            logger.log('p', f'cmd-{i}')

        entries = logger.read_entries(limit=3)
        commands = [e.command for e in entries]
        assert commands == ['cmd-7', 'cmd-8', 'cmd-9']

    def test_creates_config_dir_if_missing(self, tmp_path):
        """AuditLogger creates the config directory on first write."""
        nested = tmp_path / 'deep' / 'nested'
        logger = AuditLogger(nested)
        logger.log('p', 'cmd')

        assert (nested / 'audit.jsonl').exists()

    def test_read_from_nonexistent_log_returns_empty(self, tmp_path):
        """Reading when no log file exists returns an empty list."""
        logger = AuditLogger(tmp_path)
        entries = logger.read_entries()
        assert entries == []

    def test_read_from_empty_file_returns_empty(self, tmp_path):
        """Reading an empty log file returns an empty list."""
        log_file = tmp_path / 'audit.jsonl'
        log_file.write_text('', encoding='utf-8')

        logger = AuditLogger(tmp_path)
        entries = logger.read_entries()
        assert entries == []

    def test_log_entry_has_timestamp(self, tmp_path):
        """Each logged entry automatically receives a timestamp."""
        logger = AuditLogger(tmp_path)
        logger.log('p', 'cmd')

        entries = logger.read_entries()
        assert entries[0].timestamp is not None
        assert len(entries[0].timestamp) > 0
