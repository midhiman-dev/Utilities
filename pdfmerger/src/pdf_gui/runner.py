from __future__ import annotations

import io
import threading
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from queue import Empty, Queue
from typing import Callable, Optional


@dataclass
class Event:
    kind: str  # start|stdout|stderr|exit|error
    payload: str


class _QueueWriter(io.TextIOBase):
    def __init__(self, events: Queue[Event], kind: str) -> None:
        self.events = events
        self.kind = kind
        self._buf = ""

    def write(self, s: str) -> int:
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self.events.put(Event(self.kind, line))
        return len(s)

    def flush(self) -> None:
        if self._buf:
            self.events.put(Event(self.kind, self._buf))
            self._buf = ""


class ProcessRunner:
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self.events: Queue[Event] = Queue()
        self._running = False
        self._cancel_requested = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self, task_name: str, task_fn: Callable[[], int]) -> None:
        if self.is_running:
            raise RuntimeError("A task is already running")

        self.events.put(Event("start", task_name))
        self._cancel_requested = False
        self._running = True

        self._thread = threading.Thread(target=self._run, args=(task_fn,), daemon=True)
        self._thread.start()

    def _run(self, task_fn: Callable[[], int]) -> None:
        out_writer = _QueueWriter(self.events, "stdout")
        err_writer = _QueueWriter(self.events, "stderr")
        try:
            with redirect_stdout(out_writer), redirect_stderr(err_writer):
                code = int(task_fn())
        except Exception as exc:  # pylint: disable=broad-except
            details = traceback.format_exc()
            self.events.put(Event("error", f"{exc}\n{details}"))
            self._running = False
            return
        finally:
            out_writer.flush()
            err_writer.flush()
            self._running = False
        self.events.put(Event("exit", str(code)))

    def cancel(self) -> None:
        if not self.is_running:
            return
        self._cancel_requested = True
        self.events.put(
            Event(
                "stderr",
                "Cancellation is not available in in-process mode for the current task. Wait for completion.",
            )
        )

    def drain_events(self) -> list[Event]:
        drained: list[Event] = []
        while True:
            try:
                drained.append(self.events.get_nowait())
            except Empty:
                break
        return drained
