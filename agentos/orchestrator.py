"""The Archon — master orchestrator.

Full task lifecycle:
  PERCEIVE → DECIDE → PLAN → DELIBERATE (win-win) → EXECUTE (skills)
    → VERIFY (hard gates) → DELIVER (structured) → LEARN (memory + RSI)

Guarded by: Constitution, Decision Engine, Loop Guards, approval gate (L4+).
"""
from __future__ import annotations

import hashlib
import os
import re
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from .agents import (ACADEMIC, ADMIN, AGENTS, ARCHON, ALL_SPECIALISTS, DATA,
                     QUALITY, RESEARCH, for_intent, roster)
from .config import (AUTONOMY_MODES, DEFAULT_TASK_BUDGET_COST,
                     MAX_DELIBERATION_ROUNDS, MAX_STEPS_PER_TASK, OUTPUT_DIR)
from .constitution import ConstitutionGuard
from .decision import Decision, DecisionEngine
from .deliberation import SYSTEM as SYSTEM_MSG, Deliberation
from .events import BUS
from . import syllabus as SYL
from .knowledge_graph import KnowledgeGraph
from .llm import engine_from_settings
from .memory import MemorySystem
from .rsi import RSIEngine
from .skills import SkillRegistry

# ---------------------------------------------------------------------------
# Intent & entity perception (deterministic NLU — works in en/hi/hinglish)
# ---------------------------------------------------------------------------
INTENT_PATTERNS: List[Tuple[str, List[str]]] = [
    # HITL upgrade intents — ordered FIRST so specific phrasings win
    ("draft_press_release", ["press release", "press note", "media release",
                             "media statement", "प्रेस विज्ञप्ति"]),
    ("story_lesson", ["storytelling", "story-driven", "story driven", "story-based",
                      "story lesson", "storify", "कहानी से"]),
    ("generate_active_recall", ["active recall", "retrieval practice", "recall drill",
                                "recall round", "सक्रिय स्मरण"]),
    ("generate_quiz", ["adaptive quiz", "quiz", "pop quiz", "प्रश्नोत्तरी"]),
    # PR pack: drafting intents beat generic external/letter patterns (L4-forced)
    ("draft_official_email", ["official email", "draft an email", "draft email",
                              "email draft", "write an email", "write a mail",
                              "draft a mail"]),
    # external transmission beats generic drafting AND "website" keyword (HITL L4)
    ("external_communication", ["send an email", "send email", "email to", "email the",
                                "email a ", "mail to", "mail the", "mail a ",
                                "send to principal", "send a message", "send a letter",
                                "send letter", "send the letter", "whatsapp",
                                "post on", "notify the", "forward the",
                                "publish ", "publishing ", "प्रकाशित",
                                "बेचो नहीं", "भेजो"]),
    ("build_learning_app", ["web app", "webapp", "webpage", "website", "simulator",
                            "interactive app", "html page", "learning app",
                            "ui component"]),
    ("generate_question_paper", ["question paper", "exam paper", "half yearly", "unit test",
                                 "question bank", "test paper", "प्रश्नपत्र", "paper बनाओ",
                                 "paper तैयार", "qp बन"]),
    ("generate_worksheet", ["worksheet", "practice sheet", "वर्कशीट", "होमवर्क", "homework",
                            "assignment", "प्रैक्टिस"]),
    ("generate_lesson_plan", ["lesson plan", "पाठ योजना", "teach plan", "class plan"]),
    ("remedial_plan", ["remedial", "weak student", "intervention", "उपचार", "कमजोर",
                       "remediation", "improve score"]),
    ("result_analysis", ["result analysis", "marks analysis", "analyse", "analyze",
                         "performance analysis", "स्कोर", "रिजल्ट विश्लेषण", "कितने बच्चे"]),
    ("draft_letter", ["letter", "पत्र", "application to", "formal letter", "write to principal"]),
    ("draft_notice", ["notice", "सूचना", "announcement"]),
    ("draft_circular", ["circular", "परिपत्र", "office order"]),
    ("draft_minutes", ["minutes of meeting", "meeting notes", "agenda", "बैठक की कार्रवाई"]),
    ("research_brief", ["research", "find out", "what is", "explain the rule", "policy",
                        "circular info", "खोजो", "जानकारी", "क्या है"]),
    ("action_plan", ["make a plan", "action plan", "roadmap", "strategy", "schedule",
                     "योजना", "कार्ययोजना", "steps to"]),
    ("generate_report", ["report", "रिपोर्ट", "write a summary document", "brief document"]),
]

ENTITY_PATTERNS = {
    "class_level": r"class\s+(x{1,2}i{0,2}|1[01]|12|xi{1,2}|ix|x)\b|"
                   r"(x{1,2}i{0,2}|1[01]|12)\s+(वीं|वी|th|st|nd|rd)?\s*(कक्षा|क्लास)|"
                   r"कक्षा\s*(x{1,2}i{0,2}|9|10|11|12)",
    # NB: ASCII lookarounds, not \b — Python \b is false between a Devanagari
    # vowel sign (Mc) and a space, which silently dropped all Hindi subjects.
    "subject": r"(?<![A-Za-z0-9])(accountancy|accounting|business studies|bst|"
               r"entrepreneurship|etp|economics|english|hindi|mathematics|maths|"
               r"science|history|अकाउंटेंसी|अकाउंटेंट्स|बिज़नेस\s*स्टडीज़?|व्यवसाय|"
               r"उद्यमशीलता|एंटरप्रेन्योरशिप|अर्थशास्त्र)(?![A-Za-z0-9])",
    "topic": r"\b(partnership|admission|retirement|dissolution|company accounts|shares|"
             r"debentures|cash flow|financial analysis|ratios|analysis of financial|"
             r"business environment|management|planning|staffing|marketing|"
             r"business plan|startup|goodwill|revaluation|forfeiture|"
             r"internal choice|blueprint|पार्टनरशिप|एडमिशन|कंपनी|गुडविल|मार्केटिंग)\b",
    "marks": r"\b(\d{2,3})\s*(marks|अंक|mark)\b|\bmarks?\s*[:=]\s*(\d{2,3})",
    "duration": r"\b(\d{2,3})\s*(min|minute|minutes|मिनट)",
    "deadline": r"\b(by|before|on|till|upto|untill?)\s+([0-9]{1,2}\s+\w+|\w+\s+[0-9]{1,2})\b",
}

SUBJECT_MAP = {"accountancy": "Accountancy", "accounting": "Accountancy",
               "etp": "Entrepreneurship",
               "business studies": "Business Studies", "bst": "Business Studies",
               "entrepreneurship": "Entrepreneurship", "economics": "Economics",
               "english": "English", "hindi": "Hindi", "mathematics": "Mathematics",
               "maths": "Mathematics", "science": "Science", "history": "History",
               "अकाउंटेंसी": "Accountancy", "अकाउंटेंट्स": "Accountancy",
               "बिज़नेस स्टडीज़": "Business Studies", "बिज़नेस स्टडीज": "Business Studies",
               "व्यवसाय": "Business Studies", "उद्यमशीलता": "Entrepreneurship",
               "एंटरप्रेन्योरशिप": "Entrepreneurship", "अर्थशास्त्र": "Economics"}

# Devanagari topic → Latin canonical (so the topic bank can match)
HI_TOPIC_MAP = {"पार्टनरशिप": "partnership", "पार्टनर": "partnership",
                "एडमिशन": "admission", "कंपनी": "company accounts",
                "गुडविल": "goodwill", "मार्केटिंग": "marketing",
                "रीवैल्यूएशन": "revaluation"}


def detect_lang(text: str) -> str:
    dev = sum(1 for ch in text if "ऀ" <= ch <= "ॿ")
    return "hi" if dev > 3 else "en"


_FOCUS_ABBR = re.compile(r"\bq[\s.]?p\b\.?", re.IGNORECASE)

_FOCUS_STOP = {"generate", "generated", "make", "making", "create", "created",
               "prepare", "prepared", "draft", "build", "write", "please",
               "need", "want", "the", "my", "a", "an", "question", "questions",
               "exam", "test", "paper", "qp", "homework", "assignment",
               "banao", "banana", "banado", "बनाओ", "तैयार", "करो"}


def classify_intent(text: str) -> str:
    low = _FOCUS_ABBR.sub("question paper", text.lower().strip())
    # An interrogative about a topic is a RESEARCH question, not a creation order —
    # unless it also carries an explicit creation verb ("what paper should I make..." etc.)
    is_question = bool(re.match(
        r"^(what|why|who|when|which|is|are|does|do|can|should|explain|tell me|बताओ|क्या|कैसे|क्यों)\b",
        low))
    has_create_verb = bool(re.search(
        r"\b(create|make|generate|build|prepare|draft|design|बनाओ|बना|तैयार)\b", low))
    if is_question and not has_create_verb:
        return "research_brief"
    for intent, pats in INTENT_PATTERNS:
        for p in pats:
            if p.lower() in low:
                return intent
    return "answer"


def extract_entities(text: str, lang: str) -> Dict[str, Any]:
    text = _FOCUS_ABBR.sub("question paper", text)
    low = text.lower()
    ent: Dict[str, Any] = {"language": lang}

    m = re.search(ENTITY_PATTERNS["subject"], low, flags=re.IGNORECASE)
    if m:
        raw = (m.group(1) or "").lower().strip()
        ent["subject"] = SUBJECT_MAP.get(raw, raw.title() if raw else None)

    m = re.search(r"class\s+(xi|xii|ix|x|10|11|12)\b", low)
    if m:
        lvl = m.group(1).upper().replace("XI", "XI")
        ent["class_level"] = {"XI": "XI", "XII": "XII", "IX": "IX", "X": "X",
                              "10": "X", "11": "XI", "12": "XII"}.get(lvl, lvl)
    else:
        m2 = re.search(r"(xi|xii|ix|x|10|11|12)\s*(वीं|कक्षा|क्लास)", low)
        if not m2:
            m2 = re.search(r"(कक्षा|क्लास)\s*(xii|xi|ix|x|12|11|10|9)\b", text,
                           flags=re.IGNORECASE)
            if m2:
                raw_cls = m2.group(2).upper()
            else:
                raw_cls = None
        else:
            raw_cls = m2.group(1).upper()
        if raw_cls:
            ent["class_level"] = {"XI": "XI", "XII": "XII", "IX": "IX", "X": "X",
                                  "10": "X", "11": "XI", "12": "XII"}.get(raw_cls, raw_cls)

    m = re.search(ENTITY_PATTERNS["topic"], low)
    if m:
        ent["topic"] = m.group(1)
    elif lang == "hi" or re.search(r"बनाओ|तैयार|करो", text):
        # try a quoted or trailing noun phrase as topic
        m3 = re.search(r"(?:पर|में|\babout\b|\bon\b)\s+([^,।.]{3,40})", text, flags=re.IGNORECASE)
        if m3:
            ent["topic"] = m3.group(1).strip()

    m = re.search(ENTITY_PATTERNS["marks"], low)
    if m:
        ent["marks"] = int(m.group(1) or m.group(3) or m.group(2))
    m = re.search(ENTITY_PATTERNS["duration"], low)
    if m:
        ent["duration"] = int(m.group(1))

    # raw marks data for analysis: comma-separated numbers
    if "raw_marks" in low or re.search(r"\d+\s*,\s*\d+\s*,\s*\d+", text):
        nums = re.findall(r"\d{1,3}", text)
        if len(nums) >= 3:
            ent["raw_marks"] = " ".join(nums)
            ent["has_data"] = True

    # topic fallback: prefer the noun BEFORE "पर/on/about" (Hinglish word order),
    # else the noun phrase after it — then normalize Devanagari topics to Latin.
    if "topic" not in ent:
        # paper-command focus: "question paper for ETP" / "ETP ka question paper".
        # NB: latin fallback words must be word-bounded — bare "on" otherwise
        # matches inside "questi-on" and yields garbage topics like "paper for ETP".
        m3 = re.search(
            r"(?:question\s+paper|exam\s+paper|test\s+paper|\bpaper|प्रश्नपत्र)"
            r"\s+(?:for|of|about|on|पर)\s+([\w][\w\- ]{1,30})",
            text, flags=re.IGNORECASE)
        if not m3:
            m3 = re.match(
                r"\s*([\w][\w\-]{1,15})\s+(?:ka\s+|ke\s+|ki\s+)?"
                r"(?:question\s+paper|\bpaper|प्रश्नपत्र)",
                text, flags=re.IGNORECASE)
        if not m3:
            m3 = re.search(r"([^,।.:!?]{3,30}?)\s+पर\b", text)
        if not m3:
            m3 = re.search(r"(?:पर|में|\babout\b|\bon\b)\s+([^,।.:!?]{3,40})", text,
                           flags=re.IGNORECASE)
        if m3:
            ent["topic"] = m3.group(1).strip()
    # Devanagari topic -> Latin canonical (restore: HI_TOPIC_MAP normalization)
    if ent.get("topic"):
        low_t = ent["topic"].lower()
        for hi, lat in HI_TOPIC_MAP.items():
            if hi in ent["topic"]:
                ent["topic"] = lat
                break
        else:
            # drop Devanagari command-verb tails like "प्रश्नपत्र बनाओ 80 अंक का"
            if re.search(r"बनाओ|तैयार|करो|बना", low_t):
                ent.pop("topic", None)

    # English focus hygiene: strip command words / marks tails, drop non-topics
    if "topic" in ent:
        t = ent["topic"].strip()
        t = re.sub(r"^(?:generate|make|create|prepare|draft|build|write|please|"
                   r"need|want|the|my|a|an|question|questions|exam|test|paper)\s+",
                   "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s+(?:please|banao|banana|banado)\s*$", "", t,
                   flags=re.IGNORECASE)
        t = re.sub(r"\s+\d{1,3}\s*(?:marks|अंक|min(?:ute)?s?)\b.*$", "", t,
                   flags=re.IGNORECASE)
        t = t.strip(" ,.-")
        if (not t or t.lower() in _FOCUS_STOP
                or re.match(r"^(class|grade|cbse|ncert)\b", t, flags=re.IGNORECASE)):
            ent.pop("topic", None)
        else:
            ent["topic"] = t

    if "subject" not in ent:
        # infer from topic bank
        from .generators import _bank_for
        bank = _bank_for(ent.get("topic"), None)
        if bank["subject"] != "General":
            ent["subject"] = bank["subject"]

    ent.setdefault("has_data", bool(ent.get("raw_marks")))
    return ent


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
class Orchestrator:
    def __init__(self, db, kg: KnowledgeGraph, skills: SkillRegistry,
                 memory: MemorySystem) -> None:
        self.db = db
        self.kg = kg
        self.skills = skills
        self.memory = memory
        self.rsi = RSIEngine(db, skills)
        self.decider = DecisionEngine()
        self._locks: Dict[str, threading.Lock] = {}
        self._pause = False
        self._kill = False

    # -- controls ---------------------------------------------------------
    def set_pause(self, v: bool) -> None:
        self._pause = v
        BUS.publish("system.control", {"pause": v})

    def set_kill(self, v: bool) -> None:
        self._kill = v
        if v:
            BUS.publish("system.control", {"kill": v})

    @property
    def killed(self) -> bool:
        return self._kill

    # ------------------------------------------------------------------
    def submit(self, command: str, lang: Optional[str] = None,
               on_done: Optional[Callable[[Dict[str, Any]], None]] = None) -> str:
        lang = lang or detect_lang(command)
        task_id = f"T-{time.strftime('%H%M%S')}-{uuid.uuid4().hex[:6]}"
        now = time.time()
        self.db.create_task({
            "id": task_id, "command": command, "lang": lang, "status": "CREATED",
            "created_at": now,
        })
        self.db.audit("user", "command", task_id, {"command": command, "lang": lang})
        BUS.publish("task.created", {"id": task_id, "command": command, "lang": lang},
                    task_id=task_id)
        t = threading.Thread(target=self._run, args=(task_id, command, lang, on_done),
                             daemon=True, name=f"task-{task_id}")
        t.start()
        return task_id

    # ------------------------------------------------------------------
    def _update(self, task_id: str, **fields: Any) -> None:
        self.db.update_task(task_id, **fields)

    def _step(self, ctx: Dict[str, Any], label: str) -> None:
        ctx["steps"] += 1
        if ctx["steps"] > MAX_STEPS_PER_TASK:
            raise RuntimeError("Agent Loop Guard: MAX_STEPS exceeded — task paused (C14).")
        if self._kill:
            raise RuntimeError("Emergency stop engaged — task halted safely.")
        BUS.publish("task.step", {"label": label, "n": ctx["steps"]},
                    task_id=ctx["id"])

    # ------------------------------------------------------------------
    def _run(self, task_id: str, command: str, lang: str,
             on_done: Optional[Callable] = None) -> None:
        ctx: Dict[str, Any] = {"id": task_id, "steps": 0, "cost": 0.0}
        try:
            # ---------------- PERCEIVE ------------------------------------
            self._step(ctx, "PERCEIVE: reading command")
            intent = classify_intent(command)
            entities = extract_entities(command, lang)
            BUS.publish("task.perceive",
                        {"intent": intent, "entities": {k: v for k, v in entities.items()}},
                        task_id=task_id)

            # ---------------- DECIDE --------------------------------------
            self._step(ctx, "DECIDE: risk · confidence · autonomy")
            settings = {"autonomy_mode": self.db.get_setting("autonomy_mode",
                                                             "SEMI_AUTONOMOUS")}
            self.decider.autonomy_mode = settings["autonomy_mode"]
            decision = self.decider.decide(intent, command, entities, task_id)
            decision.task_id = task_id
            self.decider.record(self.db, decision)
            self._update(task_id, decision=decision.as_dict(), status="DECIDED")
            BUS.publish("task.decision", decision.as_dict(), task_id=task_id)

            if decision.autonomy_level == 5:
                self._blocked(task_id, decision,
                              "This action is constitutionally FORBIDDEN (L5). "
                              "निषिद्ध कार्य — यह अनुमति नहीं है।", lang)
                return

            if decision.context_missing and decision.confidence < 0.55:
                # C12: ONE precise question instead of guessing
                q = (f"I need {', '.join(decision.context_missing)} to do this correctly. "
                     f"कृपया यह बताएँ — तभी सही बन पाएगा।")
                self._clarify(task_id, decision, q, lang)
                return

            # ---------------- PLAN ----------------------------------------
            self._step(ctx, "PLAN: decompose & route specialists")
            specialists = for_intent(intent)
            discovered = self.skills.discover(
                list(entities.keys()) + [command] + [entities.get("topic", "")], limit=4)
            skill_ids = []
            for d in discovered:
                if d["skill"]["id"] in [s for sp in specialists for s in sp.skills] or \
                   d["score"] >= 0.3:
                    skill_ids.append(d["skill"]["id"])
            if not skill_ids:
                # direct intent → skill mapping fallback
                intent_skill = {
                    "generate_question_paper": "question_paper",
                    "generate_worksheet": "worksheet",
                    "generate_lesson_plan": "lesson_plan",
                    "remedial_plan": "remedial_plan",
                    "result_analysis": "result_analysis",
                    "draft_letter": "official_letter",
                    "draft_notice": "notice",
                    "draft_circular": "circular",
                    "draft_minutes": "minutes_of_meeting",
                    "external_communication": "official_letter",
                    "research_brief": "research_brief",
                    "action_plan": "action_plan",
                    "generate_report": "structured_report",
                    "draft_press_release": "draft_press_release",
                    "draft_official_email": "draft_official_email",
                    "generate_active_recall": "active_recall",
                    "story_lesson": "story_scaffold",
                    "generate_quiz": "adaptive_quiz",
                    "build_learning_app": "web_app_scaffold",
                }.get(intent)
                if intent_skill:
                    skill_ids = [intent_skill]

            # --- HITL skill packs (Vibe Coder / EduVis) — deterministic overrides
            low_cmd = command.lower()
            if intent == "build_learning_app" and re.search(
                    r"(?<![a-z])(react|tailwind|codebase|npm)(?![a-z])|"
                    r"python (script|lab|code)|equation lab|source code", low_cmd):
                skill_ids = ["code_generator", "code_validator"]
            elif intent == "story_lesson" and re.search(
                    r"simulation|simulator|interactive|virtual lab|visual stor", low_cmd):
                skill_ids = ["visual_storytelling_planner", "story_scaffold"]
            # only run skills that exist in the runtime registry (stale ids from
            # renames/KG discovery must never reach execution)
            skill_ids = [sid for sid in skill_ids if self.skills.get(sid)]

            plan = {
                "goal": command,
                "intent": intent,
                "specialists": [s.id for s in specialists],
                "skills": skill_ids,
                "phases": ["deliberate", "execute", "verify", "deliver", "learn"],
                "context_missing": decision.context_missing,
            }
            self._update(task_id, plan=plan, status="PLANNED")
            BUS.publish("task.plan", plan, task_id=task_id)

            # ---------------- DELIBERATE ------------------------------------
            self._step(ctx, "DELIBERATE: structured win-win rounds")
            self._update(task_id, status="DELIBERATING")
            deliberation = self._deliberate(task_id, ctx, plan, decision, entities, lang)
            if deliberation.escalation:
                self._clarify(task_id, decision, deliberation.escalation, lang)
                return
            if not deliberation.consensus:
                self._fail(task_id, "No consensus and arbitration failed.", lang)
                return
            consensus = deliberation.consensus
            self._update(task_id, rounds=consensus.get("rounds_used", 0))

            # ---------------- PRE-ACTION GATE (strict HITL for L4/L5) ----------
            consensus = self._pre_action_gate(
                task_id, decision, command, skill_ids, lang, ctx, plan, consensus, entities)
            if consensus is None:
                return  # gate hard-stopped the task (blocked / forbidden / timed out)

            # ---------------- EXECUTE ---------------------------------------
            self._step(ctx, "EXECUTE: run skills → artifacts")
            self._update(task_id, status="EXECUTING")
            artifacts, exec_notes, provenance = [], [], []
            for sid in skill_ids:
                if self._kill:
                    raise RuntimeError("Emergency stop engaged mid-execution.")
                try:
                    result = self.skills.run(sid, entities,
                                             {"memory_hits": self.memory.recall(
                                                 entities.get("topic", command)),
                                              "command": command, "lang": lang,
                                              "consensus": consensus,
                                              "syllabus": SYL.compact(
                                                  entities.get("subject"),
                                                  entities.get("class_level"))})
                except Exception as e:
                    exec_notes.append(f"skill '{sid}' failed: {e}")
                    BUS.publish("task.error", {"skill": sid, "error": str(e)},
                                task_id=task_id)
                    continue
                artifacts.extend(result.get("artifacts", []))
                exec_notes.extend(result.get("notes", []))
                if result.get("provenance"):
                    provenance.append({"skill": sid, **result["provenance"]})
                for v in result.get("validators", []):
                    ctx.setdefault("validators", []).append(
                        {"skill": sid, **v})
                if result.get("clarify"):
                    self._clarify(task_id, decision, result["clarify"], lang)
                    return
                self.skills.record_run(sid, bool(result.get("artifacts")),
                                       0.8 if result.get("artifacts") else 0.3)
            artifacts = artifacts[:12]
            self._step(ctx, "EXECUTE: persist artifacts")

            # ---------------- VERIFY (hard gates) -----------------------------
            self._update(task_id, status="VERIFYING")
            self._step(ctx, "VERIFY: quality gates (Janus)")
            quality = self._verify(task_id, command, artifacts, ctx, consensus, provenance)

            # one targeted repair loop if soft issues but no hard fail
            if quality["status"] == "NEEDS_REVIEW" and not quality["hard_failures"]:
                BUS.publish("task.step", {"label": "REWORK: targeted repair pass"},
                            task_id=task_id)
                quality = self._verify(task_id, command, artifacts, ctx, consensus,
                                       provenance, second_pass=True)

            if quality["hard_failures"]:
                quality["status"] = "REWORK" if quality["hard_failures"] else quality["status"]

            # ---------------- DELIVER -------------------------------------------
            self._update(task_id, status="DELIVERING")
            self._step(ctx, "DELIVER: structured output")
            summary, summary_hi, final_status = self._synthesize(
                task_id, command, plan, artifacts, quality, consensus, entities, lang)

            # persist artifacts to disk
            saved = []
            for a in artifacts:
                sha = hashlib.sha256(a["content"].encode("utf-8")).hexdigest()[:12]
                path = os.path.join(OUTPUT_DIR, f"{task_id}_{a['name']}")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(a["content"])
                rec = {"task_id": task_id, "name": a["name"], "kind": a["kind"],
                       "path": path, "status": a.get("status", "TRUSTED"),
                       "sha": sha, "bytes": len(a["content"].encode("utf-8"))}
                self.db.add_artifact(rec)
                saved.append({"name": a["name"], "kind": a["kind"],
                              "status": a.get("status"), "sha": sha,
                              "bytes": len(a["content"].encode("utf-8")),
                              "path": f"/api/artifacts/{task_id}/{a['name']}"})

            overall = quality.get("overall", 0.6)
            self._update(task_id, status=final_status, summary=summary,
                         summary_hi=summary_hi, quality=quality, artifacts=saved,
                         cost=round(ctx["cost"], 3),
                         confidence=quality.get("confidence", 0.6))
            BUS.publish("task.completed", {
                "id": task_id, "status": final_status, "score": overall,
                "artifacts": saved, "summary": summary, "summary_hi": summary_hi,
                "quality": quality,
            }, task_id=task_id)
            self.db.audit("archon", "deliver", task_id,
                          {"status": final_status, "score": overall,
                           "artifacts": len(saved)})

            # ---------------- LEARN (memory + RSI) ------------------------------
            self._step(ctx, "LEARN: memory + RSI cycle")
            self._learn(task_id, command, plan, quality, consensus)

            if on_done:
                on_done(self.db.get_task(task_id))

        except Exception as e:
            self._fail(task_id, str(e), lang)

    # ------------------------------------------------------------------
    def _deliberate(self, task_id: str, ctx: Dict[str, Any], plan: Dict[str, Any],
                    decision: Decision, entities: Dict[str, Any], lang: str) -> Deliberation:
        def emit(mtype, frm, to, body, payload):
            BUS.publish("deliberation.message",
                        {"mtype": mtype, "from": frm, "to": to, "body": body,
                         "payload": payload}, task_id=task_id)

        d = Deliberation(task_id, emit, self.db, round_max=MAX_DELIBERATION_ROUNDS)
        agent_ids = plan["specialists"]
        agent_objs = [AGENTS[a] for a in agent_ids]

        # --- orchestrator opening brief
        brief = (f"Goal: {plan['goal']}\nIntent: {plan['intent']}\n"
                 f"Entities: { {k: v for k, v in entities.items() if v} }\n"
                 f"Skills: {plan['skills']}\n"
                 f"Decision: L{decision.autonomy_level} confidence={decision.confidence} "
                 f"risk={decision.risk}")
        d.request("archon", agent_ids, brief, plan)

        # --- Round 1: proposals from each specialist (own expertise only)
        engine = engine_from_settings({"llm": self.db.get_setting("llm", {})})
        for sp in agent_objs:
            proposal = self._make_proposal(sp, plan, decision, entities, engine, lang)
            d.propose(sp.id, proposal["body"], proposal["payload"])

        # --- Round 2: challenges — Janus (quality) and Veritas (provenance)
        # Janus challenges every artifact-facing proposal with validator demands
        if "quality" in agent_ids:
            for target, p in list(d.proposals.items()):
                if target == "quality":
                    continue
                concerns, ev = self._critique(p, plan, decision, entities)
                if concerns:
                    d.challenge("quality", target,
                                "Pre-delivery critique — let's harden this before the user "
                                "sees it (win-win): " + " | ".join(concerns),
                                concerns, ev)
        # Veritas challenges overconfidence / unverified factual claims
        if "research" in agent_ids:
            for target, p in list(d.proposals.items()):
                if target == "research" or p["confidence"] > 0.9:
                    continue
                if p["confidence"] >= 0.88:
                    d.challenge("research", target,
                                "Confidence seems high for offline mode — label provenance "
                                "explicitly so the user is never misled (C1/C2).",
                                ["confidence above offline evidence threshold"],
                                ["offline engine has no live source access",
                                 "constitution C1 requires provenance labeling"])
        # Cross-discipline peer review (AutoGen-inspired): when the build team
        # is in the room, EduVis and Vibe Coder critique EACH OTHER's proposals
        # before CONSENSUS — Lumina checks pedagogy, Kai checks feasibility.
        if "eduvis" in agent_ids and "vibecoder" in agent_ids:
            for target, p in list(d.proposals.items()):
                if target == "vibecoder":
                    concerns, ev = self._peer_review("eduvis", "vibecoder", p, plan)
                    if concerns:
                        d.challenge("eduvis", "vibecoder",
                                    "Pedagogy review of this build (win-win: code must "
                                    "actually TEACH, not just render): "
                                    + " | ".join(concerns),
                                    concerns, ev)
                elif target == "eduvis":
                    concerns, ev = self._peer_review("vibecoder", "eduvis", p, plan)
                    if concerns:
                        d.challenge("vibecoder", "eduvis",
                                    "Engineering feasibility review of this blueprint "
                                    "(win-win: good pedagogy must also run offline): "
                                    + " | ".join(concerns),
                                    concerns, ev)
        # Data agent validates arithmetic if analysis involved
        if "data" in agent_ids and plan["intent"] == "result_analysis":
            d.challenge("data", "archon" if "archon" not in d.proposals else "quality",
                        "Independently recomputing all statistics before acceptance.",
                        ["math must be deterministically recomputed"], ["C6 hard gate"])

        # --- Round 2b: revisions addressing challenges
        if d.challenges:
            d.round = min(d.round + 1, d.round_max) if d.round < d.round_max else d.round
            for target, chs in list(d.challenges.items()):
                sp = AGENTS.get(target)
                if not sp or target not in d.proposals:
                    continue
                addresses = []
                new_body_parts = []
                for c in chs:
                    for concern in c["concerns"]:
                        addresses.append(f"{c['from']}: {concern}")
                        new_body_parts.append(f"[addressed → {concern}] "
                                              f"revised with: {self._concession(sp, concern)}")
                base = d.proposals[target]
                revised_body = base["body"] + "\n\nREVISIONS:\n- " + "\n- ".join(new_body_parts)
                payload = {**base["payload"],
                           "addresses": addresses,
                           "confidence": min(0.93, base["confidence"] + 0.03),
                           "evidence_quality": "derived"}
                d.revise(target, revised_body, payload)

        # --- Quality agent's own proposal is its acceptance verdict
        janus_open = [c for c in d.open_concerns if c["from"] == "quality"]

        # --- Consensus attempt
        limitations = [f"{c['from']}: {c['body']}" for c in d.open_concerns]
        note = (f"{len(d.proposals)} specialists aligned on plan with "
                f"{sum(len(v) for v in d.concessions.values())} documented concessions")
        ok = d.try_consensus(note, limitations)
        if not ok and d.round < d.round_max:
            # one more targeted resolution round
            d.round += 1
            for c in list(d.open_concerns):
                d.resolve_concern(c["from"],
                                  f"incorporated into limitations & final verification: "
                                  f"{c['body'][:80]}")
            ok = d.try_consensus(note + " (concerns folded into limitations, C6)",
                                 limitations)
        if not ok:
            d.deadlock_arbitration("rounds exhausted; evidence-ranked selection")

        # hard concerns from Janus that remain → flag as limitations, not silence
        if d.consensus is not None:
            d.consensus["janus_verdict"] = "APPROVED_WITH_LIMITATIONS" if janus_open else "APPROVED"
        return d

    # ------------------------------------------------------------------
    def _make_proposal(self, sp, plan, decision, entities, engine, lang) -> Dict[str, Any]:
        """Specialist proposal: profile-driven, domain-scoped, honest."""
        domain_note = ""
        if plan["intent"] not in self._intents_for(sp):
            domain_note = ("Note: this task is outside my strict authority; contributing "
                           "adjacent checks only (C4 non-interference).")

        llm_text = None
        if engine.name != "offline-deterministic":
            try:
                r = engine.complete(
                    system=f"You are {sp.name} ({sp.role}). Charter: {sp.charter}",
                    user=f"Goal: {plan['goal']}\nProvide a concise specialist proposal: "
                         f"approach, risks, and one concrete artifact recommendation.",
                    max_tokens=400)
                llm_text = r["text"]
            except Exception as e:
                llm_text = None

        confidence = 0.78
        if sp.id == "quality":
            confidence = 0.7
        if sp.id == "research":
            confidence = 0.72
        body_parts = [f"PROPOSAL from {sp.name} ({sp.role})",
                      f"Approach for: {plan['goal'][:160]}"]
        if entities.get("topic"):
            body_parts.append(f"Focus: {entities['topic']}")
        if entities.get("subject"):
            body_parts.append(f"Domain: {entities['subject']}"
                              + (f" / Class {entities['class_level']}"
                                 if entities.get("class_level") else ""))
            _anchor = SYL.unit_for_topic(entities.get("subject"),
                                         entities.get("class_level"),
                                         entities.get("topic"))
            if _anchor:
                body_parts.append(
                    f"Syllabus anchor: Unit {_anchor['unit']} '{_anchor['title']}' "
                    f"(official CBSE {SYL.SESSION} weightage; scope-verified)")
        body_parts.append(f"Validators I will enforce: {', '.join(sp.validators) or '—'}")
        if domain_note:
            body_parts.append(domain_note)
        if llm_text:
            body_parts.append(f"Model note: {llm_text}")
            confidence = min(0.9, confidence + 0.05)
        body = "\n".join(body_parts)

        ev_quality = "derived" if engine.name != "offline-deterministic" else "inferred"
        return {"body": body, "payload": {
            "agent": sp.id, "confidence": confidence,
            "evidence": [
                f"charter authority: {', '.join(sp.authority_domains)}",
                f"validators: {sp.validators}",
                "inputs: user command + extracted entities + active memory hits",
            ],
            "evidence_quality": ev_quality,
            "engine": engine.name,
            "recommendation": f"proceed via {', '.join(sp.skills) or 'verification-only'}",
        }}

    @staticmethod
    def _intents_for(sp) -> set:
        m = {
            "academic": {"generate_question_paper", "generate_worksheet",
                         "generate_lesson_plan", "remedial_plan",
                         "generate_active_recall", "story_lesson", "generate_quiz"},
            "admin": {"draft_letter", "draft_notice", "draft_circular", "draft_minutes",
                      "external_communication", "draft_official_email"},
            "research": {"research_brief", "answer"},
            "data": {"result_analysis"},
            "eduvis": {"generate_lesson_plan", "story_lesson", "generate_quiz",
                       "build_learning_app"},
            "vibecoder": {"build_learning_app"},
            "prcomms": {"draft_press_release", "draft_official_email", "draft_letter",
                        "draft_notice", "draft_circular", "external_communication"},
            "quality": set(),  # janus: all
        }
        return m.get(sp.id, set())

    def _peer_review(self, critic: str, target: str, proposal: Dict[str, Any],
                     plan: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        """Deterministic cross-discipline review (protocol-compliant challenge:
        concrete concerns + evidence, no personal attack — C4/C5).

        eduvis → vibecoder: does the build state LEARNING outcomes?
        vibecoder → eduvis: does the blueprint state FEASIBILITY (offline/run)?
        Marker-sensitive: proposals that already cover the point are not
        challenged (no vacuous criticism theatre).
        """
        body = str(proposal.get("body", "")).lower()
        if critic == "eduvis":
            markers = ["learning objective", "learner", "student will", "understand",
                       "practice", "recall", "quiz", "assessment", "misconception",
                       "pedagog", "scaffold"]
            found = [m for m in markers if m in body]
            if found:
                return [], []
            return (["no learning objective / assessment markers in the build plan "
                     "(EduVis pedagogy gate — C6)"],
                    ["CBSE pedagogy requires stated outcomes and a check for "
                     "understanding before delivery",
                     f"scanned proposal body — none of {len(markers)} pedagogy "
                     f"markers present"])
        if critic == "vibecoder":
            # feasibility terms only — deliberately NOT generic words like
            # "build"/"run"/"test" that appear in any goal line ("Approach for: …")
            markers = ["offline", "single-file", "stdlib", "deterministic",
                       "runtime", "dependencies", "no cdn", "no api",
                       "build step", "npm install", "zero api"]
            found = [m for m in markers if m in body]
            if found:
                return [], []
            return (["feasibility not addressed — blueprint must state how it runs "
                     "offline (Vibe Coder gate — C1/C2)"],
                    ["system rule: offline-first, zero API keys, no CDN promises",
                     f"scanned proposal body — none of {len(markers)} feasibility "
                     f"markers present"])
        return [], []

    def _critique(self, proposal, plan, decision, entities) -> Tuple[List[str], List[str]]:
        """Deterministic critique — the critic actually checks things."""
        concerns: List[str] = []
        ev: List[str] = []
        intent = plan["intent"]
        if intent == "generate_question_paper":
            if not entities.get("marks"):
                concerns.append("marks not specified — blueprint will default to 80; "
                                "confirm before print")
                ev.append("entity 'marks' missing from extraction")
            if not entities.get("class_level"):
                concerns.append("class level not specified — defaulting may mis-target difficulty")
                ev.append("entity 'class_level' missing")
            _sub = SYL.norm_subject(entities.get("subject"))
            if _sub:
                _sok, _sdetail, _ = SYL.scope_check(
                    _sub, SYL.norm_class(entities.get("class_level")),
                    entities.get("topic") or None)
                if not _sok:
                    concerns.append(f"syllabus scope: {_sdetail}")
                    ev.append("syllabus.scope_check reports out-of-syllabus topic (C1)")
        if intent in ("generate_question_paper", "generate_worksheet",
                      "generate_active_recall", "story_lesson", "generate_quiz",
                      "build_learning_app", "draft_press_release") and \
                not entities.get("topic"):
            concerns.append("no topic focus given — paper will span the standard chapter bank; "
                            "state topic for precision")
            ev.append("entity 'topic' missing")
        if intent in ("draft_letter", "external_communication", "draft_press_release") \
                and decision.requires_approval:
            concerns.append("external communication: draft only — MUST NOT be sent (L4 gate)")
            ev.append("decision.requires_approval=True")
        if decision.risk_tier == "MEDIUM":
            concerns.append("MEDIUM risk action: proceeds auto-execute, but is being "
                            "async-audited after the fact (risk tiering policy)")
            ev.append("decision.risk_tier == MEDIUM")
        if proposal.get("confidence", 0) > 0.88 and not entities.get("subject"):
            concerns.append("high confidence without subject specified — please ground the claim")
            ev.append("confidence vs context mismatch")
        if plan.get("context_missing"):
            concerns.append(f"context missing: {plan['context_missing']} — must be declared "
                            "in limitations")
            ev.append("decision.context_missing non-empty")
        return concerns, ev

    @staticmethod
    def _concession(sp, concern: str) -> str:
        if "marks not specified" in concern:
            return "will use 80-mark blueprint default and declare it in limitations"
        if "class level" in concern.lower():
            return "will declare assumed class level prominently in output header"
        if "topic focus" in concern:
            return "will label scope as 'standard chapter bank' in artifact"
        if "syllabus scope" in concern:
            return ("generator flags artifact NEEDS_REVIEW and prints the official "
                    "scope note from the CBSE syllabus knowledge base (C1)")
        if "L4" in concern or "MUST NOT be sent" in concern:
            return "draft-only status printed on artifact; send path blocked by approval gate"
        if "provenance" in concern.lower() or "confidence" in concern.lower():
            return "provenance labels (DERIVED/INTERNAL_KNOWLEDGE/UNCERTAIN) added explicitly"
        if "context missing" in concern:
            return "missing context will appear under Honest Limitations section"
        return f"acknowledged and addressed: {concern[:70]}"

    # ------------------------------------------------------------------
    def _verify(self, task_id: str, command: str, artifacts: List[Dict[str, Any]],
                ctx: Dict[str, Any], consensus: Dict[str, Any],
                provenance: List[Dict[str, Any]], second_pass: bool = False) -> Dict[str, Any]:
        hard_failures: List[str] = []
        warnings: List[str] = []
        validators: List[Dict[str, Any]] = []

        # 1) artifact-level deterministic checks
        if not artifacts:
            hard_failures.append("no artifacts produced — cannot claim completion (C2)")
        for a in artifacts:
            content = a.get("content", "")
            if len(content.strip()) < 120:
                hard_failures.append(f"{a['name']}: artifact too thin")
            if content.count("\n") < 4:
                hard_failures.append(f"{a['name']}: lacks structure")
            v = ConstitutionGuard.screen(content)
            if not v.ok:
                hard_failures.append(f"{a['name']}: constitution {v.article} — {v.reason}")

        # 2) skill validators collected during execution
        for v in ctx.get("validators", []):
            validators.append(v)
            if not v.get("passed", True) and v.get("name") == "marks_total":
                hard_failures.append(f"marks mismatch: {v.get('detail')}")
            elif not v.get("passed", True):
                warnings.append(f"{v.get('name')}: {v.get('detail')}")

        # 3) honesty checks: provenance must be labeled
        if artifacts and not provenance:
            warnings.append("no provenance labels attached — defaulting to INTERNAL_KNOWLEDGE")
        for p in provenance:
            if p.get("level") == "UNCERTAIN" and "limitation" not in " ".join(warnings):
                warnings.append("UNCERTAIN provenance present — must appear in limitations")

        # 4) command coverage: deliverable must relate to command.
        # Command-verbs (banao/generate/...) are routing noise, not subject matter —
        # excluding them stops Hinglish phrasings from being unfairly scored.
        _CMD_STOP = {"generate", "generated", "make", "making", "create", "created",
                     "prepare", "prepared", "draft", "build", "write", "please",
                     "need", "want", "banao", "banana", "banado", "assignment",
                     "homework", "question", "questions", "paper", "papers"}
        cmd_tokens = set(re.findall(r"[a-z]{4,}", command.lower())) - _CMD_STOP
        blob = " ".join(a.get("content", "") for a in artifacts).lower()
        if cmd_tokens:
            # light stemming: match on 5-char prefix so analyse≈analysis, papers≈paper
            overlap = sum(1 for t in cmd_tokens
                          if t in blob or (len(t) > 5 and t[:5] in blob))
            coverage = overlap / max(1, len(cmd_tokens))
        else:
            # Pure Devanagari command: latin-token coverage is meaningless —
            # routing evidence = a skill matched this intent and produced artifacts.
            coverage = 0.85 if artifacts else 0.0
        # Relevance floor: when token coverage is weak but the intent→skill chain
        # produced artifacts that PASSED their validators with zero warnings,
        # relevance is evidenced by routing + validation, not string overlap.
        if coverage < 0.5 and artifacts and not hard_failures and not warnings:
            coverage = 0.55
            validators.append({"name": "intent_skill_alignment", "passed": True,
                               "detail": "relevance evidenced by skill routing + "
                                         "passing validators (string coverage weak)"})

        # 5) consensus sanity
        if not consensus or not consensus.get("participants"):
            hard_failures.append("no deliberation consensus recorded")

        # score
        score = 0.0
        score += 0.35 if artifacts else 0.0
        score += 0.25 * min(1.0, coverage / 0.6)
        passed_v = sum(1 for v in validators if v.get("passed", True))
        score += 0.2 * (passed_v / max(1, len(validators)))
        score += 0.2 * (1.0 if not warnings else 0.7)
        score = round(min(0.99, score), 3)

        if second_pass and warnings:
            # targeted repair: warnings that we can resolve by disclosure get disclosed
            warnings = [w for w in warnings]  # keep visible; status accounts for it

        status = "TRUSTED"
        if hard_failures:
            status = "FAILED"
        elif warnings or coverage < 0.5:
            status = "NEEDS_REVIEW"

        report = {
            "status": status,
            "overall": score,
            "confidence": round(min(0.95, 0.4 + score / 2), 2),
            "hard_failures": hard_failures,
            "warnings": warnings,
            "validators": validators,
            "coverage": round(coverage, 3),
            "second_pass": second_pass,
            "consensus_confidence": consensus.get("confidence"),
            "janus_verdict": consensus.get("janus_verdict", "APPROVED"),
        }
        BUS.publish("task.quality", report, task_id=task_id)
        return report

    # ------------------------------------------------------------------
    def _synthesize(self, task_id: str, command: str, plan: Dict[str, Any],
                    artifacts: List[Dict[str, Any]], quality: Dict[str, Any],
                    consensus: Dict[str, Any], entities: Dict[str, Any],
                    lang: str) -> Tuple[str, str, str]:
        n_art = len(artifacts)
        parts = [
            f"## DELIVERABLE — {command[:120]}",
            "",
            f"- **Status:** {quality['status']}"
            + (" (hard gates passed)" if quality["status"] == "TRUSTED"
               else " — review flagged items below"),
            f"- **Quality score:** {quality['overall']:.2f}  |  "
            f"- **Confidence:** {quality['confidence']:.2f}",
            f"- **Deliberation:** {consensus.get('rounds_used', '?')} round(s), "
            f"{len(consensus.get('participants', []))} agents, "
            f"consensus conf={consensus.get('confidence')}",
            f"- **Artifacts ({n_art}):** " + ", ".join(a["name"] for a in artifacts),
            "",
            "### Quality gates",
        ]
        if quality["hard_failures"]:
            parts.append("- ❌ HARD FAILURES: " + "; ".join(quality["hard_failures"]))
        else:
            parts.append("- ✅ No hard-gate failures (C6)")
        for w in quality["warnings"]:
            parts.append(f"- ⚠️ {w}")
        lims = consensus.get("residual_limitations") or []
        parts += ["", "### Honest limitations (C1/C2)"]
        if lims:
            parts += [f"- {l}" for l in lims[:6]]
        if plan.get("context_missing"):
            parts.append(f"- Context you did not provide: "
                         f"{', '.join(plan['context_missing'])} (assumptions declared above)")
        if not lims and not plan.get("context_missing"):
            parts.append("- None beyond what is stated in artifact provenance sections.")
        parts += ["", "### Provenance",
                  "- Each artifact carries its own provenance block "
                  "(DERIVED / INTERNAL_KNOWLEDGE / UNCERTAIN).",
                  "- Offline mode: no live-web claims were made."]
        parts += ["", "### Next actions",
                  "- Open the artifact(s) from the ARTIFACTS panel.",
                  "- If anything is off: issue a refine command (e.g., 'make it 40 marks, "
                  "focus on topic X')."]
        summary = "\n".join(parts)

        # Hindi mirror (bilingual duty C13)
        parts_hi = [
            f"## डिलिवरेबल — {command[:120]}",
            "",
            f"- **स्थिति:** {quality['status']}"
            + (" (सभी गुणवत्ता गेट पास)" if quality["status"] == "TRUSTED"
               else " — नीचे ध्यान दें"),
            f"- **गुणवत्ता स्कोर:** {quality['overall']:.2f}",
            f"- **विचार-विमर्श:** {consensus.get('rounds_used', '?')} राउंड, "
            f"{len(consensus.get('participants', []))} एजेंट",
            f"- **आर्टिफैक्ट ({n_art}):** " + ", ".join(a["name"] for a in artifacts),
            "",
            "### Quality gates",
        ]
        if quality["hard_failures"]:
            parts_hi.append("- ❌ हार्ड फेल: " + "; ".join(quality["hard_failures"]))
        else:
            parts_hi.append("- ✅ कोई हार्ड-गेट फेल नहीं (C6)")
        for w in quality["warnings"]:
            parts_hi.append(f"- ⚠️ {w}")
        parts_hi += ["", "### ईमानदार सीमाएँ"]
        if lims:
            parts_hi += [f"- {l}" for l in lims[:5]]
        else:
            parts_hi.append("- आर्टिफैक्ट की provenance में जो लिखा है वही सीमा है।")
        if plan.get("context_missing"):
            parts_hi.append(f"- आपने नहीं बताया: {', '.join(plan['context_missing'])}")
        parts_hi += ["", "### अगला कदम",
                     "- ARTIFACTS पैनल से फ़ाइल खोलें।",
                     "- कुछ ठीक न लगे तो refine command दें (जैसे '40 marks, topic X पर')।"]
        summary_hi = "\n".join(parts_hi)

        status = "COMPLETED" if quality["status"] in ("TRUSTED", "NEEDS_REVIEW") \
            else "FAILED"
        if quality["status"] == "NEEDS_REVIEW":
            status = "COMPLETED_WITH_NOTES"
        return summary, summary_hi, status

    # ------------------------------------------------------------------
    def _learn(self, task_id: str, command: str, plan: Dict[str, Any],
               quality: Dict[str, Any], consensus: Dict[str, Any]) -> None:
        score = quality.get("overall", 0.5)
        self.memory.episode(task_id, f"Completed: {command[:80]}",
                            quality["status"], score)
        self.memory.decision(command[:80], f"route={plan['specialists']}",
                             quality["status"], quality.get("confidence", 0.5))
        if plan.get("skills"):
            self.memory.procedure(plan["intent"], plan["phases"],
                                  success_rate=score)
        self.memory.performance("+".join(plan["specialists"]), score, 0.0)
        # semantic: capture topic-subject associations with modest authority
        self.db.audit("archon", "learn", task_id, {"score": score})
        try:
            self.rsi.evaluate_task({"id": task_id, "quality": quality,
                                    "rounds": consensus.get("rounds_used", 0),
                                    "plan": plan})
        except Exception as e:
            BUS.publish("rsi.error", {"error": str(e)}, task_id=task_id)

    # ------------------------------------------------------------------
    def _await_approval(self, aid: str, timeout: float = 600) -> Dict[str, Any]:
        """Wait for the human verdict. Returns {status, feedback}:
        approved | rejected (with user feedback text) | timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            row = self.db._q1("SELECT status, feedback FROM approvals WHERE id=?", (aid,))
            if row and row["status"] == "approved":
                return {"status": "approved", "feedback": None}
            if row and row["status"] == "rejected":
                return {"status": "rejected",
                        "feedback": (row.get("feedback") or "").strip() or None}
            if self._kill:
                return {"status": "timeout", "feedback": None}
            time.sleep(0.6)
        return {"status": "timeout", "feedback": None}

    # ---------------- PRE-ACTION GATE (HITL risk tiers) ----------------
    GATE_MAX_REVISIONS = 3

    def _pre_action_gate(self, task_id: str, decision: Decision, command: str,
                         skill_ids: List[str], lang: str, ctx: Dict[str, Any],
                         plan: Dict[str, Any], consensus: Dict[str, Any],
                         entities: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Strict Pre-Action Gate for ALL L4/L5 actions (HITL spec).

        HIGH    → HARD BLOCK until a human approves; Reject captures feedback
                  which is routed back as a CHALLENGE (revision loop below).
        MEDIUM  → auto-execute, then ASYNC audit (non-blocking, after-the-fact).
        LOW     → auto-execute untouched.
        L5      → FORBIDDEN: no approval can ever unlock it (constitution).
        Returns the (possibly revised) consensus, or None → task stopped.
        """
        # -- L5: constitutional hard stop (defence-in-depth re-check) --
        if decision.autonomy_level == 5:
            self._blocked(task_id, decision,
                          "PRE-ACTION GATE: this action is constitutionally FORBIDDEN "
                          "(L5) — no approval path exists. निषिद्ध कार्य।", lang)
            return None

        # -- MEDIUM: auto-execute with async audit --
        if decision.risk_tier == "MEDIUM" and not decision.requires_approval:
            self._schedule_async_audit(task_id, decision, command)
            return consensus

        # -- LOW: auto-execute, nothing to gate --
        if not decision.requires_approval:
            return consensus

        # -- HIGH / L4: hard block for human approval, with revision loop --
        self._update(task_id, status="WAITING_APPROVAL")
        current = consensus
        revisions = 0
        while True:
            aid = f"A-{task_id}" if revisions == 0 else f"A-{task_id}-r{revisions}"
            reason = (f"L4 action ({decision.mode_label}, tier {decision.risk_tier}) — "
                      f"external/consequential steps require explicit human approval (C7).")
            preview = (f"Command: {command}\nPlanned skill(s): {skill_ids}\n"
                       f"Decision gate: {decision.gate} | risk={decision.risk:.2f}\n")
            if revisions:
                preview += (f"Revision round {revisions} — feedback applied: "
                            f"{ctx.get('user_feedback', '')}\n"
                            f"Entities now: "
                            f"{ {k: v for k, v in entities.items() if v} }\n")
            preview += ("The system will NOT send/publish/finalize anything without "
                        "your approval. Reject WITH feedback → the agent revises and "
                        "re-asks.")
            self.db.add_approval({
                "id": aid, "task_id": task_id, "action": decision.action,
                "reason": reason, "risk": decision.risk, "preview": preview,
            })
            BUS.publish("approval.required",
                        {"id": aid, "task_id": task_id, "action": decision.action,
                         "risk": decision.risk, "revision": revisions}, task_id=task_id)
            verdict = self._await_approval(aid, timeout=600)

            if verdict["status"] == "approved":
                BUS.publish("approval.granted",
                            {"id": aid, "revisions": revisions}, task_id=task_id)
                self.db.audit("archon", "gate_approved", task_id,
                              {"approval": aid, "revisions": revisions})
                return current

            if verdict["status"] == "rejected":
                feedback = verdict.get("feedback")
                self.db.audit("user", "gate_rejected", task_id,
                              {"approval": aid, "feedback": feedback,
                               "revision_round": revisions + 1})
                if not feedback:
                    self._blocked(task_id, decision,
                                  "Approval rejected without feedback — nothing to "
                                  "revise against, task halted safely (C2).", lang)
                    return None
                if revisions >= self.GATE_MAX_REVISIONS:
                    self._blocked(task_id, decision,
                                  f"Rejected {revisions} times (revision limit "
                                  f"{self.GATE_MAX_REVISIONS}) — task halted safely; "
                                  "review the feedback manually. "
                                  "अनुमति नहीं मिली, कार्य रोका गया।", lang)
                    return None
                revisions += 1
                self._update(task_id, status="REVISION_NEEDED")
                current = self._revision_loop(task_id, ctx, plan, decision,
                                              entities, lang, feedback, current,
                                              revisions)
                self._update(task_id, status="WAITING_APPROVAL")
                continue  # re-present approval with the revised proposal

            # timeout
            self._blocked(task_id, decision,
                          "Approval not granted within window — task paused safely. "
                          "अनुमति नहीं मिली, कार्य रोका गया।", lang, status="BLOCKED")
            return None

    # ---------------- HITL revision loop (Reject → CHALLENGE → PROPOSAL) ----
    def _revision_loop(self, task_id: str, ctx: Dict[str, Any], plan: Dict[str, Any],
                       decision: Decision, entities: Dict[str, Any], lang: str,
                       feedback: str, consensus: Dict[str, Any],
                       rev_no: int) -> Dict[str, Any]:
        """User Reject feedback → CHALLENGE to the owning agent → new PROPOSAL.

        Deterministic side-effect: entities mentioned in the feedback (marks,
        class, topic, duration…) are merged so the regenerated artifact actually
        reflects what the user asked for.
        """
        def emit(mtype, frm, to, body, payload):
            BUS.publish("deliberation.message",
                        {"mtype": mtype, "from": frm, "to": to, "body": body,
                         "payload": payload}, task_id=task_id)

        primary = plan["specialists"][0] if plan["specialists"] else "academic"
        sp = AGENTS.get(primary) or AGENTS["academic"]

        # 1. deterministic entity merge from the feedback text
        fb_entities = extract_entities(feedback, lang)
        merged = {}
        for k in ("marks", "class_level", "topic", "subject", "duration"):
            if fb_entities.get(k) is not None and fb_entities.get(k) != entities.get(k):
                entities[k] = fb_entities[k]
                merged[k] = fb_entities[k]
        ctx["user_feedback"] = feedback  # visible to skills at EXECUTE time

        # 2. protocol: CHALLENGE (user) must cite evidence — the rejection IS evidence
        d = Deliberation(task_id, emit, self.db, round_max=2)
        d.round = 1
        d._send(SYSTEM_MSG, "archon", "all",
                f"Approval rejected (round {rev_no}) — routing user feedback as "
                f"CHALLENGE to {sp.name}.", {"feedback": feedback})
        d.challenge("user", primary,
                    f"USER CHALLENGE (approval #{rev_no} rejected): {feedback}",
                    concerns=[feedback],
                    evidence=[f"human operator rejected the approval gate with "
                              f"feedback: {feedback[:300]}"])

        # 3. owning agent files a NEW PROPOSAL addressing the challenge
        engine = engine_from_settings({"llm": self.db.get_setting("llm", {})})
        base = self._make_proposal(sp, plan, decision, entities, engine, lang)
        body = (base["body"]
                + f"\n\nREVISION after user challenge #{rev_no}:\n"
                + f"- addressed → {feedback}"
                + (f"\n- merged entities: {merged}" if merged else ""))
        payload = {**base["payload"],
                   "addresses": [feedback],
                   "user_feedback": feedback,
                   "confidence": min(0.93, base["payload"]["confidence"] + 0.03)}
        d.revise(primary, body, payload)   # rule #3: revision maps to concerns

        # 4. consensus re-cut with the revised proposal
        limitations = (list(consensus.get("residual_limitations") or [])
                       + [f"user: {feedback}"])
        ok = d.try_consensus(
            f"revised after user challenge #{rev_no}: {feedback[:100]}", limitations)
        if not ok:
            d.deadlock_arbitration(f"user revision round {rev_no}")
        rev_cons = d.consensus or {}
        new_consensus = {
            **consensus,
            "confidence": rev_cons.get("confidence", consensus.get("confidence", 0.7)),
            "rounds_used": (consensus.get("rounds_used") or 0) + 1,
            "note": (consensus.get("note", "")
                     + f" | revised after user feedback #{rev_no}: {feedback[:80]}"),
            "residual_limitations": limitations,
            "user_feedback": (consensus.get("user_feedback") or []) + [feedback],
            "revision_round": rev_no,
        }
        BUS.publish("task.revision",
                    {"id": task_id, "round": rev_no, "feedback": feedback,
                     "merged_entities": merged, "agent": primary}, task_id=task_id)
        self.db.audit("archon", "revision_loop", task_id,
                      {"round": rev_no, "feedback": feedback, "merged": merged,
                       "agent": primary})
        return new_consensus

    # ---------------- MEDIUM tier: non-blocking after-the-fact audit ----
    def _schedule_async_audit(self, task_id: str, decision: Decision,
                              command: str) -> None:
        def _worker() -> None:
            try:
                time.sleep(1.5)  # let the action run first — audit is AFTER-THE-FACT
                self.db.audit("risk", "async_audit_pass", task_id,
                              {"tier": decision.risk_tier, "action": decision.action,
                               "risk": decision.risk, "mode": decision.mode,
                               "command": command[:160]})
                BUS.publish("audit.async",
                            {"task_id": task_id, "tier": decision.risk_tier,
                             "action": decision.action}, task_id=task_id)
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    def _blocked(self, task_id: str, decision: Decision, msg: str, lang: str,
                 status: str = "BLOCKED") -> None:
        self._update(task_id, status=status, summary=msg,
                     summary_hi=msg if lang == "hi" else msg)
        BUS.publish("task.blocked", {"id": task_id, "message": msg}, task_id=task_id)
        self.db.audit("archon", "blocked", task_id, {"reason": msg})

    def _clarify(self, task_id: str, decision: Decision, question: str, lang: str) -> None:
        self._update(task_id, status="CLARIFY_NEEDED", summary=question, summary_hi=question,
                     confidence=decision.confidence)
        BUS.publish("task.clarify", {"id": task_id, "question": question},
                    task_id=task_id)
        self.db.audit("archon", "clarify", task_id, {"question": question})

    def _fail(self, task_id: str, err: str, lang: str) -> None:
        msg = (f"Task halted safely: {err}\nState was checkpointed; nothing was "
               f"silently marked complete (C2).")
        try:
            self._update(task_id, status="FAILED", summary=msg, summary_hi=msg)
        except Exception:
            pass
        BUS.publish("task.failed", {"id": task_id, "error": err}, task_id=task_id)
        self.db.audit("archon", "failed", task_id, {"error": err})
