from abc import ABC, abstractmethod

from economy_lab.core.state import EconomyState


class EconomicEngine(ABC):
    """Adapter contract for Mesa/HARK/Minsky/Dynare-like engines."""

    name: str

    @abstractmethod
    def step(self, state: EconomyState) -> EconomyState:
        raise NotImplementedError
