"""Quality gates framework."""

from typing import Any, Dict, List, Protocol

from pydantic import BaseModel, Field


class GateResult(BaseModel):
    """Result of a quality gate check."""

    name: str
    passed: bool
    score: float = Field(default=0.0)
    details: Dict[str, Any] = Field(default_factory=dict)


class QualityGate(Protocol):
    """Protocol for quality gates."""

    name: str

    def check(self, artifact: Dict[str, Any]) -> GateResult:
        """Check if artifact passes this gate."""
        ...


class GateRunner:
    """Runs quality gates on artifacts."""

    def __init__(self, gates: List[QualityGate]):
        self.gates = gates

    def run(self, artifact: Dict[str, Any]) -> List[GateResult]:
        """Run all gates on artifact."""
        results = []
        for gate in self.gates:
            result = gate.check(artifact)
            results.append(result)
        return results

    def all_passed(self, results: List[GateResult]) -> bool:
        """Check if all gates passed."""
        return all(r.passed for r in results)


# Stub gates
class CompletenessGate:
    """Checks artifact completeness."""

    name = "completeness"

    def check(self, artifact: Dict[str, Any]) -> GateResult:
        return GateResult(
            name=self.name,
            passed=True,
            score=0.5,
            details={"message": "Stub completeness check"},
        )


class QualityGateRunner:
    """Stub quality gate runner."""

    def __init__(self, gates: List[QualityGate] | None = None):
        self.gates = gates or [CompletenessGate()]

    def run(self, artifact: Dict[str, Any]) -> List[GateResult]:
        return [gate.check(artifact) for gate in self.gates]


__all__ = ["GateResult", "QualityGate", "GateRunner", "QualityGateRunner"]
