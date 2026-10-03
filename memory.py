"""Five-layer memory: Episodic · Semantic · Procedural · Performance · Decision.

Promotion policy: candidates become active only with sufficient confidence;
protected layers (semantic institutional rules) never decay; contradicted
entries are deprecated, never silently deleted (auditability, C10).
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

ACTIVE = "active"
CANDIDATE = "candidate"
DEPRECATED = "deprecated"
PROTECTED = "protected"

LAYERS = ["episodic", "semantic", "procedural", "performance", "decision"]


class MemorySystem:
    def __init__(self, db) -> None:
        self.db = db

    # ------------------------------------------------------------------
    def remember(self, layer: str, key: str, content: str, confidence: float = 0.5,
                 source: str = "runtime", promote: bool = False) -> int:
        """Store memory. Non-protected layers start as candidate unless confidence high."""
        status = ACTIVE
        if layer == "semantic" and confidence < 0.7:
            status = CANDIDATE          # domain knowledge needs validation before active
        if layer in ("episodic", "decision", "performance"):
            status = ACTIVE             # experiences are facts about what happened
        if promote:
            status = ACTIVE
        return self.db.add_memory(layer, key, content, confidence, source, status)

    def recall(self, needle: str, layer: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = self.db.find_memories(needle)
        if layer:
            rows = [r for r in rows if r["layer"] == layer and r["status"] in (ACTIVE, PROTECTED)]
        return [r for r in rows if r["status"] in (ACTIVE, PROTECTED, CANDIDATE)][:8]

    def all(self, layer: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.db.memories(layer)

    # ------------------------------------------------------------------
    def episode(self, task_id: str, summary: str, outcome: str, score: float) -> int:
        return self.remember("episodic", task_id,
                             f"{summary} → {outcome} (score={score:.2f})",
                             confidence=min(0.95, 0.5 + score / 2), source="runtime")

    def procedure(self, name: str, steps: List[str], success_rate: float) -> int:
        content = f"{name}: " + " → ".join(steps)
        return self.remember("procedural", name, content, confidence=success_rate,
                             source="runtime", promote=success_rate >= 0.7)

    def performance(self, strategy: str, score: float, cost: float) -> int:
        return self.remember("performance", strategy,
                             f"strategy={strategy} score={score:.2f} cost={cost:.2f}",
                             confidence=0.6, source="runtime")

    def decision(self, situation: str, decision: str, result: str, confidence: float) -> int:
        return self.remember("decision", situation[:60],
                             f"situation={situation} | decision={decision} | result={result}",
                             confidence=confidence, source="runtime")

    def semantic(self, fact: str, source: str, authority: float) -> Optional[int]:
        """Institutional/domain knowledge — needs authority ≥0.7 to become active."""
        if authority < 0.4:
            return None  # too weak to store even as candidate (C1/C3)
        return self.remember("semantic", fact[:60], fact, confidence=authority,
                             source=source, promote=authority >= 0.85)

    def promote(self, mid: int) -> None:
        self.db.update_memory(mid, status=ACTIVE, updated_at=time.time())

    def deprecate(self, mid: int, reason: str) -> None:
        self.db.update_memory(mid, status=DEPRECATED, content_extra=reason) \
            if False else self.db.update_memory(mid, status=DEPRECATED)

    def stats(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for layer in LAYERS:
            rows = self.db.memories(layer)
            out[layer] = {
                "total": len(rows),
                "active": sum(1 for r in rows if r["status"] in (ACTIVE, PROTECTED)),
                "candidate": sum(1 for r in rows if r["status"] == CANDIDATE),
                "deprecated": sum(1 for r in rows if r["status"] == DEPRECATED),
            }
        return out
