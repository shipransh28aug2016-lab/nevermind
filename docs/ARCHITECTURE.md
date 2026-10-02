# NEVERMIND — Architecture

## Planes (the RSI safety boundary)

```
┌────────────────────────────────────────────────────┐
│ CONTROL PLANE — constitution.py, decision.py,      │
│   golden suite, kill switch, approvals             │
│   ▲ NEVER modified by Agent Plane                  │
├────────────────────────────────────────────────────┤
│ AGENT PLANE — orchestrator, deliberation, agents   │
│   ▲ reads policy, executes tasks                   │
├────────────────────────────────────────────────────┤
│ DATA PLANE — SQLite (db.py), knowledge graph,      │
│   memory, output/ artifacts                        │
└────────────────────────────────────────────────────┘
```

## Task lifecycle state machine

```
CREATED → DECIDED → PLANNED → DELIBERATING → [WAITING_APPROVAL ⇄ REVISION_NEEDED]
   → EXECUTING → VERIFYING → DELIVERING → COMPLETED | COMPLETED_WITH_NOTES
   ↘ CLARIFY_NEEDED (C12 — one precise question)
   ↘ BLOCKED (L5 / rejected-without-feedback / revision limit / timeout)
   ↘ FAILED (safe halt, checkpoint kept)
```

## Pre-action gate — HITL risk tiering (decision.py + orchestrator.py)

Every decision carries `risk_tier` and `gate`; the orchestrator enforces the
**strict Pre-Action Gate AFTER deliberation, BEFORE execution**:

| Tier | What | Gate behaviour |
|---|---|---|
| **LOW** | drafting, reading, artifact creation (L0–L2) | `AUTO_EXECUTE` |
| **MEDIUM** | local file writes (L3) | `AUTO_EXECUTE_WITH_ASYNC_AUDIT` — action runs, `async_audit_pass` written ~1.5 s later on a daemon thread, `audit.async` published |
| **HIGH** | external communication / publishing / consequential (L4) — **incl. `draft_press_release` & `draft_official_email` (PR pack)** | `HUMAN_APPROVAL_REQUIRED` — task parks in `WAITING_APPROVAL` until approve/reject/timeout (600 s); their artifacts also carry the `NEEDS_APPROVAL` flag |
| **L5** | forbidden (delete, destructive, malicious) | `FORBIDDEN` — hard-blocked at DECIDE *and* re-checked in the gate; no approval path exists |

**Revision loop (Reject → CHALLENGE → PROPOSAL):**
```
user clicks REJECT + writes feedback  (server: 400 if feedback empty)
  → gate routes feedback as CHALLENGE to the owning agent (evidence = the
    rejection itself, protocol rule #2 satisfied)
  → entities in the feedback (marks/class/topic/duration) are merged into the
    task so the regenerated artifact actually changes
  → agent files a REVISION (rule #3: addresses[] = the feedback)
  → new approval presented under a fresh id A-{task}-r{n} (max 3 rounds)
  → reject w/o feedback, revision limit, or timeout → BLOCKED (never silent)
```

Assisted mode additionally keeps all execution at L1 (nothing auto-runs).

## Agent roster (agents.py — 7 specialists + archon)

`academic · admin · research · data · eduvis · vibecoder · prcomms · quality(Janus)`
with intent routing in `for_intent()`: press/media → **prcomms** first;
story-driven pedagogy → **eduvis** first (academic co-authors CBSE rigour);
edu apps → **eduvis blueprint → vibecoder build**; recall/quiz → **academic**.
All specialists pass through the same win-win deliberation protocol and
ConstitutionGuard — no agent can quarrel, disobey, or report fake completion.

- **EduVis (Lumina)** — interactive simulations, virtual labs, story-driven
  lesson plans, Class 11–12 Commerce; owns `visual_storytelling_planner`.
- **Vibe Coder (Kai)** — builds/debugs web-based edu apps, UI components,
  simulators from EduVis blueprints; owns `code_generator` + `code_validator`.
- **PR & Comms (Herald)** — press releases, official correspondence,
  administrative notices.

## Evidence-based skills (21 total — deterministic, zero API keys)

| Skill | Owner intent | Validators |
|---|---|---|
| `active_recall` | `generate_active_recall` | structure + recall_ladder |
| `story_scaffold` | `story_lesson` | structure + story_arc |
| `adaptive_quiz` | `generate_quiz` | structure + tier_balance |
| `draft_press_release` ¹ | `draft_press_release` | structure + attributable_claims |
| `draft_official_email` ¹ | `draft_official_email` | structure + recipient_slot |
| `web_app_scaffold` | `build_learning_app` | structure + offline_first |
| `code_generator` ² | `build_learning_app` (react/python keywords) | structure + completeness |
| `code_validator` ² | runs beside `code_generator` | structure + completeness |
| `visual_storytelling_planner` ³ | `story_lesson` (simulation keywords) | structure + simulation_steps |

¹ PR pack (Composio-inspired): artifacts ship with `needs_approval=True` /
`approval_flag="NEEDS_APPROVAL"` and the intent is forced to L4 in
`decision.py` — drafts park for human approval before generation completes.
² Vibe Coder pack (OpenHands/Aider-inspired): React+Tailwind or stdlib-Python
simulator source + static completeness audit before anything is saved.
³ EduVis pack (Manim/Qwen-Agent-inspired): CBSE topic → scene-by-scene
interactive simulation script assigned to the EduVis Specialist.

All TRUSTED-gated before delivery; offline-first HTML apps carry no external
URLs; manifest ids are the source of truth (seed prunes renamed rows).

## Deliberation protocol (enforced in code, not prompts)

| Rule | Enforcement |
|---|---|
| Typed envelopes | `Deliberation._send` writes every message to DB + SSE |
| Challenges need evidence | empty `evidence[]` → FAULT, message not delivered |
| Revisions map to concerns | revision without `addresses[]` → FAULT |
| No quarrelling | attack regex → FAULT + C5 logged; bodies screened by ConstitutionGuard |
| Bounded rounds | `MAX_DELIBERATION_ROUNDS = 3`, then evidence-ranked arbitration |
| Consensus requires quality | Janus open concerns block consensus; residual → visible limitations |
| Cross-discipline peer review | when EduVis+Vibe Coder both deliberate: Lumina challenges builds lacking learning-objective markers, Kai challenges blueprints lacking feasibility markers (concerns+evidence, marker-sensitive — no theatre) |

Specialists propose within their **authority domains** only (edge type
`AUTHORITY_IN` in the knowledge graph); others may contribute adjacent checks
with an explicit non-interference note (C4).

## Quality pipeline (C6)

```
artifacts → deterministic validators (marks, structure, math, provenance)
         → ConstitutionGuard screen → coverage check → consensus check
         → TRUSTED | NEEDS_REVIEW | REWORK(→one targeted pass) | FAILED
hard failures block delivery regardless of soft scores
```

## RSI promotion gate

```
task experience → learning item → anti-habit filter (H1–H7 blacklist)
  → proposal (candidate) → sandbox → 7 golden tests
  → PASS: candidate (user/archon may PROMOTE → version++)
  → FAIL: rejected — recorded so the idea is never re-proposed
```

Forbidden forever: weakening constitution/permissions/verification/honesty,
hiding errors, gaming golden tests, permission erosion, absolute claims.

## Knowledge graph edge vocabulary

`EXECUTES · REQUIRES · VALIDATED_BY · BELONGS_TO · IMPROVES · SUPERSEDES ·
AUTHORITY_IN · CONTAINS · HANDLES · COMPOSES`

## Syllabus knowledge base (syllabus.py)

Official CBSE Subject-wise Syllabus 2026-27 (Sec 2 Phase 2) for Accountancy (055),
Business Studies (054) and Entrepreneurship (066), Classes XI & XII.

| Consumer | What it uses |
|---|---|
| `generators.gen_question_paper` | official A–E blueprint (80), ETP 70-mark structure, header unit weightage/typology, scope gate → `NEEDS_REVIEW` |
| `generators.gen_worksheet` / `gen_lesson_plan` | `Syllabus anchor:` unit line + scope validator |
| `orchestrator._propose` / `_critique` / `_concession` | `Syllabus anchor:` in proposals, out-of-scope concern with evidence, documented concession |
| `orchestrator` EXECUTE ctx | `ctx["syllabus"]` compact facts injected into every skill call |
| `seed.seed_syllabus` | idempotent KG (`subject:`/`syllabus:`/`unit:` nodes + CONTAINS/REQUIRES) + keyword-rich semantic memory (`syllabus_{subject}_{class}`) every boot |
| `GET /api/syllabus` | UI/inspection payload |

Validators: `marks_total`, `section_structure`, `syllabus_scope`, `answer_key_match` —
all deterministic and REAL (out-of-syllabus focus topics flip artifacts to `NEEDS_REVIEW`, C1).

## API surface

| Endpoint | Purpose |
|---|---|
| `POST /api/command` | text/voice command → task |
| `GET /api/syllabus` | full CBSE 2026-27 syllabus payload (units, marks, typology, scope notes) |
| `GET  /api/events` | SSE broadcast (steps, deliberation, quality, RSI, approvals) |
| `GET  /api/tasks/{id}` | task + messages + decisions |
| `POST /api/approvals/{id}` | approve L4 (resumes execution) / **reject with `feedback`** — feedback is mandatory on reject; it routes into the revision loop (`{decision:"approved\|rejected", feedback:"…"}`) |
| `POST /api/rsi/{id}/promote\|reject` | RSI lab actions (golden suite re-checked on promote) |
| `GET  /api/kg` · `/api/skills` · `/api/memory` · `/api/constitution` | explorers |
| `POST /api/control` | pause/resume/kill/reset_kill |
| `POST /api/settings` | language, autonomy, rounds, LLM key (masked on read) — the same key arms 🎤 Whisper |
| `POST /api/voice` | **mike pipeline**: `{audio_b64, mime, lang}` → OpenAI Whisper (`whisper-1`, multipart upload, 45s timeout) → `{text}`; honest errors: `no_key`(400) · `empty_transcript`(422) · upstream/network(502) · oversize(413). Zero-key → UI falls back to browser STT |
| `GET  /api/files` | **📁 file library** — every artifact joined with on-disk truth: name/kind/task/real bytes/timestamp/status + canonical `server_path`, `view` & `download` URLs, `kinds` counts, `dir` (permanent output folder). Powers the Files screen that answers "where did my download go?" |
| `GET  /api/artifacts/{task}/{name}` | artifact view (inline; names URL-decoded, spaces OK) |
| `GET  /api/artifacts/download/{filename}` | **forced file download** — `Content-Disposition: attachment; filename="…"`; traversal-safe (basename + realpath check); also accepts `/download/{task}/{name}` |

## Performance & guards

- `MAX_STEPS_PER_TASK=40`, `MAX_DELIBERATION_ROUNDS=3`, task budget ₹5 nominal
- Loop guard trips → safe halt with checkpoint (never silent completion)
- All SQLite writes serialized behind a re-entrant lock; SSE fan-out via queues
- LLM calls only in proposal prose (optional); validators are always code
