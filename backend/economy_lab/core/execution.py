"""Cooperative execution controls shared by synchronous and background runs."""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event
from time import monotonic
from typing import Callable


class SimulationExecutionError(RuntimeError):
    """Base class for controlled job termination."""


class SimulationCancelledError(SimulationExecutionError):
    """Raised at a safe checkpoint after cancellation was requested."""


class SimulationTimeoutError(SimulationExecutionError):
    """Raised at a safe checkpoint after the job deadline expired."""


ProgressCallback = Callable[[str, float, int, int], None]
CancellationProbe = Callable[[], bool]


@dataclass(slots=True)
class SimulationExecutionControl:
    """Deadline, cancellation and monotonic progress contract.

    Economy Zero checks this control between monthly steps. External subprocess
    calls additionally receive the remaining deadline as their own hard
    timeout. Python threads are never force-killed because that could leave the
    ledger or SQLite transaction in an unknown state.
    """

    timeout_seconds: float | None = None
    cancel_event: Event = field(default_factory=Event)
    cancellation_probe: CancellationProbe | None = None
    progress_callback: ProgressCallback | None = None
    started_monotonic: float = field(default_factory=monotonic)
    _last_progress: float = 0.0

    @property
    def deadline_monotonic(self) -> float | None:
        if self.timeout_seconds is None:
            return None
        return self.started_monotonic + max(0.0, float(self.timeout_seconds))

    def cancellation_requested(self) -> bool:
        return self.cancel_event.is_set() or bool(
            self.cancellation_probe and self.cancellation_probe()
        )

    def checkpoint(
        self,
        stage: str,
        *,
        completed_steps: int = 0,
        total_steps: int = 1,
        progress: float | None = None,
    ) -> None:
        if self.cancellation_requested():
            raise SimulationCancelledError("Simulation job cancellation requested")
        deadline = self.deadline_monotonic
        if deadline is not None and monotonic() >= deadline:
            raise SimulationTimeoutError("Simulation job timeout exceeded")

        total = max(1, int(total_steps))
        completed = max(0, min(int(completed_steps), total))
        calculated = 100.0 * completed / total if progress is None else float(progress)
        calculated = max(self._last_progress, min(100.0, max(0.0, calculated)))
        self._last_progress = calculated
        if self.progress_callback is not None:
            self.progress_callback(stage, calculated, completed, total)

    def remaining_seconds(self, default: float) -> float:
        """Return a positive hard timeout bounded by the job deadline."""

        self.checkpoint("external-engine", progress=self._last_progress)
        deadline = self.deadline_monotonic
        if deadline is None:
            return max(0.1, float(default))
        return max(0.1, min(float(default), deadline - monotonic()))
