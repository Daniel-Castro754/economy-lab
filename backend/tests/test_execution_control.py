from threading import Event
from time import sleep

import pytest

from economy_lab.core.execution import (
    SimulationCancelledError,
    SimulationExecutionControl,
    SimulationTimeoutError,
)


def test_execution_control_reports_monotonic_progress():
    updates = []
    control = SimulationExecutionControl(
        progress_callback=lambda stage, progress, current, total: updates.append(
            (stage, progress, current, total)
        )
    )
    control.checkpoint("first", progress=40, completed_steps=4, total_steps=10)
    control.checkpoint("second", progress=20, completed_steps=2, total_steps=10)

    assert [item[1] for item in updates] == [40.0, 40.0]
    assert updates[-1][0] == "second"


def test_execution_control_cancels_at_safe_checkpoint():
    event = Event()
    control = SimulationExecutionControl(cancel_event=event)
    event.set()

    with pytest.raises(SimulationCancelledError):
        control.checkpoint("simulating")


def test_execution_control_enforces_deadline():
    control = SimulationExecutionControl(timeout_seconds=0.01)
    sleep(0.02)

    with pytest.raises(SimulationTimeoutError):
        control.checkpoint("simulating")
