import asyncio
from typing import AsyncGenerator, Dict, List, Optional

_DISCONNECT = object()


def _format_event(event_type: str, data: Optional[str] = None) -> str:
    d = data if data is not None else ""
    return f"event: {event_type}\ndata: {d}\n\n"


class SSEManager:
    def __init__(self):
        self._connections: Dict[str, List[asyncio.Queue]] = {}

    def connect(self, installation_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._connections.setdefault(installation_id, []).append(q)
        return q

    def disconnect(self, installation_id: str, queue: asyncio.Queue) -> None:
        queues = self._connections.get(installation_id, [])
        self._connections[installation_id] = [q for q in queues if q is not queue]
        if not self._connections[installation_id]:
            self._connections.pop(installation_id, None)

    def notify(self, installation_id: str, event_type: str, data: Optional[str] = None) -> None:
        chunk = _format_event(event_type, data)
        for q in self._connections.get(installation_id, []):
            try:
                q.put_nowait(chunk)
            except asyncio.QueueFull:
                print(f"[SSE] Queue full for {installation_id}, dropping event")

    def notify_many(self, installation_ids: List[str], event_type: str, data: Optional[str] = None) -> None:
        for iid in installation_ids:
            self.notify(iid, event_type, data)

    def active_connections(self) -> Dict[str, int]:
        return {k: len(v) for k, v in self._connections.items() if v}

    async def event_generator(
        self, installation_id: str, queue: asyncio.Queue, heartbeat_interval: float = 30.0
    ) -> AsyncGenerator[str, None]:
        while True:
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
                if chunk is _DISCONNECT:
                    return
                yield chunk
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"


sse_manager = SSEManager()
