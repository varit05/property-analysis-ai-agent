"""
AnalysisStore — Async JSON file-backed storage for analysis records.

Thread-safe via asyncio.Lock. Auto-creates the data directory and
initialises the file with an empty list on first access.
"""

import json
import logging
from pathlib import Path

from server.core.config import settings

logger = logging.getLogger(__name__)


class AnalysisStore:
    """Persistent, async-safe storage for analysis records backed by a JSON file."""

    def __init__(self, file_path: str | None = None):
        self._file_path = Path(file_path or settings.ANALYSES_FILE)
        self._lock = None  # asyncio.Lock — lazy initialised
        self._ensure_file()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _ensure_file(self) -> None:
        """Create the data directory and JSON file if they don't exist."""
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._file_path.exists():
            self._file_path.write_text("[]", encoding="utf-8")
            logger.info("Created analyses file: %s", self._file_path)

    async def _get_lock(self):
        """Lazy-initialise the asyncio lock (cannot be done at __init__)."""
        if self._lock is None:
            import asyncio

            self._lock = asyncio.Lock()
        return self._lock

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    async def _load_all(self) -> list[dict]:
        """Read and return all records from the JSON file."""
        raw = self._file_path.read_text(encoding="utf-8")
        if not raw.strip():
            return []
        return json.loads(raw)

    async def _save_all(self, records: list[dict]) -> None:
        """Write all records to the JSON file."""
        self._file_path.write_text(
            json.dumps(records, indent=2, default=str),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get(self, analysis_id: str) -> dict | None:
        """Get a single analysis record by ID, or None if not found."""
        lock = await self._get_lock()
        async with lock:
            records = await self._load_all()
            for record in records:
                if record.get("id") == analysis_id:
                    return record
            return None

    async def upsert(self, analysis_id: str, data: dict) -> dict:
        """Insert or update an analysis record.

        If a record with the given ID already exists it is merged with *data*
        (data wins).  Otherwise a new record is appended.
        Returns the final merged record.
        """
        lock = await self._get_lock()
        async with lock:
            records = await self._load_all()
            for idx, record in enumerate(records):
                if record.get("id") == analysis_id:
                    records[idx].update(data)
                    merged = records[idx]
                    break
            else:
                records.append(data)
                merged = data

            await self._save_all(records)
            return merged

    async def list(
        self,
        query_filter: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[dict], int]:
        """List analysis records with optional query-text filter and pagination.

        Returns (items, total_count).
        """
        lock = await self._get_lock()
        async with lock:
            records = await self._load_all()

        if query_filter:
            q = query_filter.lower()
            records = [r for r in records if q in r.get("query", "").lower()]

        total = len(records)
        paginated = records[skip : skip + limit]
        return paginated, total

    async def delete(self, analysis_id: str) -> bool:
        """Delete an analysis record by ID. Returns True if deleted."""
        lock = await self._get_lock()
        async with lock:
            records = await self._load_all()
            new_records = [r for r in records if r.get("id") != analysis_id]
            if len(new_records) == len(records):
                return False
            await self._save_all(new_records)
            return True


# Singleton store instance (lazy-initialised by the service)
_store: AnalysisStore | None = None


async def get_store() -> AnalysisStore:
    """Return the singleton AnalysisStore instance."""
    global _store
    if _store is None:
        _store = AnalysisStore()
    return _store
