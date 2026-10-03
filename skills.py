"""Skill registry — versioned, testable, discoverable capabilities.

A Skill is NOT a prompt: it has identity, triggers, schemas, procedure,
validators, autonomy level, performance metrics and learning hooks.
"""
from __future__ import annotations

import re
import time
from typing import Any, Callable, Dict, List, Optional

from .knowledge_graph import KnowledgeGraph

# skill_id -> generator(entities, ctx) -> {artifact dicts}
_REGISTRY: Dict[str, Callable] = {}
_SKILL_MANIFESTS: List[Dict[str, Any]] = []


def register(manifest: Dict[str, Any]):
    """Decorator: attach manifest + generator to the registry."""
    def deco(fn: Callable) -> Callable:
        m = dict(manifest)
        m.setdefault("version", "1.0.0")
        m.setdefault("autonomy", 2)
        m.setdefault("risk", 0.1)
        m.setdefault("validators", [])
        m.setdefault("triggers", [])
        m.setdefault("category", "general")
        _REGISTRY[m["id"]] = fn
        if m not in _SKILL_MANIFESTS:
            _SKILL_MANIFESTS.append(m)
        return fn
    return deco


class SkillRegistry:
    def __init__(self, db, kg: KnowledgeGraph) -> None:
        self.db = db
        self.kg = kg

    def seed(self) -> None:
        """Idempotent registration into DB + knowledge graph."""
        from . import generators  # noqa: F401  (triggers @register decorators)
        for m in _SKILL_MANIFESTS:
            self.db.upsert_skill(m)
            # graph node
            self.kg.upsert_node(f"skill:{m['id']}", "skill", m["name"],
                                category=m["category"], version=m["version"],
                                autonomy=m.get("autonomy", 2))
            # skill -> domain
            self.kg.add_edge(f"skill:{m['id']}", f"domain:{m['category']}", "BELONGS_TO")
            # skill -> validators
            for v in m.get("validators", []):
                self.kg.upsert_node(f"validator:{v}", "validator", v)
                self.kg.add_edge(f"skill:{m['id']}", f"validator:{v}", "VALIDATED_BY")
            # skill -> tools (declared)
            for t in m.get("tools", []):
                self.kg.upsert_node(f"tool:{t}", "tool", t)
                self.kg.add_edge(f"skill:{m['id']}", f"tool:{t}", "REQUIRES")
        # manifests are the source of truth: drop rows from renamed/retired
        # skills so discovery can never route execution to an unregistered id
        live = {m["id"] for m in _SKILL_MANIFESTS}
        for row in self.db.skills():
            if row["id"] not in live:
                self.db._exec("DELETE FROM skills WHERE id=?", (row["id"],))

    def get(self, skill_id: str) -> Optional[Dict[str, Any]]:
        for s in self.db.skills():
            if s["id"] == skill_id:
                return s
        return None

    def run(self, skill_id: str, entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        fn = _REGISTRY.get(skill_id)
        if not fn:
            # generators' @register decorators must have fired (seed() normally
            # guarantees this; lazy-import keeps late/edge calls working too)
            from . import generators  # noqa: F401
            fn = _REGISTRY.get(skill_id)
        if not fn:
            raise KeyError(f"skill '{skill_id}' not registered in runtime")
        out = fn(entities, ctx)
        out.setdefault("skill_id", skill_id)
        return out

    def discover(self, tokens: List[str], limit: int = 5) -> List[Dict[str, Any]]:
        return self.kg.discover_skills(tokens, limit)

    def record_run(self, skill_id: str, ok: bool, score: float) -> None:
        self.db.record_skill_run(skill_id, ok, score)
        self.db.audit("skill", "run", skill_id, {"ok": ok, "score": score})

    def list_manifests(self) -> List[Dict[str, Any]]:
        stats = {s["id"]: s for s in self.db.skills()}
        out = []
        for m in _SKILL_MANIFESTS:
            row = stats.get(m["id"], {})
            out.append({**m, "runs": row.get("runs", 0),
                        "successes": row.get("successes", 0),
                        "last_score": row.get("last_score")})
        return out

    def bump_version(self, skill_id: str, note: str) -> str:
        """RSI promotion: increment minor version of a skill."""
        row = self.db._q1("SELECT version FROM skills WHERE id=?", (skill_id,))
        if not row:
            return "0.0.0"
        try:
            major, minor, patch = [int(x) for x in row["version"].split(".")]
        except ValueError:
            major, minor, patch = 1, 0, 0
        minor += 1
        patch = 0
        newv = f"{major}.{minor}.{patch}"
        self.db._exec("UPDATE skills SET version=?, updated_at=? WHERE id=?",
                      (newv, time.time(), skill_id))
        # KG lineage
        self.kg.upsert_node(f"skill:{skill_id}:v{newv}", "skill",
                            f"{skill_id} v{newv}", version=newv)
        self.db.audit("rsi", "skill_version_bump", skill_id, {"to": newv, "note": note})
        return newv


# ---------------------------------------------------------------------------
# Evidence-based academic skills (HITL upgrade) — deterministic, offline.
# Registered here per spec (skills.py); SkillRegistry.seed() publishes them to
# DB + knowledge graph. Validators run inside the quality pipeline (C6).
# ---------------------------------------------------------------------------

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "topic").lower()).strip("_")[:40] or "topic"


def _skill_frame(title: str, entities: Dict[str, Any], kind: str,
                 body: str, notes: List[str], validators: List[Dict[str, Any]],
                 provenance_note: str) -> Dict[str, Any]:
    """Common result frame: 1 artifact + honest provenance + validators."""
    topic = entities.get("topic") or entities.get("subject") or "general focus"
    cls = entities.get("class_level") or "XI-XII"
    content = body.strip() + "\n\n---\n**Provenance:** INTERNAL_KNOWLEDGE — "
    content += provenance_note + "\n"
    status = "TRUSTED" if len(content) >= 400 and all(
        v.get("passed", True) for v in validators) else "NEEDS_REVIEW"
    return {
        "artifacts": [{"name": f"{kind}_{cls}_{_slug(topic)}.md", "kind": kind,
                       "content": content, "status": status}],
        "notes": notes,
        "validators": validators,
        "provenance": {"level": "INTERNAL_KNOWLEDGE", "note": provenance_note},
    }


@register({
    "id": "active_recall",
    "name": "Active Recall Generator",
    "category": "academic",
    "triggers": ["active recall", "retrieval practice", "recall drill", "recall round",
                 "सक्रिय स्मरण"],
    "input_schema": {"required": ["topic"],
                     "optional": ["subject", "class_level", "language"]},
    "output_schema": {"recall_deck": "markdown"},
    "validators": ["structure", "recall_ladder"],
    "autonomy": 2, "risk": 0.1,
    "tools": [],
})
def gen_active_recall(entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieval-practice deck: closed-book prompts → cloze → teach-back → key.

    Evidence base: the testing/retrieval-practice effect (established cognitive-
    psychology finding: actively retrieving strengthens memory more than
    re-reading). Deterministic 3-round ladder, CBSE commerce flavoured.
    """
    topic = entities.get("topic") or entities.get("subject") or "the chapter"
    cls = entities.get("class_level") or "XI-XII"
    subject = entities.get("subject") or "Commerce"
    lines = [
        f"# Active Recall Deck — {topic}",
        f"**Class {cls} · {subject} · closed-book retrieval practice**",
        "",
        "> How to use: answer ALOUD or on paper BEFORE flipping to the key. "
        "Struggle = learning. Repeat missed items after 10 minutes (spacing).",
        "",
        "## Round 1 — Retrieve (no notes, no hints)",
        f"1. Define **{topic}** in your own words in 30 seconds.",
        f"2. State any 3 features/components of **{topic}** without looking.",
        f"3. Give 2 real-world examples connected to **{topic}** "
        "(shop, business, or Class 11-12 Commerce context).",
        f"4. Write the correct order of the steps/process involved in **{topic}**.",
        f"5. Contrast **{topic}** with the nearest confusing concept — one line each.",
        f"6. Application: a 4-mark situation where **{topic}** decides the answer — "
        "what do you apply and why?",
        "",
        "## Round 2 — Cloze (fill the blanks from memory)",
        f"1. ________ is the term used when **{topic}** is applied to a new case.",
        f"2. The first step connected to **{topic}** is to ________, then to ________.",
        f"3. If **{topic}** is misapplied, the immediate consequence is ________.",
        f"4. One exam-relevant exception/condition for **{topic}** is ________.",
        "",
        "## Round 3 — Teach-back (60 seconds, out loud)",
        f"Explain **{topic}** to a classmate who missed the lecture. Include: what it is, "
        "why it matters, one example, one common mistake.",
        "",
        "## Self-check key (expected elements — award yourself 1 mark each)",
        f"- Definition names the core concept of **{topic}** (not a copy of the heading)",
        "- 3 features are distinct, not restatements of each other",
        "- Examples are concrete (named business/transaction, not vague)",
        "- Process steps are in a defensible order",
        "- Contrast states the distinguishing condition crisply",
        "- Teach-back includes a common-mistake warning",
        "",
        "## Scoring → next action",
        "| Score out of 6 | Action |\n|---|---|\n| 5-6 | Move on; re-test in 3 days |\n"
        "| 3-4 | Re-attempt only missed items tomorrow |\n"
        "| 0-2 | Re-read with notes, then repeat Round 1 today |",
    ]
    body = "\n".join(lines)
    structured = all(h in body for h in ("Round 1", "Round 2", "Round 3", "Self-check"))
    validators = [
        {"name": "structure", "passed": len(body) >= 400, "detail": f"{len(body)} chars"},
        {"name": "recall_ladder", "passed": structured,
         "detail": "retrieve → cloze → teach-back → key ladder present" if structured
                   else "ladder section missing"},
    ]
    notes = [f"active-recall deck on '{topic}' for Class {cls}",
             "evidence: retrieval-practice effect (established finding)"]
    return _skill_frame("Active Recall Deck", entities, "active_recall", body, notes,
                        validators,
                        "deterministic retrieval-practice scaffold; no external claims "
                        "were consulted (offline).")


@register({
    "id": "story_scaffold",
    "name": "CBSE Storytelling Scaffolder",
    "category": "academic",
    "triggers": ["storytelling", "story-driven", "story lesson", "storify", "story scaffold",
                 "कहानी"],
    "input_schema": {"required": ["topic"],
                     "optional": ["subject", "class_level", "language"]},
    "output_schema": {"lesson_story": "markdown"},
    "validators": ["structure", "story_arc"],
    "autonomy": 2, "risk": 0.1,
    "tools": [],
})
def gen_story_scaffold(entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """CBSE-specific storytelling scaffolding: 5-act arc welded to syllabus content.

    Story spine (deterministic): Hook → Conflict → Journey → Resolution → Reflect.
    Commerce Class 11-12 characters recur so later lessons extend the same world.
    """
    topic = entities.get("topic") or entities.get("subject") or "the concept"
    cls = entities.get("class_level") or "XI-XII"
    subject = entities.get("subject") or "Commerce"
    lines = [
        f"# Story-Driven Lesson Scaffold — {topic}",
        f"**Class {cls} · {subject} · 5-act CBSE storytelling spine**",
        "",
        "**Cast (recurring across your lesson series):**",
        "- **Aarav** — sharp but shortcut-loving; always wants the 'trick'.",
        "- **Meera** — methodical; asks 'but WHY does the rule exist?'",
        "- **Chacha Ji** — runs the neighbourhood shop; source of real transactions.",
        "",
        "## Act 1 — Hook (4 min): the anomaly",
        f"Chacha Ji's ledger for **{topic}** shows a number that 'looks wrong'. "
        "Aarav bets it is fine; Meera wants the rule behind it. Students place a "
        "30-second pre-judgement (prior knowledge activation).",
        "",
        "## Act 2 — Conflict (8 min): the syllabus question",
        f"Pose the driving question: *'According to CBSE, what SHOULD happen with "
        f"**{topic}**, and why does Chacha Ji's way differ?'* Elicit 2 student "
        "theories on the board — both kept visible (no ridicule).",
        "",
        "## Act 3 — Journey (15 min): concept stations",
        f"Station A — the rule/definition of **{topic}** (teacher mini-input, 5 min).",
        "Station B — worked example on Chacha Ji's ledger (guided, 5 min).",
        "Station C — pair check: Meera explains it to Aarav, swapped next round (5 min).",
        "",
        "## Act 4 — Resolution (8 min): the reveal",
        f"Re-open the Act 1 anomaly. Students apply **{topic}** themselves; the 'wrong' "
        "number resolves via the rule. Aarav's shortcut is tested — where it breaks, "
        "is named aloud (misconception made visible).",
        "",
        "## Act 5 — Reflect (5 min): exam bridge",
        f"Exit ticket (3-2-1): 3 features of **{topic}**, 2 exam phrasings you might "
        "see, 1 doubt to raise next class. Map Acts 2-4 to the CBSE marking "
        "language (define / state / apply).",
        "",
        "## Story-driven worksheet (embedded in the narrative)",
        f"1. Why did Chacha Ji's ledger for **{topic}** look wrong? (2 marks)",
        f"2. State the CBSE rule for **{topic}** and justify it in one sentence. (3 marks)",
        f"3. Aarav's shortcut fails in one situation — identify it. (3 marks)",
        f"4. Apply **{topic}** to a fresh transaction of your own invention. (4 marks)",
        f"5. Write the exam-style conclusion Meera would give for **{topic}**. (4 marks)",
        "",
        "## Teacher notes",
        "- Keep Acts 1/2/4 story beats identical across chapters — the WORLD is stable, "
        "only the concept changes (schema becomes automatic).",
        "- Every fictional detail must be labelled fictional; every rule cited must be "
        "the actual CBSE syllabus rule (C1 honesty inside the story too).",
    ]
    body = "\n".join(lines)
    structured = all(h in body for h in ("Act 1", "Act 2", "Act 3", "Act 4", "Act 5"))
    validators = [
        {"name": "structure", "passed": len(body) >= 400, "detail": f"{len(body)} chars"},
        {"name": "story_arc", "passed": structured,
         "detail": "Hook→Conflict→Journey→Resolution→Reflect arc complete" if structured
                   else "act missing"},
    ]
    notes = [f"story scaffold for '{topic}' — recurring cast + exam bridge",
             "CBSE: narrative serves the syllabus, never replaces the rule"]
    return _skill_frame("Story Scaffold", entities, "story_scaffold", body, notes,
                        validators,
                        "deterministic CBSE storytelling scaffold; fictional characters "
                        "labelled, rules deferred to the official syllabus.")


@register({
    "id": "adaptive_quiz",
    "name": "Adaptive Quiz Generator",
    "category": "academic",
    "triggers": ["adaptive quiz", "quiz", "pop quiz", "tiered quiz", "प्रश्नोत्तरी"],
    "input_schema": {"required": ["topic"],
                     "optional": ["subject", "class_level", "language", "marks"]},
    "output_schema": {"quiz": "markdown"},
    "validators": ["structure", "tier_balance"],
    "autonomy": 2, "risk": 0.1,
    "tools": [],
})
def gen_adaptive_quiz(entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """3-tier adaptive quiz: Foundation → Competent → Proficient with branch rules.

    Adaptive path (deterministic): F-score ≥ 3/4 → jump to Tier 2; ≤ 1/4 → remediation
    branch first. T2/T3 scores band the learner and prescribe the next step.
    """
    topic = entities.get("topic") or entities.get("subject") or "the chapter"
    cls = entities.get("class_level") or "XI-XII"
    subject = entities.get("subject") or "Commerce"
    lines = [
        f"# Adaptive Quiz — {topic}",
        f"**Class {cls} · {subject} · 3 tiers, branching rules**",
        "",
        "**Branching (apply after each tier):**",
        "- Tier score ≥ 75% → proceed UP to the next tier.",
        "- Tier score 40-74% → repeat missed items, then same tier's next block.",
        "- Tier score < 40% → REMEDIATION branch: re-read the relevant section, "
        "then retake this tier (do not advance).",
        "",
        "## Tier 1 — Foundation (4 × 1 mark) — everyone starts here",
        f"1. The term **{topic}** refers to: (a) definition recall prompt "
        "(write the definition) (b) a related but wrong term (c) none (d) not covered.",
        f"2. One key feature of **{topic}**: ________.",
        f"3. **{topic}** belongs to which unit/chapter of {subject}? ________.",
        f"4. True/False with reason: **{topic}** can be applied without knowing its "
        "pre-conditions. ________.",
        "",
        "## Tier 2 — Competent (3 × 2 marks)",
        f"5. State the rule/procedure of **{topic}** in correct order.",
        f"6. Aarav applies **{topic}** to a case where it does not apply — identify "
        "the error and correct it.",
        f"7. Differentiate **{topic}** from its nearest confusing neighbour "
        "(2 points).",
        "",
        "## Tier 3 — Proficient (3 × 3 marks)",
        f"8. Case: Chacha Ji's transaction hits an exception in **{topic}** — work "
        "the solution with working shown.",
        f"9. Justify WHY the CBSE rule for **{topic}** is framed the way it is "
        "(exam-style, 3 points).",
        f"10. Create a 3-mark exam question on **{topic}** with a model answer — "
        "then solve a peer's question.",
        "",
        "## Scoring bands & prescribed next step",
        "| Overall | Band | Next step |\n|---|---|---|\n"
        "| ≥ 85% | Proficient | Enrichment: case-study project on "
        f"**{topic}** |\n| 60-84% | Competent | Spaced re-test of missed items in 2 days |\n"
        "| 40-59% | Developing | Remediation branch + Tier 1 re-test tomorrow |\n"
        "| < 40% | Needs support | Teacher 5-minute clinic, then retake full quiz |",
        "",
        "**Answer key (expected elements):** Q1 definition of "
        f"**{topic}**; Q2-4 single-feature recall; Q5 ordered rule; Q6 mis-application "
        "identified + correction; Q7 two-point contrast; Q8 worked solution with the "
        "exception applied; Q9 three justified points; Q10 plausible question + matching "
        "model answer.",
    ]
    body = "\n".join(lines)
    tiers = all(h in body for h in ("Tier 1", "Tier 2", "Tier 3", "Scoring bands"))
    validators = [
        {"name": "structure", "passed": len(body) >= 400, "detail": f"{len(body)} chars"},
        {"name": "tier_balance", "passed": tiers,
         "detail": "3 tiers + branch rules + scoring bands present" if tiers
                   else "tier/branch section missing"},
    ]
    notes = [f"adaptive quiz on '{topic}': 4+3+3 tier structure with branch rules",
             "honest: item wording is a deterministic template — teacher should swap "
             "in chapter specifics before high-stakes use"]
    return _skill_frame("Adaptive Quiz", entities, "adaptive_quiz", body, notes,
                        validators,
                        "deterministic tiered-quiz template; branch rules follow standard "
                        "mastery-learning practice; no external sources consulted.")


# ---------------------------------------------------------------------------
# EduVis pedagogy pack (Manim/Qwen-Agent-inspired, deterministic & offline):
# CBSE topic -> step-by-step interactive simulation script.
# ---------------------------------------------------------------------------

@register({
    "id": "visual_storytelling_planner",
    "name": "Visual Storytelling Planner",
    "category": "academic",
    "triggers": ["simulation script", "simulation plan", "visual story",
                 "interactive simulation", "virtual lab script", "sim story",
                 "सिमुलेशन"],
    "input_schema": {"required": ["topic"],
                     "optional": ["subject", "class_level", "duration"]},
    "output_schema": {"simulation_script": "markdown"},
    "validators": ["structure", "simulation_steps"],
    "autonomy": 2, "risk": 0.1,
    "tools": [],
})
def gen_visual_storytelling_planner(entities: Dict[str, Any],
                                    ctx: Dict[str, Any]) -> Dict[str, Any]:
    """EduVis Specialist (Lumina): breaks a CBSE Class 11/12 Commerce topic into a
    scene-by-scene interactive simulation script — hook → model → learner action →
    check-for-understanding — the 12-year storytelling pedagogy turned into a
    digital lab plan that Vibe Coder can build offline."""
    topic = entities.get("topic") or entities.get("subject") or "the concept"
    subject = entities.get("subject") or "Commerce"
    cls = entities.get("class_level") or "XI-XII"
    duration = entities.get("duration") or 40

    beats = [
        ("Hook — the story question", 
         f"Open on a 12-year-old's world: a shopkeeper deciding whether "
         f"**{topic}** is 'fair'. Pose the ONE question the simulation will answer.",
         "Learner states a prediction (tap/click: agree → disagree).",
         "Prediction recorded on screen — visible again at the end."),
        ("Model — build the world",
         f"Show the {subject} ledger/scene as an interactive diagram: movable cards, "
         f"highlighted numbers, one hidden variable tied to **{topic}**.",
         "Learner drags one card to see what changes (immediate visual feedback).",
         "Story beat: the shopkeeper reacts to the learner's move."),
        ("Challenge — break it",
         f"Simulation introduces a transaction that breaks the **{topic}** model "
         f"(wrong balance / violated rule).",
         "Learner must restore the rule by adjusting inputs — 2 attempts allowed.",
         "Failure shows the story consequence (shop loses money), never a scold."),
        ("Scaffold — the rule revealed",
         "Overlay the formal CBSE rule/entry exactly as the textbook states it, "
         "mapped card-by-card onto the simulation the learner just fixed.",
         "Learner matches formal term → simulation card (tap-to-match mini-quiz).",
         "Win-win: learner sees the textbook rule is the SAME thing they just used."),
        ("Practice — spaced recall",
         f"Three rapid rounds on **{topic}** with fading hints (hint 1: story cue, "
         f"hint 2: rule name, hint 3: worked step).",
         "Learner solves rounds; score feeds the check-for-understanding below.",
         "Story closure: shopkeeper's balance restored — prediction revisited."),
        ("Check for understanding",
         "Exit ticket: 3 adaptive questions (easy → hard) + 1 'teach it back' line.",
         "Learner answers; auto-scored; weak item triggers a one-line remedy hint.",
         "Evidence: per-learner mastery map for the teacher (offline artifact)."),
    ]

    lines = [
        f"# Simulation Script — {topic}",
        f"**Subject:** {subject} · **Class:** {cls} · **Duration:** {duration} min · "
        f"**Owner:** EduVis Specialist (Lumina)",
        "",
        f"**Learning objective:** the learner can explain and apply **{topic}** by "
        f"manipulating a model, failing safely, and recovering — not by memorising.",
        "",
        "**Pedagogy contract:** story hook → interactive model → safe failure → "
        "formal rule → spaced recall → exit ticket (12-year storytelling arc).",
        "",
    ]
    for i, (name, teacher, learner, story) in enumerate(beats, 1):
        lines += [
            f"## Step {i} — {name}",
            f"- **Teacher move:** {teacher}",
            f"- **Learner action:** {learner}",
            f"- **Story tie-in:** {story}",
            "",
        ]
    lines += [
        "**Build notes for Vibe Coder (offline-first):** single-file HTML/JS or "
        "Python lab; no CDN; every step above must be a tappable screen.",
        "",
        "**Provenance:** deterministic pedagogy template (INTERNAL_KNOWLEDGE) — "
        "fill chapter-specific numbers from the CBSE source before use (C1).",
    ]
    content = "\n".join(lines)

    # structure: markdown headings + required role lines
    headings = content.count("## Step ")
    role_lines = content.count("**Teacher move:**") + content.count("**Learner action:**")
    struct_ok = headings == len(beats) and role_lines == 2 * len(beats)
    steps_ok = (headings >= 5
                and content.count("**Learner action:**") >= 5
                and content.count("Check for understanding") >= 1
                and "**Learning objective:**" in content)
    return {
        "artifacts": [{"name": f"sim_script_{_slug(topic)}.md",
                       "kind": "simulation_script", "content": content,
                       "status": "TRUSTED" if (struct_ok and steps_ok)
                                 else "NEEDS_REVIEW"}],
        "notes": [f"{len(beats)} simulation steps planned for '{topic}'",
                  "assigned to EduVis Specialist — hand script to Vibe Coder to build"],
        "validators": [
            {"name": "structure", "passed": struct_ok,
             "detail": f"{headings} step headings, {role_lines} role lines"},
            {"name": "simulation_steps", "passed": steps_ok,
             "detail": "steps≥5 with learner actions, objective + exit ticket"
                       if steps_ok else "missing steps/actions/objective"},
        ],
        "provenance": {"level": "INTERNAL_KNOWLEDGE",
                       "note": "Deterministic pedagogy scaffold; no external content fetched."},
    }
