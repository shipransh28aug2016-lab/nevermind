"""System seed — builds the knowledge graph, registers skills, initial memory."""
from __future__ import annotations

import re
import time
from typing import Any

from .agents import AGENTS, ALL_SPECIALISTS, ARCHON, roster
from .constitution import ARTICLES
from .knowledge_graph import KnowledgeGraph
from .skills import SkillRegistry


def seed_syllabus(kg, memory, db) -> None:
    """Idempotent seeding of the official CBSE 2026-27 syllabus knowledge base.

    Runs on EVERY process start but inserts only what is missing (guarded
    per-key on semantic memory + node-existence checks on the KG), so a
    pre-existing production DB gains the syllabus knowledge without losing
    history.
    """
    from . import syllabus as SYL
    for name, s in SYL.SUBJECTS.items():
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        sid = f"subject:{slug}"
        if not kg.node(sid):
            kg.upsert_node(sid, "knowledge", f"{name} (CBSE code {s['code']})",
                           code=s["code"], session=SYL.SESSION)
            kg.add_edge("domain:academic", sid, "CONTAINS")
        for skill in ("question_paper", "worksheet", "lesson_plan"):
            if kg.node(f"skill:{skill}"):
                kg.add_edge(f"skill:{skill}", sid, "REQUIRES")
        for cl, cd in s["classes"].items():
            syid = f"syllabus:{slug}:{cl.lower()}"
            if not kg.node(syid):
                kg.upsert_node(syid, "knowledge",
                               f"{name} Class {cl} syllabus {SYL.SESSION}",
                               theory_marks=cd["theory"],
                               project_marks=cd.get("project", 0))
                kg.add_edge(sid, syid, "CONTAINS")
            for u in cd["units"]:
                uid = f"unit:{slug}:{cl.lower()}:{u['unit']}"
                if not kg.node(uid):
                    kg.upsert_node(uid, "knowledge",
                                   f"{name} {cl} U{u['unit']}: {u['title']}")
                    kg.add_edge(syid, uid, "CONTAINS")
            key = f"syllabus_{slug}_{cl.lower()}"
            exists = db._q1(
                "SELECT id FROM memories WHERE layer='semantic' AND key=?", (key,))
            if not exists:
                memory.remember("semantic", key, SYL.summary(name, cl),
                                source="cbse_syllabus_sec_p2_2026_27",
                                confidence=0.99, promote=True)
            elif (exists.get("confidence") or 0) < 0.99:
                # migration: official reference data outranks tied 0.95 episodic rows
                db.update_memory(exists["id"], confidence=0.99)


def seed_system(db, kg: KnowledgeGraph, skills: SkillRegistry, memory) -> None:
    # -- agents into KG -------------------------------------------------
    for a in roster():
        kg.upsert_node(f"agent:{a['id']}", "agent", a["name"],
                       role=a["role"], charter=a["charter"][:240])
    # archon routes to specialists
    for sp in ALL_SPECIALISTS:
        kg.add_edge("agent:archon", f"agent:{sp.id}", "COMPOSES")
    # domains
    for dom, label in [("academic", "Academic / Teaching"), ("admin", "Administration"),
                       ("research", "Research & Provenance"), ("data", "Data & Analysis"),
                       ("quality", "Quality & Verification"), ("general", "General Purpose")]:
        kg.upsert_node(f"domain:{dom}", "domain", label)
    # authority: which agent owns which domain
    for sp in ALL_SPECIALISTS:
        for d in sp.authority_domains:
            if d != "*":
                kg.add_edge(f"agent:{sp.id}", f"domain:{d}", "AUTHORITY_IN")
    # knowledge nodes
    for kid, klabel in [("cbse_blueprint", "CBSE-style blueprint conventions"),
                        ("document_format", "Official document formats"),
                        ("stats_methods", "Deterministic statistics methods")]:
        kg.upsert_node(f"knowledge:{kid}", "knowledge", klabel)
        kg.add_edge("domain:academic" if kid == "cbse_blueprint" else
                    "domain:admin" if kid == "document_format" else
                    "domain:data", f"knowledge:{kid}", "CONTAINS")

    # -- skills -----------------------------------------------------------
    skills.seed()
    # link skills to executing agents
    for sp in ALL_SPECIALISTS:
        for sid in sp.skills:
            if kg.node(f"skill:{sid}"):
                kg.add_edge(f"agent:{sp.id}", f"skill:{sid}", "EXECUTES")

    # -- artifacts handled ----------------------------------------------
    for tool, kinds in [("document_generator", ["question_paper", "worksheet", "letter",
                                                "notice", "circular", "report", "plan"]),
                        ("calculator", ["analysis"]),
                        ("knowledge_base", ["research_brief"])]:
        kg.upsert_node(f"tool:{tool}", "tool", tool)
        for k in kinds:
            kg.add_edge(f"tool:{tool}", f"artifact_kind:{k}", "HANDLES")
            kg.upsert_node(f"artifact_kind:{k}", "artifact", k)

    # -- constitution into KG ----------------------------------------------
    kg.upsert_node("knowledge:constitution", "knowledge",
                   "NEVERMIND Constitution (C1–C14)",
                   articles=len(ARTICLES), control_plane=True)
    for a in AGENTS.values():
        kg.add_edge(f"agent:{a.id}", "knowledge:constitution", "REQUIRES")

    # -- seed official CBSE syllabus (idempotent; runs every start)
    seed_syllabus(kg, memory, db)

    # -- seed official CBSE syllabus (idempotent; runs every start)

    # -- seed memory -------------------------------------------------------
    if not memory.all("semantic"):
        memory.semantic(
            "CBSE Class 12 Accountancy standard question paper pattern: sections A–E, "
            "80 marks, 180 minutes unless school-specific blueprint says otherwise.",
            source="internal_seed", authority=0.6)
        memory.semantic(
            "Official communications to external parties (principal, board, parents) are "
            "L4: draft freely, send only after explicit user approval.",
            source="constitution_seed", authority=0.95)
        memory.semantic(
            "Offline mode honesty: without LLM/web connectivity, no live-source claims "
            "may be presented as verified.",
            source="constitution_seed", authority=0.95)
        memory.remember("procedural", "standard_task_flow",
                        "perceive → decide → plan → deliberate → execute → verify → "
                        "deliver → learn", confidence=0.9, source="seed", promote=True)
        memory.remember("performance", "default_routing",
                        "archon+specialists by intent → janus always present",
                        confidence=0.8, source="seed")
        memory.episode("SEED", "System initialised with EDU-OPS + general skill pack",
                       "OK", 1.0)

    # -- settings -----------------------------------------------------------
    db.set_setting("autonomy_mode", db.get_setting("autonomy_mode", "SEMI_AUTONOMOUS"))
    db.set_setting("language", db.get_setting("language", "en"))
    db.set_setting("max_rounds", db.get_setting("max_rounds", 3))
    db.set_setting("kill", False)
    db.set_setting("paused", False)
    db.set_setting("system_name", "NEVERMIND")
    db.set_setting("version", "1.0.0")
    db.set_setting("seeded_at", db.get_setting("seeded_at", time.time()))

    db.audit("system", "seed", "boot", {"skills": len(skills.list_manifests()),
                                        "agents": len(roster())})
