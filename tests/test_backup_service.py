"""
F9 Data Backup Service Tests — 15 tests.

Tests backup creation, listing, cleanup, and edge cases.
Uses MemoryBackend (no real PostgreSQL needed).
pg_dump/psql calls are not tested here (they need real DB);
we test the metadata management and logic.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta

import pytest

from backup.backup_service import BackupConfig, BackupRecord, BackupService
from human_ops.storage import MemoryBackend

pytestmark = pytest.mark.asyncio


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def backend():
    return MemoryBackend()


@pytest.fixture
def config(tmp_path):
    return BackupConfig(
        pg_host="localhost",
        pg_port=5432,
        pg_database="ecis_test",
        pg_user="ecis",
        pg_password="test",
        backup_dir=str(tmp_path / "backups"),
        retention_days=30,
    )


@pytest.fixture
def service(config, backend):
    return BackupService(config=config, backend=backend)


# =========================================================================
# BackupRecord model tests
# =========================================================================

class TestBackupRecord:
    """Test BackupRecord dataclass."""

    def test_default_values(self):
        """F9-01: BackupRecord creates with default ID and timestamp."""
        record = BackupRecord()
        assert record.backup_id != ""
        assert record.created_at != ""
        assert record.backup_type == "full"
        assert record.status == "pending"

    def test_invalid_backup_type(self):
        """F9-02: Invalid backup type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid backup_type"):
            BackupRecord(backup_type="partial")

    def test_custom_values(self):
        """F9-03: BackupRecord accepts custom values."""
        record = BackupRecord(
            backup_id="test-123",
            backup_type="incremental",
            database="ecis",
            notes="daily backup",
        )
        assert record.backup_id == "test-123"
        assert record.backup_type == "incremental"
        assert record.notes == "daily backup"


# =========================================================================
# BackupService metadata tests (no pg_dump needed)
# =========================================================================

class TestBackupServiceMetadata:
    """Test backup metadata management via StorageBackend."""

    async def test_list_empty(self, service):
        """F9-04: list_backups returns empty when no backups exist."""
        backups = await service.list_backups()
        assert backups == []

    async def test_get_nonexistent(self, service):
        """F9-05: get_backup returns None for unknown ID."""
        result = await service.get_backup("nonexistent")
        assert result is None

    async def test_store_and_retrieve(self, service, backend):
        """F9-06: Manually stored backup can be retrieved."""
        from dataclasses import asdict
        record = BackupRecord(
            backup_id="manual-1",
            backup_type="full",
            status="completed",
            database="ecis_test",
            file_path="/tmp/backup.sql",
            file_size_bytes=1024,
        )
        await backend.put("backup_records", "manual-1", asdict(record))

        retrieved = await service.get_backup("manual-1")
        assert retrieved is not None
        assert retrieved.backup_id == "manual-1"
        assert retrieved.status == "completed"
        assert retrieved.file_size_bytes == 1024

    async def test_list_filters_by_date(self, service, backend):
        """F9-07: list_backups filters by date range."""
        from dataclasses import asdict

        # Old backup (40 days ago)
        old = BackupRecord(
            backup_id="old-1",
            database="ecis_test",
            created_at=(datetime.utcnow() - timedelta(days=40)).isoformat(),
        )
        await backend.put("backup_records", "old-1", asdict(old))

        # Recent backup
        recent = BackupRecord(
            backup_id="recent-1",
            database="ecis_test",
        )
        await backend.put("backup_records", "recent-1", asdict(recent))

        # Query last 30 days
        results = await service.list_backups(days=30)
        ids = [r.backup_id for r in results]
        assert "recent-1" in ids
        assert "old-1" not in ids

    async def test_list_sorted_newest_first(self, service, backend):
        """F9-08: list_backups returns newest first."""
        from dataclasses import asdict

        for i, offset in enumerate([3, 1, 2]):
            ts = (datetime.utcnow() - timedelta(hours=offset)).isoformat()
            rec = BackupRecord(
                backup_id=f"rec-{i}",
                database="ecis_test",
                created_at=ts,
            )
            await backend.put("backup_records", f"rec-{i}", asdict(rec))

        results = await service.list_backups(days=30)
        times = [r.created_at for r in results]
        assert times == sorted(times, reverse=True)

    async def test_cleanup_removes_old_records(self, service, backend):
        """F9-09: cleanup_old_backups removes expired metadata."""
        from dataclasses import asdict

        # Old backup (100 days ago)
        old = BackupRecord(
            backup_id="expired-1",
            database="ecis_test",
            created_at=(datetime.utcnow() - timedelta(days=100)).isoformat(),
        )
        await backend.put("backup_records", "expired-1", asdict(old))

        # Recent backup
        recent = BackupRecord(
            backup_id="keep-1",
            database="ecis_test",
        )
        await backend.put("backup_records", "keep-1", asdict(recent))

        removed = await service.cleanup_old_backups(keep_days=30)
        assert removed == 1

        # Verify only recent remains
        assert await service.get_backup("expired-1") is None
        assert await service.get_backup("keep-1") is not None

    async def test_cleanup_removes_files(self, service, backend, config):
        """F9-10: cleanup removes actual backup files."""
        from dataclasses import asdict
        import os

        # Create a temporary file simulating a backup
        os.makedirs(config.backup_dir, exist_ok=True)
        fake_file = os.path.join(config.backup_dir, "old.sql")
        with open(fake_file, "w") as f:
            f.write("-- fake backup")

        old = BackupRecord(
            backup_id="file-cleanup-1",
            database="ecis_test",
            file_path=fake_file,
            created_at=(datetime.utcnow() - timedelta(days=100)).isoformat(),
        )
        await backend.put("backup_records", "file-cleanup-1", asdict(old))

        await service.cleanup_old_backups(keep_days=30)
        assert not os.path.exists(fake_file)


# =========================================================================
# Restore validation tests
# =========================================================================

class TestBackupRestore:
    """Test restore logic (without real psql)."""

    async def test_restore_nonexistent_fails(self, service):
        """F9-11: Restore of nonexistent backup returns False."""
        result = await service.restore_from_backup("nonexistent")
        assert result is False

    async def test_restore_failed_backup_rejected(self, service, backend):
        """F9-12: Cannot restore from a failed backup."""
        from dataclasses import asdict
        record = BackupRecord(
            backup_id="failed-1",
            status="failed",
            database="ecis_test",
        )
        await backend.put("backup_records", "failed-1", asdict(record))

        result = await service.restore_from_backup("failed-1")
        assert result is False

    async def test_restore_missing_file_fails(self, service, backend):
        """F9-13: Restore fails if backup file doesn't exist."""
        from dataclasses import asdict
        record = BackupRecord(
            backup_id="no-file-1",
            status="completed",
            database="ecis_test",
            file_path="/nonexistent/path/backup.sql",
        )
        await backend.put("backup_records", "no-file-1", asdict(record))

        result = await service.restore_from_backup("no-file-1")
        assert result is False


# =========================================================================
# Config tests
# =========================================================================

class TestBackupConfig:
    """Test BackupConfig dataclass."""

    def test_default_config(self):
        """F9-14: Default config has sensible values."""
        config = BackupConfig()
        assert config.pg_database == "ecis"
        assert config.retention_days == 90
        assert config.max_backups == 100

    def test_custom_config(self):
        """F9-15: Custom config values are preserved."""
        config = BackupConfig(
            pg_host="db.example.com",
            pg_port=5433,
            pg_database="ecis_prod",
            retention_days=60,
        )
        assert config.pg_host == "db.example.com"
        assert config.pg_port == 5433
        assert config.retention_days == 60
