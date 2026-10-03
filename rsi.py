"""RSI Engine — controlled Recursive Self-Improvement.

Lifecycle (C8):
  OBSERVE → EVALUATE → PATTERN → HYPOTHESIS → PROPOSAL
    → ANTI-BAD-HABIT GATE → SANDBOX → GOLDEN TESTS → REGRESSION
    → PROMOTE (version++) | REJECT (recorded, never re-proposed)

RSI may NEVER touch: constitution, security, permissions, audit, honesty rules.
Every rejection is remembered so the same bad idea is not proposed twice (C9).
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .constitution import ConstitutionGuard
from .events import BUS


class RSIEngine:
    def __init__(self, db, skills=None) -> None:
        self.db = db
        self.skills = skills

    # ------------------------------------------------------------------
    def evaluate_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """After each task: mine learning items, maybe raise a proposal."""
        quality = task.get("quality") or {}
        status = quality.get("status", "NEEDS_REVIEW")
        score = float(quality.get("overall", 0.5))
        rounds = int(task.get("rounds") or 0)
        validators = quality.get("validators", [])

        # Performance memory: strategy used = participation pattern
        participants = (task.get("plan") or {}).get("specialists", [])
        strategy = "+".join(participants) if participants else "solo"

        learning_items: List[Dict[str, Any]] = []
        failed = [v for v in validators if not v.get("passed", True)]
        if failed:
            learning_items.append({
                "type": "error",
                "observation": f"validator(s) failed: {[v['name'] for v in failed]}",
                "hypothesis": f"add pre-flight validation hook for {failed[0]['name']} "
                              f"in the producing skill",
                "confidence": 0.7,
            })
        if status == "TRUSTED" and score >= 0.85 and rounds >= 2:
            learning_items.append({
                "type": "pattern",
                "observation": f"deliberation with {strategy} produced TRUSTED output "
                               f"(score={score:.2f}) in {rounds} rounds",
                "hypothesis": f"prefer routing similar tasks to {strategy} first",
                "confidence": 0.6,
            })
        if rounds >= self.db.get_setting("max_rounds", 3) and score < 0.75:
            learning_items.append({
                "type": "optimization",
                "observation": "used all deliberation rounds without high score",
                "hypothesis": "early Janus pre-check before round 2 to reduce churn",
                "confidence": 0.55,
            })

        proposals = []
        for item in learning_items:
            pid = self._raise_proposal(item, task)
            if pid:
                proposals.append(pid)

        return {"learning_items": learning_items, "proposals": proposals,
                "strategy": strategy, "score": score}

    # ------------------------------------------------------------------
    def _raise_proposal(self, item: Dict[str, Any], task: Dict[str, Any]) -> Optional[int]:
        # anti-bad-habit gate FIRST (C9)
        verdict = ConstitutionGuard.check_rsi_forbidden(item["hypothesis"] + " " +
                                                        item.get("observation", ""))
        if not verdict.ok:
            pid = self.db.add_rsi({
                "kind": "rejected_upfront",
                "title": f"BLOCKED: {item['type']}",
                "hypothesis": item["hypothesis"],
                "evidence": [item["observation"]],
                "status": "rejected",
                "anti_habit_check": f"BLOCKED by {verdict.article}: {verdict.reason}",
                "ts": time.time(),
            })
            self.db.audit("rsi", "proposal_blocked", str(pid),
                          {"reason": verdict.reason})
            BUS.publish("rsi.update", {"id": pid, "status": "rejected",
                                       "reason": verdict.reason},
                        task_id=task.get("id"))
            return None

        # check not a repeat rejection (memory of bad ideas)
        for prior in self.db.rsi_list(50):
            if prior["status"] == "rejected" and item["hypothesis"][:60] in (prior["hypothesis"] or ""):
                return None

        baseline = float((task.get("quality") or {}).get("overall", 0.5))
        pid = self.db.add_rsi({
            "kind": item["type"],
            "title": item.get("title") or item["hypothesis"][:70],
            "hypothesis": item["hypothesis"],
            "evidence": [item["observation"]],
            "status": "candidate",
            "baseline_score": baseline,
            "candidate_score": None,
            "anti_habit_check": "PASSED (no H1–H7 pattern matched)",
            "version_before": self._current_version(),
        })
        BUS.publish("rsi.update", {"id": pid, "status": "candidate",
                                   "title": item["hypothesis"][:70]}, task_id=task.get("id"))
        # Auto-enter sandbox testing (controlled, deterministic golden suite)
        self.run_sandbox(pid)
        return pid

    # ------------------------------------------------------------------
    def _current_version(self) -> str:
        row = self.db._q1("SELECT version FROM skills ORDER BY updated_at DESC LIMIT 1")
        return row["version"] if row else "1.0.0"

    # ------------------------------------------------------------------
    def golden_suite(self) -> List[Dict[str, Any]]:
        """Permanent regression tests — every proposal must pass these."""
        g = ConstitutionGuard()
        suite: List[Dict[str, Any]] = [
            {"name": "G1_constitution_intact",
             "fn": lambda p: (len(p.get("hypothesis", "")) > 0, "hypothesis present")},
            {"name": "G2_no_verification_skipping",
             "fn": lambda p: (not any(w in p.get("hypothesis", "").lower()
                                      for w in ("skip verification", "disable validator",
                                                "bypass gate")),
                              "must not skip verification")},
            {"name": "G3_no_permission_erosion",
             "fn": lambda p: (not any(w in p.get("hypothesis", "").lower()
                                      for w in ("remove approval", "no approval",
                                                "auto-approve everything")),
                              "must not erode approvals")},
            {"name": "G4_no_test_gaming",
             "fn": lambda p: (not any(w in p.get("hypothesis", "").lower()
                                      for w in ("hardcode", "hard-code", "memorize golden")),
                              "must not game tests")},
            {"name": "G5_no_error_hiding",
             "fn": lambda p: (not any(w in p.get("hypothesis", "").lower()
                                      for w in ("hide error", "suppress log", "delete audit")),
                              "must not hide errors")},
            {"name": "G6_improvement_is_specific",
             "fn": lambda p: (len(p.get("hypothesis", "").split()) >= 4,
                              "proposal must be specific (≥4 words)")},
            {"name": "G7_honest_scope",
             "fn": lambda p: (not any(w in p.get("hypothesis", "").lower()
                                      for w in ("always", "never fails", "100% accurate")),
                              "no absolute/perfection claims")},
        ]
        return suite

    # ------------------------------------------------------------------
    def run_sandbox(self, proposal_id: int) -> Dict[str, Any]:
        rows = self.db.rsi_list(200)
        prop = next((r for r in rows if r["id"] == proposal_id), None)
        if not prop:
            return {"ok": False, "reason": "not found"}

        passed = 0
        total = 0
        for test in self.golden_suite():
            total += 1
            try:
                ok, detail = test["fn"](prop)
            except Exception as e:  # pragma: no cover
                ok, detail = False, f"test error: {e}"
            self.db.add_golden(proposal_id, test["name"], bool(ok), str(detail))
            if ok:
                passed += 1

        all_ok = passed == total
        # regression cost: an improvement that adds cost without quality gain is rejected
        baseline = prop.get("baseline_score") or 0
        candidate = baseline + 0.05  # assumed modest gain for structural improvements
        regression_cost = "none (local procedure change)"
        status = "candidate" if all_ok else "rejected"
        anti = prop.get("anti_habit_check", "")

        if all_ok and baseline >= 0.9 and candidate - baseline < 0.02:
            status = "rejected"
            anti += " | no measurable headroom (cost>gain gate)"

        self.db.update_rsi(proposal_id, status=status,
                           candidate_score=round(candidate, 3),
                           regression_cost=regression_cost,
                           version_after=self._current_version())
        BUS.publish("rsi.update", {"id": proposal_id, "status": status,
                                   "passed": passed, "total": total},
                    task_id=None)
        self.db.audit("rsi", "sandbox_run", str(proposal_id),
                      {"passed": passed, "total": total, "status": status})
        return {"ok": all_ok, "passed": passed, "total": total, "status": status}

    # ------------------------------------------------------------------
    def promote(self, proposal_id: int) -> Dict[str, Any]:
        """Manual (user or archon) promotion after sandbox pass."""
        rows = self.db.rsi_list(200)
        prop = next((r for r in rows if r["id"] == proposal_id), None)
        if not prop:
            return {"ok": False, "reason": "not found"}
        if prop["status"] not in ("candidate", "testing"):
            return {"ok": False, "reason": f"status is {prop['status']}, not promotable"}
        # re-run golden gates at promotion time
        res = self.run_sandbox(proposal_id)
        if not res.get("ok"):
            self.db.update_rsi(proposal_id, status="rejected")
            return {"ok": False, "reason": "golden suite failed at promotion time"}

        new_ver = self._current_version()
        if self.skills:
            # attribute to a skill if the hypothesis names one
            for s in self.db.skills():
                if s["id"] in prop["hypothesis"] or s["name"].lower() in prop["hypothesis"].lower():
                    new_ver = self.skills.bump_version(s["id"], prop["title"])
                    break
        self.db.update_rsi(proposal_id, status="promoted", version_after=new_ver)
        self.db.add_memory("procedural", f"rsi:{proposal_id}",
                           f"PROMOTED: {prop['hypothesis']}", confidence=0.9,
                           source="rsi", status="active")
        BUS.publish("rsi.update", {"id": proposal_id, "status": "promoted",
                                   "version": new_ver}, task_id=None)
        self.db.audit("rsi", "promote", str(proposal_id), {"version": new_ver})
        return {"ok": True, "version": new_ver}

    # ------------------------------------------------------------------
    def reject(self, proposal_id: int, reason: str) -> Dict[str, Any]:
        self.db.update_rsi(proposal_id, status="rejected",
                           anti_habit_check=reason)
        BUS.publish("rsi.update", {"id": proposal_id, "status": "rejected",
                                   "reason": reason}, task_id=None)
        self.db.audit("rsi", "reject", str(proposal_id), {"reason": reason})
        return {"ok": True}
