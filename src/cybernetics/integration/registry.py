from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .contracts import ModuleContract, ContractViolation, DependencyAuditor


@dataclass(frozen=True)
class DependencyEdge:
    consumer: str
    capability: str
    provider: str


@dataclass(frozen=True)
class IntegrationGraph:
    contracts: tuple[ModuleContract, ...]
    edges: tuple[DependencyEdge, ...]


class IntegrationRegistry:
    def __init__(self):
        self._contracts: dict[str, ModuleContract] = {}

    def register(self, contract: ModuleContract) -> None:
        if contract.module_id in self._contracts:
            raise ContractViolation(
                f"duplicate_module_id:{contract.module_id}"
            )
        self._contracts[contract.module_id] = contract

    def contracts(self) -> tuple[ModuleContract, ...]:
        return tuple(self._contracts.values())

    def audit(self):
        return DependencyAuditor().audit(self.contracts())

    def graph(self) -> IntegrationGraph:
        providers: dict[str, list[str]] = {}
        for c in self._contracts.values():
            for capability in c.provides:
                providers.setdefault(capability, []).append(c.module_id)

        edges=[]
        for c in self._contracts.values():
            for requirement in c.requires:
                owners=providers.get(requirement, [])
                if len(owners)==1:
                    edges.append(
                        DependencyEdge(c.module_id, requirement, owners[0])
                    )
        return IntegrationGraph(self.contracts(), tuple(edges))

    def production_eligible_modules(self) -> tuple[str, ...]:
        return tuple(
            c.module_id for c in self._contracts.values()
            if c.production_eligible
        )
