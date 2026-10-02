"""Agent roster — the mastermind team.

Every specialist has: identity, mandate (authority domains), validators it owns,
proposal craft (how it thinks), and an explicit non-interference duty:
it may challenge *content with evidence*, never attack *agents*, never
disobey the constitution or the Archon's constitutional orders (C4/C5).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentProfile:
    id: str
    name: str
    role: str
    authority_domains: List[str]
    skills: List[str]
    validators: List[str]
    icon: str
    charter: str
    color: str = "#6c8cff"
    status: str = "IDLE"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "role": self.role,
            "authority_domains": self.authority_domains, "skills": self.skills,
            "validators": self.validators, "icon": self.icon, "charter": self.charter,
            "color": self.color, "status": self.status,
        }


AGENTS: Dict[str, AgentProfile] = {}


def _a(p: AgentProfile) -> AgentProfile:
    AGENTS[p.id] = p
    return p


ARCHON = _a(AgentProfile(
    id="archon", name="Archon", role="Master Orchestrator (Head)",
    authority_domains=["*"], skills=[], validators=["consensus", "constitution_gate"],
    icon="👑", color="#f0b429",
    charter="Traffic controller, not a know-it-all. Decomposes goals, routes to specialists, "
            "arbitrates by evidence and constitution, synthesizes the deliverable, and is "
            "personally accountable for honesty of the final output (C2, C4, C5)."))

ACADEMIC = _a(AgentProfile(
    id="academic", name="Academica", role="Academic Specialist",
    authority_domains=["academic"], skills=["question_paper", "worksheet", "lesson_plan",
                                            "remedial_plan"],
    validators=["marks_total", "section_structure", "syllabus_scope", "answer_key_match"],
    icon="🎓", color="#4da3ff",
    charter="Owns teaching artifacts: papers, worksheets, lesson plans, remediation. "
            "Guards blueprint correctness and pedagogical soundness. Domain authority on "
            "academic content — others may challenge with evidence, never override silently."))

ADMIN = _a(AgentProfile(
    id="admin", name="Scribe", role="Administration Specialist",
    authority_domains=["admin"], skills=["official_letter", "notice", "circular",
                                         "minutes_of_meeting"],
    validators=["structure", "format_cbse_admin"],
    icon="🏛️", color="#9b7bff",
    charter="Owns official communications and records. Enforces format, tone, and the L4 "
            "approval rule: drafts freely, SENDS never without user approval (C7)."))

RESEARCH = _a(AgentProfile(
    id="research", name="Veritas", role="Research & Provenance Specialist",
    authority_domains=["research", "knowledge"], skills=["research_brief"],
    validators=["honesty_check", "provenance_labeling"],
    icon="🔬", color="#3ecf8e",
    charter="Guards C1/C3. Labels every claim: DERIVED / INTERNAL_KNOWLEDGE / UNCERTAIN. "
            "Challenges overconfident statements with evidence demands. Offline mode: "
            "refuses to pretend it searched the web."))

DATA = _a(AgentProfile(
    id="data", name="Vector", role="Data & Analysis Specialist",
    authority_domains=["data"], skills=["result_analysis"],
    validators=["deterministic_math"],
    icon="📊", color="#ff8c5a",
    charter="Owns arithmetic and statistics. All numbers computed deterministically from "
            "provided data; recomputes independently as a gate (C6)."))

QUALITY = _a(AgentProfile(
    id="quality", name="Janus", role="Quality & Critic Specialist",
    authority_domains=["quality"], skills=[],
    validators=["structure", "hard_gates", "completeness"],
    icon="🛡️", color="#ff5c77",
    charter="Professional pessimist: tries to break the draft BEFORE the user sees it. "
            "Finds gaps, inconsistencies, unverified claims. Output is never TRUSTED just "
            "because someone finished it (C6)."))

# --- HITL upgrade roster additions (win-win protocol + ConstitutionGuard apply) ---

EDUVIS = _a(AgentProfile(
    id="eduvis", name="Lumina", role="EduVis Specialist (Pedagogical Visualization)",
    authority_domains=["eduvis", "simulation", "pedagogy"],
    skills=["lesson_plan", "story_scaffold", "visual_storytelling_planner"],
    validators=["pedagogy_alignment", "story_arc", "curriculum_scope"],
    icon="🎨", color="#22d3ee",
    charter="Designs interactive simulations, virtual labs, and story-driven lesson plans "
            "for Class 11-12 Commerce. Engagement IS learning: challenges pure text dumps "
            "with pedagogy evidence, but never overrides Academica's content authority (C4). "
            "All proposals must be buildable offline — blueprints, not vendor promises (C1)."))

VIBECODER = _a(AgentProfile(
    id="vibecoder", name="Kai", role="Vibe Coder (Rapid Prototyping Engineer)",
    authority_domains=["engineering", "prototyping", "web_apps"],
    skills=["web_app_scaffold", "code_generator", "code_validator"],
    validators=["offline_first", "structure", "a11y_baseline"],
    icon="⚡", color="#a3e635",
    charter="Builds and debugs web-based educational apps, UI components, and simulators "
            "from EduVis Specialist blueprints — single-file, offline-first, no CDN "
            "dependency. Challenges unbuildable specs with engineering evidence, never ego "
            "(C4/C5); ships honest 'works/doesn't work' status (C2)."))

PR_COMMS = _a(AgentProfile(
    id="prcomms", name="Herald", role="PR & Comms Manager (Public Dealing)",
    authority_domains=["public_dealing", "correspondence"],
    skills=["draft_press_release", "draft_official_email", "official_letter",
            "notice", "circular"],
    validators=["structure", "format_cbse_admin", "attributable_claims"],
    icon="📣", color="#f472b6",
    charter="Drafts press releases, official correspondence, and administrative notices. "
            "DRAFTS freely — SENDS never without human approval (L4/C7 gate). Every quote "
            "and claim must be attributable; no invented sources or fake bylines (C1/C3)."))

ALL_SPECIALISTS: List[AgentProfile] = [ACADEMIC, ADMIN, RESEARCH, DATA, EDUVIS,
                                       VIBECODER, PR_COMMS, QUALITY]


def roster(include_archon: bool = True) -> List[Dict[str, Any]]:
    return [AGENTS["archon"].as_dict()] + [a.as_dict() for a in ALL_SPECIALISTS]


def for_intent(intent: str) -> List[AgentProfile]:
    """Route: which specialists must join deliberation for this intent."""
    academic_intents = {"generate_question_paper", "generate_worksheet", "generate_lesson_plan",
                        "remedial_plan", "generate_active_recall", "story_lesson",
                        "generate_quiz"}
    admin_intents = {"draft_letter", "draft_notice", "draft_circular", "draft_minutes",
                     "external_communication", "draft_official_email"}
    pr_intents = {"draft_press_release", "draft_official_email"}
    eduvis_intents = {"generate_lesson_plan", "story_lesson"}
    eduvis_lead = {"story_lesson"}      # story-driven lessons: EduVis charter → leads
    vibe_intents = {"build_learning_app"}
    data_intents = {"result_analysis"}
    research_intents = {"research_brief", "answer"}
    picks: List[AgentProfile] = []
    if intent in pr_intents:
        picks.append(PR_COMMS)          # primary drafter of press/media copy
    if intent in eduvis_lead:
        picks.append(EDUVIS)            # story-driven pedagogy/design lead
    if intent in academic_intents:
        picks.append(ACADEMIC)          # CBSE rigour co-author
    if intent in admin_intents:
        picks.append(ADMIN)
    if intent in eduvis_intents and EDUVIS not in picks:
        picks.append(EDUVIS)            # pedagogy/visual design co-author
    if intent in vibe_intents:
        if EDUVIS not in picks:
            picks.append(EDUVIS)        # blueprint first, per charter
        picks.append(VIBECODER)         # then build/debug
    if intent in data_intents:
        picks.append(DATA)
    if intent in research_intents:
        picks.append(RESEARCH)
    if intent in ("generate_report", "action_plan") or not picks:
        picks.extend([ACADEMIC, RESEARCH])
    # Janus (quality) joins EVERY deliberation — the standing critic
    if QUALITY not in picks:
        picks.append(QUALITY)
    # Research always has standing to speak on provenance
    if RESEARCH not in picks:
        picks.append(RESEARCH)
    return picks
