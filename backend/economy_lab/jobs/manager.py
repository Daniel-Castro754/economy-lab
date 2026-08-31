"""Persistent background simulation queue for the local-first API."""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import os
from pathlib import Path
from threading import Event, Lock
from time import perf_counter
from typing import Callable

from economy_lab.core.execution import (
    SimulationCancelledError,
    SimulationTimeoutError,
    SimulationExecutionControl,
)
from economy_lab.core.schemas import ScenarioSpec, SimulationResult
from economy_lab.core.simulation import run_simulation
from economy_lab.engines.dynare_adapter import DynareExecutionError, DynareUnavailableError
from economy_lab.engines.hark_adapter import EngineUnavailableError
from economy_lab.storage import ProjectStore, resolve_database_path


SimulationRunner = Callable[..., SimulationResult]


class SimulationJobManager:
    """Run simulations on bounded worker threads and persist every transition."""

    def __init__(
        self,
        store: ProjectStore,
        *,
        max_workers: int = 2,
        runner: SimulationRunner = run_simulation,
    ):
        self.store = store
        self.runner = runner
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, min(int(max_workers), 16)),
            thread_name_prefix="economy-lab-job",
        )
        self._lock = Lock()
        self._events: dict[str, Event] = {}
        self._futures: dict[str, Future[None]] = {}
        self.store.recover_interrupted_jobs()
        for job_id in self.store.queued_job_ids():
            self._schedule(job_id)

    def submit(
        self,
        scenario: ScenarioSpec,
        *,
        project_id: str | None = None,
        save_scenario: bool = True,
        timeout_seconds: float = 300.0,
    ) -> dict[str, object]:
        item = self.store.create_job(
            scenario=scenario,
            project_id=project_id,
            save_scenario=save_scenario,
            timeout_seconds=timeout_seconds,
        )
        self._schedule(str(item["id"]))
        return item

    def cancel(self, job_id: str) -> dict[str, object] | None:
        item = self.store.request_job_cancel(job_id)
        if item is None:
            return None
        with self._lock:
            event = self._events.get(job_id)
            future = self._futures.get(job_id)
        if event is not None:
            event.set()
        if future is not None:
            future.cancel()
        refreshed = self.store.get_job(job_id)
        return refreshed

    def shutdown(self, *, wait: bool = True) -> None:
        """Stop accepting work and unblock any threads waiting on a checkpoint.

        Setting every live cancel event first makes shutdown prompt: a job
        blocked in ``SimulationExecutionControl.checkpoint`` raises
        ``SimulationCancelledError`` at its next monthly step instead of
        running to completion or to its full timeout. Without this, process
        exit would stall (Python's ``ThreadPoolExecutor`` joins all worker
        threads at interpreter shutdown) for as long as the slowest running
        job's remaining timeout_seconds.
        """
        with self._lock:
            events = list(self._events.values())
        for event in events:
            event.set()
        self._executor.shutdown(wait=wait, cancel_futures=True)

    def _schedule(self, job_id: str) -> None:
        event = Event()
        with self._lock:
            if job_id in self._futures:
                return
            self._events[job_id] = event
            future = self._executor.submit(self._execute, job_id, event)
            self._futures[job_id] = future
            future.add_done_callback(
                lambda completed: self._forget(job_id) if completed.cancelled() else None
            )

    def _execute(self, job_id: str, event: Event) -> None:
        if not self.store.start_job(job_id):
            self._forget(job_id)
            return

        item = self.store.get_job(job_id)
        if item is None:
            self._forget(job_id)
            return
        scenario = ScenarioSpec.model_validate(item["scenario"])
        timeout_seconds = float(item["timeout_seconds"])
        started = perf_counter()

        def progress(stage: str, percent: float, current: int, total: int) -> None:
            self.store.update_job_progress(
                job_id,
                stage=stage,
                progress=percent,
                current_step=current,
                total_steps=total,
            )

        control = SimulationExecutionControl(
            timeout_seconds=timeout_seconds,
            cancel_event=event,
            cancellation_probe=lambda: self.store.cancellation_requested(job_id),
            progress_callback=progress,
        )
        try:
            result = self.runner(scenario, execution_control=control)
            control.checkpoint(
                "persisting",
                completed_steps=scenario.months,
                total_steps=scenario.months,
                progress=99.0,
            )
            run_id = None
            project_id = item["project_id"]
            if project_id is not None:
                run_id = self.store.complete_project_job(
                    job_id,
                    project_id=str(project_id),
                    scenario=scenario,
                    result=result,
                    duration_ms=(perf_counter() - started) * 1000.0,
                    engine_version="2.13.0",
                    save_scenario=bool(item["save_scenario"]),
                )
                if run_id is None:
                    self.store.cancel_job(job_id)
            elif not self.store.complete_job(job_id, result=result, run_id=run_id):
                self.store.cancel_job(job_id)
        except SimulationCancelledError:
            self.store.cancel_job(job_id)
        except SimulationTimeoutError as exc:
            self.store.fail_job(job_id, error_code="timeout", error_message=str(exc))
        except (DynareExecutionError, DynareUnavailableError, EngineUnavailableError) as exc:
            try:
                control.checkpoint("external-engine-failed", progress=control._last_progress)
            except SimulationCancelledError:
                self.store.cancel_job(job_id)
            except SimulationTimeoutError as timeout_exc:
                self.store.fail_job(
                    job_id, error_code="timeout", error_message=str(timeout_exc)
                )
            else:
                self.store.fail_job(
                    job_id, error_code="engine_error", error_message=str(exc)
                )
        except Exception as exc:  # defensive worker boundary; state must never remain running
            if self.store.cancellation_requested(job_id):
                self.store.cancel_job(job_id)
            else:
                self.store.fail_job(
                    job_id,
                    error_code="simulation_error",
                    error_message=f"{type(exc).__name__}: {exc}",
                )
        finally:
            self._forget(job_id)

    def _forget(self, job_id: str) -> None:
        with self._lock:
            self._events.pop(job_id, None)
            self._futures.pop(job_id, None)


_managers: dict[str, SimulationJobManager] = {}
_managers_lock = Lock()


def get_job_manager() -> SimulationJobManager:
    path = Path(resolve_database_path()).resolve()
    key = str(path)
    with _managers_lock:
        manager = _managers.get(key)
        if manager is None:
            workers = int(os.getenv("ECONOMY_LAB_JOB_WORKERS", "2"))
            manager = SimulationJobManager(ProjectStore(path), max_workers=workers)
            _managers[key] = manager
        return manager


def shutdown_all_job_managers(*, wait: bool = False) -> None:
    """Signal cancellation and stop every job manager created in this process.

    Call this from the ASGI shutdown hook and the desktop shutdown callback so
    closing the app does not leave background simulation threads running (or
    block process exit on them) past the request that asked the server to stop.
    """
    with _managers_lock:
        managers = list(_managers.values())
        _managers.clear()
    for manager in managers:
        manager.shutdown(wait=wait)
