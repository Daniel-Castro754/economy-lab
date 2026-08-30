from economy_lab.core.schemas import BatchExperimentRequest, ScenarioSpec
from economy_lab.experiments import run_batch_experiment
from economy_lab.storage import ProjectStore


def tiny_base() -> ScenarioSpec:
    return ScenarioSpec(months=3, households=120, firms=8, banks=2, seed=11, policy_rate=10.0)


def test_batch_sweeps_axis_and_repetitions():
    response = run_batch_experiment(BatchExperimentRequest(
        base=tiny_base(), axis="policy_rate", values=[8.0, 12.0], repetitions=2
    ))
    assert response.total_runs == 4
    assert [row.axis_value for row in response.aggregates] == [8.0, 12.0]
    assert all(row.runs == 2 for row in response.aggregates)
    assert all(row.all_accounting_balanced for row in response.aggregates)
    assert {p.seed for p in response.runs} == {11, 12}


def test_batch_rejects_invalid_axis_value():
    request = BatchExperimentRequest(base=tiny_base(), axis="income_tax", values=[10.0, 120.0], repetitions=1)
    try:
        run_batch_experiment(request)
    except ValueError as exc:
        assert "Invalid value" in str(exc)
    else:
        raise AssertionError("invalid axis value should fail")


def test_store_persists_experiment(tmp_path):
    store = ProjectStore(tmp_path / "experiment.sqlite3")
    project = store.create_project(name="Batch", description="", scenario=tiny_base())
    response = run_batch_experiment(BatchExperimentRequest(
        base=tiny_base(), axis="policy_rate", values=[9.0, 11.0], repetitions=1
    ))
    saved = store.save_experiment(project_id=project["id"], result=response, engine_version="1.3.0")
    assert saved["result"]["total_runs"] == 2
    assert store.status()["experiments"] == 1
    listed = store.list_experiments(project["id"])
    assert listed[0]["axis"] == "policy_rate"
