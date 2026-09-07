"""Exercise optional engines before activating a managed environment."""
import json
from economy_lab.core.schemas import ScenarioSpec
from economy_lab.core.simulation import run_simulation
from economy_lab.labs import run_hark_lab, run_mesa_lab


def main():
    run_mesa_lab(agents=12, steps=4, seed=11)
    run_hark_lab(income_groups=1, points=5)
    result = run_simulation(ScenarioSpec(name="Verificação dos motores", months=1,
        households=100, firms=5, banks=1, activation_engine="mesa", household_behavior="hark"))
    result = result.model_dump() if hasattr(result, "model_dump") else result
    assert len(result["series"]) == 1
    for key in ("ledger_balanced", "godley_stocks_balanced", "godley_flows_balanced"):
        assert result["summary"][key], key
    print(json.dumps({"mesa": "ok", "hark": "ok", "economy_zero": "ok", "ledger": "balanced"}))


if __name__ == "__main__":
    main()
