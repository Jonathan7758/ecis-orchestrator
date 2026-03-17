"""
F9 Data Backup Service — PostgreSQL daily auto-backup with recovery.

Provides automated backup creation, restoration, listing, and cleanup.
All backup metadata is stored via StorageBackend for consistency.

Usage:
    service = BackupService(config=BackupConfig(...), backend=backend)
    record = await service.create_backup()
    ok = await service.restore_from_backup(record.backup_id)
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from human_ops.storage import StorageBackend

logger = logging.getLogger("ecis.backup")


# =========================================================================
# Data Models (Step 1: dataclass, NOT Pydantic)
# =========================================================================

@dataclass
class BackupConfig:
    """Configuration for the backup service."""
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_database: str = "ecis"
    pg_user: str = "ecis"
    pg_password: str = field(default="", repr=False)
    backup_dir: str = "/var/backups/ecis"
    retention_days: int = 90
    max_backups: int = 100


@dataclass
class BackupRecord:
    """Metadata record for a single backup."""
    backup_id: str = ""
    backup_type: str = "full"          # full / incremental
    status: str = "pending"            # pending / completed / failed / restored
    file_path: str = ""
    file_size_bytes: int = 0
    database: str = ""
    created_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0
    error: Optional[str] = None
    notes: str = ""

    def __post_init__(self):
        if not self.backup_id:
            self.backup_id = str(uuid4())
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
        if self.backup_type not in ("full", "incremental"):
            raise ValueError(f"Invalid backup_type: {self.backup_type}")


# =========================================================================
# F9 BackupService (Step 2: Interface + Step 4: Implementation)
# =========================================================================

class BackupService:
    """V9 F9: PostgreSQL backup and recovery service.

    Manages automated database backups with configurable retention,
    metadata tracking via StorageBackend, and point-in-time recovery.
    """

    COLLECTION = "backup_records"

    def __init__(self, config: BackupConfig, backend: StorageBackend) -> None:
        """Initialize backup service.

        Args:
            config: Database and backup configuration.
            backend: StorageBackend for metadata persistence.
        """
        self._config = config
        self._backend = backend

    async def create_backup(self, backup_type: str = "full",
                            notes: str = "") -> BackupRecord:
        """Create a database backup.

        Args:
            backup_type: 'full' or 'incremental'.
            notes: Optional description for this backup.

        Returns:
            BackupRecord with completion status and metadata.
        """
        record = BackupRecord(
            backup_type=backup_type,
            database=self._config.pg_database,
            notes=notes,
        )

        start_time = datetime.utcnow()
        timestamp = start_time.strftime("%Y%m%d_%H%M%S")
        filename = f"ecis_{self._config.pg_database}_{timestamp}.sql"
        file_path = os.path.join(self._config.backup_dir, filename)
        record.file_path = file_path

        try:
            # Ensure backup directory exists
            os.makedirs(self._config.backup_dir, exist_ok=True)

            # Run pg_dump
            cmd = [
                "pg_dump",
                f"--host={self._config.pg_host}",
                f"--port={self._config.pg_port}",
                f"--username={self._config.pg_user}",
                f"--dbname={self._config.pg_database}",
                "--format=plain",
                f"--file={file_path}",
            ]

            env = os.environ.copy()
            env["PGPASSWORD"] = self._config.pg_password

            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                record.status = "failed"
                record.error = error_msg
                logger.error("Backup failed: %s", error_msg)
            else:
                record.status = "completed"
                if os.path.exists(file_path):
                    record.file_size_bytes = os.path.getsize(file_path)
                logger.info("Backup completed: %s (%d bytes)",
                            file_path, record.file_size_bytes)

        except FileNotFoundError:
            record.status = "failed"
            record.error = "pg_dump not found — is PostgreSQL client installed?"
            logger.error("pg_dump not found")
        except Exception as exc:
            record.status = "failed"
            record.error = str(exc)
            logger.error("Backup error: %s", exc)

        end_time = datetime.utcnow()
        record.completed_at = end_time.isoformat()
        record.duration_seconds = (end_time - start_time).total_seconds()

        # Persist metadata
        await self._backend.put(
            self.COLLECTION, record.backup_id, asdict(record),
        )
        return record

    async def restore_from_backup(self, backup_id: str) -> bool:
        """Restore database from a specific backup.

        Args:
            backup_id: ID of the backup to restore.

        Returns:
            True if restoration succeeded, False otherwise.
        """
        data = await self._backend.get(self.COLLECTION, backup_id)
        if data is None:
            logger.error("Backup record %s not found", backup_id)
            return False

        record = BackupRecord(**data)
        if record.status != "completed":
            logger.error("Cannot restore from %s backup (status: %s)",
                         backup_id, record.status)
            return False

        if not os.path.exists(record.file_path):
            logger.error("Backup file not found: %s", record.file_path)
            return False

        try:
            cmd = [
                "psql",
                f"--host={self._config.pg_host}",
                f"--port={self._config.pg_port}",
                f"--username={self._config.pg_user}",
                f"--dbname={self._config.pg_database}",
                f"--file={record.file_path}",
            ]

            env = os.environ.copy()
            env["PGPASSWORD"] = self._config.pg_password

            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error("Restore failed: %s", stderr.decode().strip())
                return False

            # Update record status
            record.status = "restored"
            await self._backend.put(
                self.COLLECTION, backup_id, asdict(record),
            )
            logger.info("Restore completed from %s", record.file_path)
            return True

        except FileNotFoundError:
            logger.error("psql not found — is PostgreSQL client installed?")
            return False
        except Exception as exc:
            logger.error("Restore error: %s", exc)
            return False

    async def list_backups(self, days: int = 30) -> List[BackupRecord]:
        """List backup records within the specified time range.

        Args:
            days: Number of days to look back.

        Returns:
            List of BackupRecord sorted by creation time (newest first).
        """
        all_records = await self._backend.query(
            self.COLLECTION, {"database": self._config.pg_database},
        )

        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        filtered = [
            BackupRecord(**r) for r in all_records
            if r.get("created_at", "") >= cutoff
        ]
        filtered.sort(key=lambda r: r.created_at, reverse=True)
        return filtered

    async def cleanup_old_backups(self, keep_days: int = 0) -> int:
        """Remove backups older than retention period.

        Args:
            keep_days: Override retention days. Uses config default if 0.

        Returns:
            Number of backups removed.
        """
        retention = keep_days if keep_days > 0 else self._config.retention_days
        cutoff = (datetime.utcnow() - timedelta(days=retention)).isoformat()

        all_records = await self._backend.query(
            self.COLLECTION, {"database": self._config.pg_database},
        )

        removed = 0
        for data in all_records:
            if data.get("created_at", "") < cutoff:
                # Remove file if it exists
                file_path = data.get("file_path", "")
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass

                # Remove metadata record
                await self._backend.delete(
                    self.COLLECTION, data.get("backup_id", ""),
                )
                removed += 1

        if removed > 0:
            logger.info("Cleaned up %d old backups", removed)
        return removed

    async def get_backup(self, backup_id: str) -> Optional[BackupRecord]:
        """Get a specific backup record by ID.

        Args:
            backup_id: The backup record ID.

        Returns:
            BackupRecord if found, None otherwise.
        """
        data = await self._backend.get(self.COLLECTION, backup_id)
        if data is None:
            return None
        return BackupRecord(**data)
