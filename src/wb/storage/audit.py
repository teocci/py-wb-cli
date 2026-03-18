"""Audit logging for WB CLI mutating operations."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from wb.core.constants import AUDIT_LOG_FILE

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AuditEntry:
    """A single audit log record.

    Attributes:
        timestamp: ISO timestamp of the action.
        profile: Profile name used.
        command: CLI command invoked.
        target_id: Campaign or object ID affected.
        payload: Request payload or mutation intent.
        response_summary: Brief response info.
        retry_count: Number of retries needed.
        result: Final result status (success/failure).
    """

    timestamp: str
    profile: str
    command: str
    target_id: str | None = None
    payload: dict | None = None
    response_summary: str | None = None
    retry_count: int = 0
    result: str = 'success'

    def to_json_line(self) -> str:
        """Serialize to a single JSON line."""
        return json.dumps(asdict(self), ensure_ascii=False)


class AuditLogger:
    """Append-only audit logger writing to a JSONL file.

    Attributes:
        config_dir: Directory containing the audit log file.
    """

    def __init__(self, config_dir: Path) -> None:
        self._config_dir = config_dir
        self._log_path = config_dir / AUDIT_LOG_FILE

    def log(
            self,
            profile: str,
            command: str,
            *,
            target_id: str | None = None,
            payload: dict | None = None,
            response_summary: str | None = None,
            retry_count: int = 0,
            result: str = 'success',
    ) -> None:
        """Append an audit entry.

        Args:
            profile: Active profile name.
            command: CLI command string.
            target_id: ID of affected object.
            payload: Request data sent.
            response_summary: Brief response info.
            retry_count: Number of retries performed.
            result: Outcome description.
        """
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            profile=profile,
            command=command,
            target_id=target_id,
            payload=payload,
            response_summary=response_summary,
            retry_count=retry_count,
            result=result,
        )
        self._write_entry(entry)

    def _write_entry(self, entry: AuditEntry) -> None:
        """Write a single entry to the audit log."""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._log_path, 'a', encoding='utf-8') as f:
                f.write(entry.to_json_line() + '\n')
        except OSError as exc:
            logger.error('Failed to write audit log: %s', exc)

    def read_entries(self, limit: int = 50) -> list[AuditEntry]:
        """Read the most recent audit entries.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of AuditEntry objects, most recent last.
        """
        if not self._log_path.exists():
            return []
        entries = []
        try:
            with open(self._log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        entries.append(AuditEntry(**data))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error('Failed to read audit log: %s', exc)
            return []
        return entries[-limit:]
