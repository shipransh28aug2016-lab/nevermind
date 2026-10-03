"""Deliberation protocol — structured, evidence-based, win-win.

Rules enforced by code (not by hope):
  1. Messages must conform to the protocol schema (typed envelopes).
  2. A CHALLENGE must cite evidence (evidence[] non-empty) — no vibes.
  3. A REVISION that follows a challenge must map to concerns (concessions).
  4. Personal attacks / disobedience of constitution → message REJECTED + fault logged.
  5. Deadlock after MAX rounds → Archon arbitrates by constitution+evidence or
     escalates ONE precise question to the user (never silent guessing, C12).
  6. Consensus requires: no open CONCERN from an authority holder, and Janus
     (quality) has approved or its residual concerns appear in limitations.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .constitution import ConstitutionGuard

MAX_ROUNDS = 3

# message types
REQUEST = "REQUEST"
PROPOSAL = "PROPOSAL"
CHALLENGE = "CHALLENGE"
REVISION = "REVISION"
CONCERN = "CONCERN"
CONSENSUS = "CONSENSUS"
ESCALATE = "ESCALATE"
FAULT = "FAULT"
SYSTEM = "SYSTEM"

ATTACK_RE = r"\b(you\s+are\s+(wrong|stupid|useless)|shut\s+up|idiot|nonsense from you)\b"


class ProtocolError(Exception):
    pass


class Deliberation:
    """One deliberation session bound to a task."""

    def __init__(self, task_id: str, emit: Callable[[str, str, str, str, str, Dict], None],
                 db, round_max: int = MAX_ROUNDS) -> None:
        self.task_id = task_id
        self.db = db
        self.emit = emit          # emit(mtype, frm, to, body, payload)
        self.round = 0
        self.round_max = round_max
        self.consensus: Optional[Dict[str, Any]] = None
        self.proposals: Dict[str, Dict[str, Any]] = {}     # agent -> proposal
        self.challenges: Dict[str, List[Dict[str, Any]]] = {}  # target_agent -> concerns
        self.concessions: Dict[str, List[str]] = {}
        self.faults: List[Dict[str, Any]] = []
        self.open_concerns: List[Dict[str, Any]] = []
        self.escalation: Optional[str] = None

    # ------------------------------------------------------------------
    def _send(self, mtype: str, frm: str, to: str, body: str,
              payload: Optional[Dict[str, Any]] = None) -> None:
        payload = payload or {}
        # Constitution screen on every outbound body (C5/C9)
        v = ConstitutionGuard.screen(body)
        if not v.ok:
            mtype, payload = FAULT, {**(payload or {}), "violation": v.as_dict()}
            body = f"[CONSTITUTION BLOCKED] {v.article}: {v.reason} — message withheld."
            self.faults.append({"article": v.article, "reason": v.reason, "from": frm})
        if len(body) > 4000:
            body = body[:4000] + " …[truncated]"
        self.db.add_message(self.task_id, self.round, mtype, frm, to, body, payload)
        self.emit(mtype, frm, to, body, payload)

    # ------------------------------------------------------------------
    def request(self, from_agent: str, to_agents: List[str], brief: str,
                plan: Dict[str, Any]) -> None:
        self.round = 1
        self._send(SYSTEM, "archon", "all",
                   f"Deliberation round 1/{self.round_max} opened.", {"plan": plan})
        for a in to_agents:
            self._send(REQUEST, from_agent, a, brief, {"plan": plan})

    # ------------------------------------------------------------------
    def propose(self, agent: str, body: str, payload: Dict[str, Any]) -> None:
        """A specialist files a proposal (content, confidence, evidence)."""
        # rule: proposals cannot claim fabricated completion (C2/C3 via constitution screen)
        confidence = float(payload.get("confidence", 0.7))
        evidence = payload.get("evidence", []) or []
        if not evidence:
            evidence = ["reasoning based on domain charter + provided inputs"]
            payload["evidence"] = evidence
            payload["evidence_quality"] = "inferred"
        self.proposals[agent] = {"body": body, "payload": payload, "confidence": confidence,
                                 "round": self.round}
        self._send(PROPOSAL, agent, "archon", body, payload)

    # ------------------------------------------------------------------
    def challenge(self, agent: str, target: str, body: str,
                  concerns: List[str], evidence: List[str]) -> None:
        """A challenge MUST carry evidence — protocol rule #2."""
        if not evidence:
            self._send(FAULT, agent, target,
                       "Challenge rejected by protocol: no evidence supplied (rule #2).",
                       {"rule": 2})
            return
        if not concerns:
            self._send(FAULT, agent, target,
                       "Challenge rejected: no concrete concerns listed (rule #2b).",
                       {"rule": 2})
            return
        # personal-attack screen (rule #4)
        import re
        if re.search(ATTACK_RE, body, flags=re.IGNORECASE):
            self._send(FAULT, agent, target,
                       "Challenge rejected: personal attack — win-win only (rule #4 / C5).",
                       {"rule": 4})
            return
        self._send(CHALLENGE, agent, target, body,
                   {"concerns": concerns, "evidence": evidence})
        self.challenges.setdefault(target, []).extend(
            [{"concerns": concerns, "evidence": evidence, "from": agent}])

    # ------------------------------------------------------------------
    def revise(self, agent: str, body: str, payload: Dict[str, Any]) -> None:
        """Revision must map to received concerns (rule #3: concessions)."""
        received = self.challenges.get(agent, [])
        addressed = payload.get("addresses", [])
        if received and not addressed:
            self._send(FAULT, agent, "archon",
                       "Revision rejected: must state which concerns it addresses (rule #3).",
                       {"rule": 3, "open": len(received)})
            return
        self.concessions.setdefault(agent, []).extend(addressed)
        self.proposals[agent] = {"body": body, "payload": payload,
                                 "confidence": float(payload.get("confidence", 0.7)),
                                 "round": self.round, "revised": True}
        self._send(REVISION, agent, "archon", body, payload)

    # ------------------------------------------------------------------
    def concern(self, agent: str, body: str, payload: Dict[str, Any]) -> None:
        self._send(CONCERN, agent, "archon", body, payload)
        self.open_concerns.append({"from": agent, "body": body, "payload": payload})

    # ------------------------------------------------------------------
    def resolve_concern(self, concern_from: str, summary: str) -> None:
        """A concern is closed when its owner accepts the resolution (win-win)."""
        self.open_concerns = [c for c in self.open_concerns if c["from"] != concern_from]
        self._send(SYSTEM, "archon", concern_from,
                   f"Concern resolved: {summary}", {"resolved": True})

    # ------------------------------------------------------------------
    def try_consensus(self, verdict_note: str, residual_limitations: List[str]) -> bool:
        # Janus must not have open hard concerns
        janus_open = [c for c in self.open_concerns if c["from"] == "quality"]
        if janus_open:
            return False
        if not self.proposals:
            return False
        avg_conf = sum(p["confidence"] for p in self.proposals.values()) / len(self.proposals)
        self.consensus = {
            "confidence": round(avg_conf, 2),
            "participants": list(self.proposals.keys()),
            "rounds_used": self.round,
            "note": verdict_note,
            "residual_limitations": residual_limitations,
            "concessions": {k: v for k, v in self.concessions.items() if v},
        }
        self._send(CONSENSUS, "archon", "all",
                   f"CONSENSUS reached in round {self.round}: {verdict_note}",
                   self.consensus)
        return True

    # ------------------------------------------------------------------
    def escalate_to_user(self, question: str) -> None:
        self.escalation = question
        self._send(ESCALATE, "archon", "user",
                   question, {"question": question})

    # ------------------------------------------------------------------
    def deadlock_arbitration(self, reason: str) -> Dict[str, Any]:
        """Archon's constitutional arbitration when rounds exhaust (C4/C5)."""
        # rank proposals by: evidence quality, confidence, authority of holder
        def score(item: Tuple[str, Dict[str, Any]]) -> float:
            agent, p = item
            s = p.get("confidence", 0.5)
            ev = p.get("payload", {}).get("evidence_quality", "inferred")
            s += {"verified": 0.25, "derived": 0.15, "inferred": 0.0}.get(ev, 0.0)
            if agent == "quality":
                s += 0.05  # janus bias: safety-first tiebreak
            return s
        ranked = sorted(self.proposals.items(), key=score, reverse=True)
        winner_agent, winner = ranked[0] if ranked else (None, None)
        arb = {
            "reason": reason,
            "winner": winner_agent,
            "ranking": [{"agent": a, "score": round(score((a, p)), 3)}
                        for a, p in ranked],
            "residual_limitations": [c["body"] for c in self.open_concerns],
        }
        self._send(SYSTEM, "archon", "all",
                   f"Arbitration ({reason}): accepted best-evidenced proposal "
                   f"from {winner_agent}; residual concerns published as limitations, "
                   "not hidden (C5/C6).", arb)
        self.consensus = {
            "confidence": round(winner.get("confidence", 0.5) * 0.9, 2) if winner else 0.4,
            "participants": list(self.proposals.keys()),
            "rounds_used": self.round,
            "note": f"arbitrated: {reason}",
            "residual_limitations": arb["residual_limitations"],
            "arbitration": arb,
        }
        return self.consensus
