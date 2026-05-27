"""
SSE event manager — a simple pub/sub system keyed by analysis_id.

Each subscriber gets an asyncio.Queue. The publisher pushes events
to all subscribers for a given analysis_id. On client disconnect
the subscriber calls ``unsubscribe`` to clean up.
"""

import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class SSEEventManager:
    """Manages pub/sub of SSE events keyed by analysis_id."""

    def __init__(self):
        # {analysis_id: set[asyncio.Queue]}
        self._subscribers: dict[str, set[asyncio.Queue]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def subscribe(self, analysis_id: str) -> asyncio.Queue:
        """Register a new subscriber queue for the given analysis.

        Returns the queue the caller should wait on.
        """
        queue: asyncio.Queue = asyncio.Queue()
        if analysis_id not in self._subscribers:
            self._subscribers[analysis_id] = set()
        self._subscribers[analysis_id].add(queue)
        logger.debug(
            "SSE subscriber added for %s (total: %d)",
            analysis_id,
            len(self._subscribers[analysis_id]),
        )
        return queue

    def unsubscribe(self, analysis_id: str, queue: asyncio.Queue) -> None:
        """Remove a subscriber queue."""
        subs = self._subscribers.get(analysis_id)
        if subs:
            subs.discard(queue)
            if not subs:
                del self._subscribers[analysis_id]
            logger.debug("SSE subscriber removed for %s", analysis_id)

    def publish(self, analysis_id: str, event_type: str, data: dict) -> None:
        """Push an event to all subscribers of *analysis_id*.

        This is a synchronous call — the caller (the background task)
        doesn't await; the event is put on each subscriber's queue
        immediately.
        """
        subs = self._subscribers.get(analysis_id)
        if not subs:
            return
        payload = {
            "event": event_type,
            "data": data,
        }
        encoded = json.dumps(payload)
        for queue in subs:
            try:
                queue.put_nowait(encoded)
            except asyncio.QueueFull:
                logger.warning("SSE queue full for %s — dropping event", analysis_id)

    def subscriber_count(self, analysis_id: str) -> int:
        """Return the number of subscribers for an analysis."""
        subs = self._subscribers.get(analysis_id)
        return len(subs) if subs else 0


# Singleton
_event_manager: SSEEventManager | None = None


def get_event_manager() -> SSEEventManager:
    """Return the singleton SSEEventManager instance."""
    global _event_manager
    if _event_manager is None:
        _event_manager = SSEEventManager()
    return _event_manager
