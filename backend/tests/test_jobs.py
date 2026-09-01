from __future__ import annotations

from threading import Event
from time import monotonic, sleep

from fastapi.testclient import TestClient

from economy_lab.api import routes
from economy_lab.core.schemas import ScenarioSpec
from economy_lab.core.simulation import run_simulation
from economy_lab.jobs.manager import SimulationJobManager
from economy_lab.main import app
from economy_lab.storage import ProjectStore


TERMINAL = {"completed", "failed", "cancelled"}


def wait_for_job(store: ProjectStore, job_id: str, timeout: float = 3.0):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        item = store.get_job(job_id)
        assert item is not None
        if item["status"] in TERMINAL:
            return item
        sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish")


def demo_spec(name: str = "Job") -> ScenarioSpec:
    return ScenarioSpec(
        name=name, mode="demo", months=2, households=120, firms=8, banks=2
    )


def test_job_store_transitions_and_filters(tmp_path):
    store = ProjectStore(tmp_path / "jobs.sqlite3")
    first = store.create_job(scenario=demo_spec("First"), timeout_seconds=30)
    second = store.create_job(scenario=demo_spec("Second"), timeout_seconds=30)

    assert store.start_job(first["id"]) is True
    assert store.start_job(first["id"]) is False
    assert store.update_job_progress(
        first["id"], stage="simulating", progress=55, current_step=1, total_steps=2
    )
    assert store.update_job_progress(
        first["id"], stage="simulating", progress=25, current_step=1, total_steps=2
    )
    running = store.get_job(first["id"])
    assert running["progress"] == 55
    assert [item["id"] for item in store.list_jobs(status="queued")] == [second["id"]]

    result = run_simulation(demo_spec("First"))
    assert store.complete_job(first["id"], result=result)
    completed = store.get_job(first["id"])
    assert completed["status"] == "completed"
    assert completed["result"]["scenario"] == "First"


def test_manager_completes_project_job_and_saves_run(tmp_path):
    store = ProjectStore(tmp_path / "project-job.sqlite3")
    spec = demo_spec("Persisted job")
    project = store.create_project(name="Project", description="", scenario=spec)
    manager = SimulationJobManager(store, max_workers=1)
    try:
        submitted = manager.submit(spec, project_id=project["id"], timeout_seconds=30)
        completed = wait_for_job(store, submitted["id"])
    finally:
        manager.shutdown()

    assert completed["status"] == "completed"
    assert completed["run_id"] is not None
    run = store.get_run(completed["run_id"])
    assert run["engine_version"] == "2.13.1"
    assert run["manifest"]["seed"] == spec.seed
    assert run["manifest_hash"] is not None


def test_manager_recovers_interrupted_and_reschedules_queued_jobs(tmp_path):
    store = ProjectStore(tmp_path / "recovery.sqlite3")
    interrupted = store.create_job(scenario=demo_spec("Interrupted"), timeout_seconds=30)
    queued = store.create_job(scenario=demo_spec("Queued"), timeout_seconds=30)
    assert store.start_job(interrupted["id"])

    manager = SimulationJobManager(store, max_workers=1)
    try:
        recovered = store.get_job(interrupted["id"])
        completed = wait_for_job(store, queued["id"])
    finally:
        manager.shutdown()

    assert recovered["status"] == "failed"
    assert recovered["error_code"] == "worker_interrupted"
    assert completed["status"] == "completed"


def test_queued_job_can_be_cancelled_without_running(tmp_path):
    store = ProjectStore(tmp_path / "queued-cancel.sqlite3")
    entered = Event()
    release = Event()

    def blocking_runner(spec, *, execution_control):
        entered.set()
        while not release.wait(0.01):
            execution_control.checkpoint("blocked", progress=10)
        return run_simulation(demo_spec(spec.name))

    manager = SimulationJobManager(store, max_workers=1, runner=blocking_runner)
    try:
        first = manager.submit(demo_spec("First"), timeout_seconds=30)
        assert entered.wait(1)
        second = manager.submit(demo_spec("Second"), timeout_seconds=30)
        assert store.get_job(second["id"])["status"] == "queued"
        cancelled = manager.cancel(second["id"])
        assert cancelled["status"] == "cancelled"
        release.set()
        assert wait_for_job(store, first["id"])["status"] == "completed"
    finally:
        release.set()
        manager.shutdown()


def test_running_job_observes_cancellation(tmp_path):
    store = ProjectStore(tmp_path / "running-cancel.sqlite3")
    entered = Event()

    def cancellable_runner(spec, *, execution_control):
        entered.set()
        while True:
            execution_control.checkpoint("simulating", progress=20)
            sleep(0.005)

    manager = SimulationJobManager(store, max_workers=1, runner=cancellable_runner)
    try:
        submitted = manager.submit(demo_spec(), timeout_seconds=30)
        assert entered.wait(1)
        manager.cancel(submitted["id"])
        cancelled = wait_for_job(store, submitted["id"])
    finally:
        manager.shutdown()

    assert cancelled["status"] == "cancelled"
    assert cancelled["cancellation_requested"] is True


def test_job_timeout_becomes_failed_with_timeout_code(tmp_path):
    store = ProjectStore(tmp_path / "timeout.sqlite3")

    def slow_runner(spec, *, execution_control):
        while True:
            execution_control.checkpoint("simulating", progress=30)
            sleep(0.005)

    manager = SimulationJobManager(store, max_workers=1, runner=slow_runner)
    try:
        submitted = manager.submit(demo_spec(), timeout_seconds=0.03)
        failed = wait_for_job(store, submitted["id"])
    finally:
        manager.shutdown()

    assert failed["status"] == "failed"
    assert failed["error_code"] == "timeout"


def test_shutdown_signals_cancellation_instead_of_blocking_on_timeout(tmp_path):
    """Regression guard: shutdown() used to only stop the executor's queue.

    A running job kept executing (and process exit would block on it, since
    ThreadPoolExecutor joins its worker threads at interpreter exit) until it
    hit its own timeout_seconds. shutdown() must set every live cancel event
    first so a job blocked in a checkpoint stops at its next monthly step.
    """
    store = ProjectStore(tmp_path / "shutdown-signal.sqlite3")
    entered = Event()

    def cancellable_runner(spec, *, execution_control):
        entered.set()
        while True:
            execution_control.checkpoint("simulating", progress=20)
            sleep(0.005)

    manager = SimulationJobManager(store, max_workers=1, runner=cancellable_runner)
    submitted = manager.submit(demo_spec(), timeout_seconds=30)
    assert entered.wait(1)

    started = monotonic()
    manager.shutdown(wait=True)
    elapsed = monotonic() - started

    assert elapsed < 5.0, "shutdown() waited near the job's 30s timeout instead of cancelling it"
    finished = wait_for_job(store, submitted["id"])
    assert finished["status"] == "cancelled"


def test_jobs_api_submit_poll_list_and_terminal_cancel(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path / "api-jobs.sqlite3")
    manager = SimulationJobManager(store, max_workers=1)
    monkeypatch.setattr(routes, "_project_store", lambda: store)
    monkeypatch.setattr(routes, "get_job_manager", lambda: manager)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/jobs/simulations",
                json={"scenario": demo_spec("API job").model_dump(mode="json")},
            )
            assert response.status_code == 202
            job_id = response.json()["id"]
            completed = wait_for_job(store, job_id)

            fetched = client.get(f"/api/v1/jobs/{job_id}")
            listed = client.get("/api/v1/jobs", params={"status": "completed"})
            cancelled = client.post(f"/api/v1/jobs/{job_id}/cancel")
    finally:
        manager.shutdown()

    assert completed["status"] == "completed"
    assert fetched.status_code == 200
    assert fetched.json()["result"]["scenario"] == "API job"
    assert any(item["id"] == job_id for item in listed.json())
    assert cancelled.status_code == 409
