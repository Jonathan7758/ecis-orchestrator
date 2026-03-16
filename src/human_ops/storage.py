"""
human_ops.storage — Storage backend abstraction and in-memory implementation.

Provides a Protocol-based StorageBackend interface so that production code
can swap between in-memory, Redis, PostgreSQL, or any other backend without
changing business logic.  The MemoryBackend is suitable for unit tests and
local development.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """存储后端抽象接口 — abstract storage backend interface.

    Every backend must implement these five async methods.  The *collection*
    parameter acts as a logical table/namespace, and *key* is a unique
    identifier within that collection.
    """

    async def get(self, collection: str, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single document by key.

        Returns ``None`` when the key does not exist.
        """
        ...

    async def put(self, collection: str, key: str, data: Dict[str, Any]) -> None:
        """Insert or replace a document at *key*."""
        ...

    async def delete(self, collection: str, key: str) -> bool:
        """Delete a document.  Returns ``True`` if the key existed."""
        ...

    async def query(
        self,
        collection: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Return all documents matching *filters*.

        Filter semantics:
        - Exact match:  ``{"role": "cleaner"}``
        - IN list:      ``{"status": ["active", "on_leave"]}``
        - Comparisons:  ``{"hours__gt": 4, "hours__lt": 8}``
          Supported suffixes: ``__gt``, ``__lt``, ``__gte``, ``__lte``
        """
        ...

    async def count(
        self,
        collection: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Return the number of documents matching *filters*."""
        ...


class MemoryBackend:
    """内存存储后端 — 用于测试和开发.

    An in-memory implementation of :class:`StorageBackend` backed by plain
    Python dicts.  Data is deep-copied on read/write so callers cannot
    accidentally mutate the store.
    """

    def __init__(self) -> None:
        # {collection_name: {key: dict_document}}
        self._store: Dict[str, Dict[str, Dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Core CRUD
    # ------------------------------------------------------------------

    async def get(self, collection: str, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single document by key, or ``None`` if missing."""
        bucket = self._store.get(collection)
        if bucket is None:
            return None
        doc = bucket.get(key)
        if doc is None:
            return None
        return copy.deepcopy(doc)

    async def put(self, collection: str, key: str, data: Dict[str, Any]) -> None:
        """Insert or replace a document at *key*."""
        if collection not in self._store:
            self._store[collection] = {}
        self._store[collection][key] = copy.deepcopy(data)

    async def delete(self, collection: str, key: str) -> bool:
        """Delete a document.  Returns ``True`` if the key existed."""
        bucket = self._store.get(collection)
        if bucket is None or key not in bucket:
            return False
        del bucket[key]
        return True

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def query(
        self,
        collection: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Return all documents matching *filters*.

        Filter semantics supported:
        - **Exact match**: ``{"role": "cleaner"}`` matches docs where
          ``doc["role"] == "cleaner"``.
        - **IN list**: ``{"status": ["active", "on_leave"]}`` matches docs
          where ``doc["status"]`` is in the given list.
        - **Comparison operators** via suffixed keys:
          - ``field__gt``  -> ``doc[field] > value``
          - ``field__lt``  -> ``doc[field] < value``
          - ``field__gte`` -> ``doc[field] >= value``
          - ``field__lte`` -> ``doc[field] <= value``

        Returns an empty list when the collection does not exist.
        """
        bucket = self._store.get(collection)
        if bucket is None:
            return []

        if not filters:
            return [copy.deepcopy(doc) for doc in bucket.values()]

        results: List[Dict[str, Any]] = []
        for doc in bucket.values():
            if self._matches(doc, filters):
                results.append(copy.deepcopy(doc))
        return results

    async def count(
        self,
        collection: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Return the number of documents matching *filters*."""
        docs = await self.query(collection, filters)
        return len(docs)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _matches(doc: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Return ``True`` if *doc* satisfies every clause in *filters*."""
        for raw_key, expected in filters.items():
            # Detect comparison suffixes
            for suffix, op in (
                ("__gte", "_gte"),
                ("__lte", "_lte"),
                ("__gt", "_gt"),
                ("__lt", "_lt"),
            ):
                if raw_key.endswith(suffix):
                    field_name = raw_key[: -len(suffix)]
                    actual = doc.get(field_name)
                    if actual is None:
                        return False
                    if op == "_gt" and not (actual > expected):
                        return False
                    if op == "_lt" and not (actual < expected):
                        return False
                    if op == "_gte" and not (actual >= expected):
                        return False
                    if op == "_lte" and not (actual <= expected):
                        return False
                    break
            else:
                # No suffix — exact or IN match
                actual = doc.get(raw_key)
                if isinstance(expected, list):
                    if actual not in expected:
                        return False
                else:
                    if actual != expected:
                        return False
        return True

    # ------------------------------------------------------------------
    # Convenience / debug helpers
    # ------------------------------------------------------------------

    async def clear(self, collection: Optional[str] = None) -> None:
        """Remove all data.  If *collection* is given, clear only that one."""
        if collection is not None:
            self._store.pop(collection, None)
        else:
            self._store.clear()

    def collection_names(self) -> List[str]:
        """Return the names of all non-empty collections."""
        return [k for k, v in self._store.items() if v]
