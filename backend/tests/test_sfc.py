from economy_lab.abm.economy_zero import EconomyZeroConfig, EconomyZeroModel
from economy_lab.engines.minsky_adapter import build_godley_export
from economy_lab.finance import flow_matrix, sector_balance_sheets, stock_matrix


def test_sector_balance_sheets_and_godley_rows_close():
    model = EconomyZeroModel(EconomyZeroConfig(households=200, firms=8, banks=2, seed=31))
    model.run(4)

    sheets = sector_balance_sheets(model.ledger)
    assert all(sheet.closes for sheet in sheets)

    stocks = stock_matrix(model.ledger, tick=model.tick)
    flows = flow_matrix(model.ledger, tick=model.tick)
    assert stocks.balanced is True
    assert flows.balanced is True
    instruments = {row.instrument for row in stocks.rows}
    assert instruments >= {"deposits", "reserves", "government_bonds"}
    assert "loans" in instruments or "household_loans" in instruments


def test_minsky_export_is_deterministic_and_balanced():
    model = EconomyZeroModel(EconomyZeroConfig(households=150, firms=6, banks=2, seed=9))
    model.run(2)
    export = build_godley_export(model.ledger, tick=model.tick)
    payload = export.to_payload()

    assert payload["schema"] == "economy-lab-godley-v1.0"
    assert payload["tick"] == 2
    assert payload["columns"] == ["households", "firms", "banks", "government", "central_bank", "rest_of_world"]
    assert all(abs(row["total"]) < 1e-6 for row in payload["stocks"])
    assert all(abs(row["total"]) < 1e-6 for row in payload["flows"])


def test_bank_equity_is_an_explicit_balanced_godley_instrument():
    model = EconomyZeroModel(EconomyZeroConfig(households=100, firms=5, banks=2, seed=3))
    stocks = stock_matrix(model.ledger, tick=0)
    equity = next(row for row in stocks.rows if row.instrument == "bank_equity")
    assert equity.sectors["households"] > 0
    assert equity.sectors["banks"] < 0
    assert abs(equity.total) < 1e-6
