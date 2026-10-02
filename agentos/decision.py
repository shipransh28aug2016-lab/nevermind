"""Autonomous Decision Engine.

DECIDE(intent, context, memory, tools, policies, risk, confidence)
  → DecisionRecord (traceable, auditable)

Risk/authority ladder:
  L0 Observe · L1 Answer · L2 Create · L3 Execute reversible ·
  L4 Approval required · L5 Forbidden
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional

from .config import AUTONOMY_LEVELS

# (keyword regex, level, risk 0..1, reversibility, action id)
_RULES: List[tuple] = [
    # L5 — forbidden
    (r"delete (the )?(student|all|database|permanent)", 5, 0.99, "low", "delete_records"),
    (r"format (the )?(disk|drive)|wipe (the )?(disk|drive)", 5, 0.99, "low", "destructive_system"),
    (r"(steal|hack|bypass login|break into)", 5, 0.99, "low", "malicious"),
    # L4 — approval required (external / consequential)
    (r"(send|email|mail|post|publish|submit) .*(principal|headmaster|parent|board|cbse|client|office|news|deo|authorit(?:y|ies)|magistrate|collector|department)",
     4, 0.6, "medium", "external_communication"),
    (r"(send|whatsapp|sms|call) (the )?(students|parents|staff)", 4, 0.55, "medium", "mass_communication"),
    (r"(sign|approve|lock|submit|finali[sz]e) .*(result|marksheet|document|report)",
     4, 0.6, "low", "official_finalize"),
    (r"(refund|payment|pay|purchase|subscribe|transfer) ", 4, 0.7, "low", "financial"),
    # NB: lookbehinds — "press release" / "media release" are DRAFTING nouns (LOW),
    # not the publish verb; explicit "publish/deploy …" still lands L4 (HIGH).
    (r"(?<!press )(?<!media )(publish|deploy|release) ", 4, 0.5, "medium", "publish"),
    # L3 — reversible execution in configured workspace
    (r"(save|move|overwrite|upload|write) ", 3, 0.3, "high", "file_write"),
    (r"(schedule|remind|queue|plan) ", 3, 0.25, "high", "schedule"),
    # L2 — creation (safe)
    (r"(create|make|generate|build|prepare|draft|write|design|prepare|बन|तैयार|लिख)",
     2, 0.12, "high", "create_artifact"),
    # L1 — answer
    (r"(what|why|how|when|where|who|explain|tell|show|क्या|कैसे|कब|क्यों)", 1, 0.05, "high", "answer"),
    # L0 — observe
    (r"(list|show|status|report of existing|दिखा)", 0, 0.02, "high", "observe"),
]

# ---------------------------------------------------------------------------
# 3-tier risk system (HITL spec):
#   LOW    → drafting/reading            → AUTO-EXECUTE
#   MEDIUM → local file writes           → AUTO-EXECUTE + ASYNC AUDIT
#   HIGH   → external comms / publishing → HARD BLOCK pending human approval
# L5 stays FORBIDDEN (approvals may never unlock it — constitution).
# ---------------------------------------------------------------------------
HIGH_RISK_ACTIONS = {"external_communication", "mass_communication", "official_finalize",
                     "financial", "publish", "malicious", "delete_records",
                     "destructive_system"}
MEDIUM_RISK_ACTIONS = {"file_write", "schedule"}
GATE_BEHAVIOR = {
    "LOW": "AUTO_EXECUTE",
    "MEDIUM": "AUTO_EXECUTE_WITH_ASYNC_AUDIT",
    "HIGH": "HUMAN_APPROVAL_REQUIRED",
}


def risk_tier(level: int, action: str, risk: float) -> str:
    """Map (level, action) → LOW | MEDIUM | HIGH per the risk-tiering spec."""
    if level >= 5 or action in HIGH_RISK_ACTIONS:
        return "HIGH"
    if level == 4:
        return "HIGH"
    if action in MEDIUM_RISK_ACTIONS or level == 3:
        return "MEDIUM"
    return "LOW"


CONFIDENCE_THRESHOLD = 0.55  # below → escalate/clarify instead of auto-execute
CONTEXT_REQUIRED_SLOTS = {
    "question_paper": ["subject", "class_level"],
    "worksheet": ["topic"],
    "result_analysis": ["dataset"],
}


@dataclass
class Decision:
    intent: str
    action: str
    autonomy_level: int
    mode: str
    confidence: float
    risk: float
    reversibility: str
    reasoning: str
    requires_approval: bool
    context_missing: List[str] = field(default_factory=list)
    budget: float = 5.0
    task_id: Optional[str] = None
    risk_tier: str = "LOW"                      # LOW | MEDIUM | HIGH
    gate: str = "AUTO_EXECUTE"                  # GATE_BEHAVIOR value / FORBIDDEN

    @property
    def mode_label(self) -> str:
        return AUTONOMY_LEVELS[self.autonomy_level]

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["mode_label"] = self.mode_label
        return d


class DecisionEngine:
    def __init__(self, autonomy_mode: str = "SEMI_AUTONOMOUS") -> None:
        self.autonomy_mode = autonomy_mode  # ASSISTED | SEMI_AUTONOMOUS | AUTONOMOUS | AUTONOMOUS_PROACTIVE

    # ------------------------------------------------------------------
    def decide(self, intent: str, command: str, entities: Dict[str, Any],
               task_id: str, mode_override: Optional[str] = None) -> Decision:
        mode = mode_override or self.autonomy_mode
        text = f"{command}"
        level, risk, rev, action = 1, 0.05, "high", "answer"

        for pattern, lv, rk, rv, act in _RULES:
            if re.search(pattern, text, flags=re.IGNORECASE):
                level, risk, rev, action = lv, rk, rv, act
                break

        # Intent can raise the level (e.g., generate artifact → L2 even if verb matched L1)
        if intent in ("generate_question_paper", "generate_worksheet", "generate_answer_key",
                      "generate_lesson_plan", "draft_letter", "draft_notice", "draft_circular",
                      "result_analysis", "remedial_plan", "generate_report",
                      # HITL upgrade intents
                      "draft_press_release", "generate_active_recall", "story_lesson",
                      "generate_quiz", "build_learning_app",
                      "draft_official_email") and level < 2:
            level, risk, action = 2, 0.12, "create_artifact"

        # External communication intent is ALWAYS L4+ (HITL high tier),
        # regardless of which recipient the rule matched. The PR skill pack
        # (artifacts flagged NEEDS_APPROVAL) is gated the same way: drafting an
        # official email or press release parks for human approval (C7).
        if intent in ("external_communication", "draft_press_release",
                      "draft_official_email") and level < 4:
            level, risk, action = 4, 0.55, intent

        # Assisted mode caps autonomy at L1 for execution actions
        if mode == "ASSISTED" and level >= 3:
            level = min(level, 4)  # keep approval marker but nothing auto-executes past create
            if level == 3:
                level = 4
                risk = max(risk, 0.4)

        # 3-tier risk classification (after level is final)
        tier = risk_tier(level, action, risk)

        # Context completeness
        missing: List[str] = []
        for slot in CONTEXT_REQUIRED_SLOTS.get(intent, []):
            if slot == "subject" and not entities.get("subject"):
                missing.append("subject")
            if slot == "class_level" and not entities.get("class_level"):
                missing.append("class_level")
            if slot == "topic" and not entities.get("topic"):
                missing.append("topic")
            if slot == "dataset" and not entities.get("has_data"):
                missing.append("data source (e.g., marks file or pasted data)")

        confidence = self._confidence(level, entities, missing, command)

        # Risk gate — tier-driven (HITL spec)
        requires_approval = False
        async_audit = False
        if level == 5:
            pass  # FORBIDDEN — pre-action gate hard-blocks downstream
        elif tier == "HIGH":
            # external communication / publishing / consequential → human gate
            requires_approval = True
            level = max(level, 4)
        elif tier == "MEDIUM":
            if risk > 0.5:  # defensive: unusually heavy MEDIUM action → human gate
                requires_approval = True
                level = max(level, 4)
                tier = "HIGH"
            else:
                async_audit = True  # auto-execute, audited after the fact
        if not requires_approval and confidence < CONFIDENCE_THRESHOLD and level >= 2:
            # insufficient context → clarification path (not silent guessing, C12)
            level = min(level, 1)
            requires_approval = False
            async_audit = False

        if level == 5:
            gate = "FORBIDDEN"
        elif requires_approval:
            gate = GATE_BEHAVIOR["HIGH"]
        elif tier == "MEDIUM":
            gate = GATE_BEHAVIOR["MEDIUM"]
        else:
            gate = GATE_BEHAVIOR["LOW"]

        reasoning = (
            f"Rule match → action '{action}' at L{level} ({AUTONOMY_LEVELS[level]}); "
            f"tier={tier} ({gate}); risk={risk:.2f}; reversibility={rev}; "
            f"confidence={confidence:.2f}; context_missing={missing or 'none'}; "
            f"mode={mode}."
        )
        return Decision(
            intent=intent, action=action, autonomy_level=level, mode=mode,
            confidence=confidence, risk=risk, reversibility=rev, reasoning=reasoning,
            requires_approval=requires_approval, context_missing=missing,
            task_id=task_id, risk_tier=tier, gate=gate,
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _confidence(level: int, entities: Dict[str, Any], missing: List[str], command: str) -> float:
        c = 0.72
        if entities.get("class_level"):
            c += 0.08
        if entities.get("subject"):
            c += 0.06
        if entities.get("topic"):
            c += 0.06
        if len(command.split()) >= 5:
            c += 0.05
        if missing:
            c -= 0.12 * len(missing)
        if level >= 4:
            c = min(c, 0.85)  # consequential actions never auto-confident
        return round(max(0.05, min(0.97, c)), 2)

    def record(self, db, decision: Decision) -> int:
        return db.add_decision(decision.as_dict())
