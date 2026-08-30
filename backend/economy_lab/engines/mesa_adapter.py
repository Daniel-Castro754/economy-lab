"""Mesa 3.5.x activation bridge for Economy Zero.

Economy Lab owns the domain state and ledger. Mesa owns agent registration,
querying and activation order when this adapter is selected.  Proxies contain no
independent economic balances, preventing two competing sources of truth.
"""

from __future__ import annotations

from importlib.util import find_spec
from typing import TYPE_CHECKING, Protocol

from economy_lab.engines.hark_adapter import EngineUnavailableError

if TYPE_CHECKING:
    from economy_lab.abm.economy_zero import EconomyZeroModel


MESA_TARGET_VERSION = "3.5.1"


def mesa_available() -> bool:
    return find_spec("mesa") is not None


class ActivationRuntime(Protocol):
    name: str

    def produce_firms(self) -> None: ...

    def consume_households(self) -> None: ...

    def update_firm_prices(self) -> None: ...


class NativeActivationRuntime:
    """Reference runtime preserving the deterministic reference-loop semantics."""

    name = "native"

    def __init__(self, domain: "EconomyZeroModel") -> None:
        self.domain = domain

    def produce_firms(self) -> None:
        for firm in self.domain.firms:
            self.domain._produce_firm(firm)

    def consume_households(self) -> None:
        for household in self.domain.households:
            self.domain._consume_household(household)

    def update_firm_prices(self) -> None:
        for firm in self.domain.firms:
            self.domain._update_price_firm(firm)


def _build_mesa_runtime(domain: "EconomyZeroModel") -> ActivationRuntime:
    if not mesa_available():
        raise EngineUnavailableError(
            "Mesa foi solicitado, mas não está instalado. "
            'Instale as dependências de simulação com: pip install -e ".[simulation]"'
        )

    import mesa

    class FirmProxy(mesa.Agent):
        def __init__(self, model, firm_id: int):
            super().__init__(model)
            self.firm_id = firm_id

        def produce(self) -> None:
            self.model.domain._produce_firm(self.model.domain.firms[self.firm_id])

        def update_price(self) -> None:
            self.model.domain._update_price_firm(self.model.domain.firms[self.firm_id])

    class HouseholdProxy(mesa.Agent):
        def __init__(self, model, household_id: int):
            super().__init__(model)
            self.household_id = household_id

        def consume(self) -> None:
            self.model.domain._consume_household(
                self.model.domain.households[self.household_id]
            )

    class EconomyMesaActivationModel(mesa.Model):
        def __init__(self, economy: "EconomyZeroModel"):
            super().__init__(seed=economy.config.seed)
            self.domain = economy
            self.firm_proxies = [FirmProxy(self, firm.id) for firm in economy.firms]
            self.household_proxies = [
                HouseholdProxy(self, household.id) for household in economy.households
            ]

    class MesaActivationRuntime:
        name = "mesa-3.5"

        def __init__(self, economy: "EconomyZeroModel"):
            self.model = EconomyMesaActivationModel(economy)

        def _activate(self, agent_type, method: str) -> None:
            agents = self.model.agents_by_type[agent_type]
            if self.model.domain.config.mesa_activation_pattern == "fixed":
                agents.do(method)
            else:
                agents.shuffle_do(method)

        def produce_firms(self) -> None:
            self._activate(FirmProxy, "produce")

        def consume_households(self) -> None:
            self._activate(HouseholdProxy, "consume")

        def update_firm_prices(self) -> None:
            self._activate(FirmProxy, "update_price")

    return MesaActivationRuntime(domain)


def create_activation_runtime(name: str, domain: "EconomyZeroModel") -> ActivationRuntime:
    if name == "native":
        return NativeActivationRuntime(domain)
    if name == "mesa":
        return _build_mesa_runtime(domain)
    raise ValueError(f"Unknown activation engine: {name}")
