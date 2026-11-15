"""Modelos tipados del SDK. Reflejan la respuesta de la API sin recalcular nada (la API es la fuente de verdad)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled"})


@dataclass(frozen=True)
class ConfidenceInterval:
    lower: float | None
    upper: float | None
    level: float
    method: str

    def __str__(self) -> str:
        if self.lower is None or self.upper is None:
            return f"IC {self.level:.0%} no disponible ({self.method})"
        return f"IC {self.level:.0%} [{self.lower:.4g}, {self.upper:.4g}] ({self.method})"


@dataclass(frozen=True)
class HypothesisTest:
    method: str
    p_value: float | None
    q_value: float | None

    def __str__(self) -> str:
        p = "n/d" if self.p_value is None else f"{self.p_value:.3g}"
        return f"{self.method}: p={p}"


@dataclass(frozen=True)
class Statistics:
    status: str  # ok | exploratory | insufficient_evidence
    estimator: str
    estimate: float | None
    estimate_unit: str
    confidence_interval: ConfidenceInterval
    hypothesis_test: HypothesisTest
    n_observations: int
    n_missing: int
    coverage_fraction: float
    autocorrelation_adjustment: str
    warnings: list[str]
    algorithm_version: str
    raw: dict[str, Any] = field(repr=False, compare=False)

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Statistics:
        return cls(
            status=d["status"], estimator=d["estimator"], estimate=d["estimate"], estimate_unit=d["estimate_unit"],
            confidence_interval=ConfidenceInterval(d["ci_lower"], d["ci_upper"], d["confidence_level"], d["ci_method"]),
            hypothesis_test=HypothesisTest(d["test_method"], d["p_value"], d.get("q_value")),
            n_observations=d["n_observations"], n_missing=d["n_missing"], coverage_fraction=d["coverage_fraction"],
            autocorrelation_adjustment=d["autocorrelation_adjustment"], warnings=list(d.get("warnings", [])),
            algorithm_version=d["algorithm_version"], raw=d,
        )

    @property
    def is_inferable(self) -> bool:
        return self.status != "insufficient_evidence" and self.estimate is not None


@dataclass(frozen=True)
class Run:
    id: str
    status: str
    analysis_spec_hash: str
    raw: dict[str, Any] = field(repr=False, compare=False)

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Run:
        return cls(id=d["run_id"], status=d["status"], analysis_spec_hash=d["analysis_spec_hash"], raw=d)

    @property
    def done(self) -> bool:
        return self.status in TERMINAL_STATES
