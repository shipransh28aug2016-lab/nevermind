"""In-process event bus with SSE fan-out.

Every meaningful runtime occurrence becomes an event. Subscribers (the browser
via SSE, audit log via DB writer) receive structured events in order.
"""
from __future__ import annotations

import json
import queue
import threading
import time
from typing import Any, Callable, Dict, List, Optional


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: List[queue.Queue] = []
        self._history: List[Dict[str, Any]] = []
        self._listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._seq = 0

    def publish(self, etype: str, payload: Dict[str, Any], task_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            self._seq += 1
            event = {
                "seq": self._seq,
                "type": etype,
                "task_id": task_id,
                "ts": round(time.time(), 3),
                "payload": payload,
            }
            self._history.append(event)
            if len(self._history) > 800:
                self._history = self._history[-800:]
            subs = list(self._subscribers)
            listeners = list(self._listeners)
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass
        for fn in listeners:
            try:
                fn(event)
            except Exception:
                pass
        return event

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=1000)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def add_listener(self, fn: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            self._listeners.append(fn)

    def history(self, task_id: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._history)
        if task_id:
            items = [e for e in items if e.get("task_id") == task_id]
        return items[-limit:]


BUS = EventBus()
