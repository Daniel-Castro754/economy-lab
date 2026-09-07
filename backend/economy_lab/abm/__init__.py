from economy_lab.abm.agents import Bank, CentralBank, Firm, Government, Household

__all__ = ["Bank", "CentralBank", "Firm", "Government", "Household", "EconomyZeroModel"]


def __getattr__(name: str):
    # Keep the public convenience export without importing economy_zero during
    # package initialization. This avoids the HARK <-> ABM circular import when
    # optional engines are inspected independently by the validation CLI.
    if name == "EconomyZeroModel":
        from economy_lab.abm.economy_zero import EconomyZeroModel
        return EconomyZeroModel
    raise AttributeError(name)
