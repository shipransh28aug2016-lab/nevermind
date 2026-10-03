# NeverMind

**The offline-first, constitutionally-governed multi-agent OS for educators.**

NeverMind (formerly *Overmind*) runs a team of **9 specialist agents** and **21 deterministic skills**
that build CBSE-aligned teaching deliverables — question papers, worksheets, lesson plans, notice
letters, quizzes and more — and verifies every one of them before you see it.

![status](https://img.shields.io/badge/status-live%20and%20running-brightgreen) ![python](https://img.shields.io/badge/python-3.11%2B-blue) ![keys](https://img.shields.io/badge/API%20keys-required%20none-orange)

---

## Why NeverMind

| Promise | How it's enforced |
|---|---|
| **Never misguides you** | Constitutional articles **C1–C14** — honesty, no fake completion, no quarrelling between agents |
| **Follows the real syllabus** | Official **CBSE 2026-27** knowledge base: Accountancy (055), Business Studies (054), Entrepreneurship (066) × Classes XI/XII — unit-wise marks, typology weightage, topic lists, scope rules |
| **Validates its own work** | Deterministic validators: `marks_total` · `section_structure` · `syllabus_scope` · `answer_key_match` — out-of-syllabus requests flip to **NEEDS_REVIEW** with the reason printed on the artifact |
| **Works with zero API keys** | All skills are offline Python; add a provider key later in *Settings* to upgrade every agent |
| **Asks before acting** | HITL approval gates on L4/L5 actions; bounded deliberation rounds with documented concessions |
| **Bilingual** | English default, हिंदी one toggle away — commands, summaries, artifacts, landing page |

## Quick start

```bash
python3 run.py          # serves on http://0.0.0.0:8317
```

* **`/`** — launch landing page (features, syllabus preview, sign-in)
* **`/app.html`** — the multi-agent Control Center (guest mode, no login required)
* **`/api/health`** — liveness probe · **`/api/syllabus`** — full CBSE syllabus payload

Optional guardian watchdog (auto-restarts the server):

```bash
python3 guardian.py
```

## GitHub sign-in (launch login)

Sign-in is **optional** — guest mode always works. To activate *Continue with GitHub*:

1. GitHub → *Settings → Developer settings → New OAuth App*
2. **Homepage URL:** your deployed origin (e.g. `https://your-domain.example`)
3. **Authorization callback URL:** `https://your-domain.example/api/auth/github/callback`
4. Put the credentials where the server can read them (first match wins):

```bash
# Option A — file (git-ignored)
echo '{"client_id":"…","client_secret":"…"}' > data/github_oauth.json

# Option B — environment
export GITHUB_CLIENT_ID=… GITHUB_CLIENT_SECRET=…
```

Until configured, the landing page shows **“OAuth not configured yet”** honestly and everything
else keeps working. Sessions are HMAC-signed cookies (`data/.session_secret`,7-day expiry).

## Deployment

Four production-ready entry points — pick your platform:

| Mode | Command |
|---|---|
| Plain stdlib (zero deps) | `python3 run.py` |
| **pip + Gunicorn (WSGI)** | `pip install -r requirements.txt` → `gunicorn wsgi:application` |
| **Docker Compose** | `docker compose up -d` (port `8317:8317`, persistent `nevermind-data` volume) |
| **Conda** | `conda env create -f environment.yml && conda activate nevermind` |

* **`wsgi.py`** runs the *real* stdlib server in-process and adapts it for any
  WSGI host — SSE, static, auth and APIs behave identically to `run.py`.
* **`gunicorn.conf.py`** is auto-loaded: binds `$PORT` / `NEVERMIND_PORT` (PaaS-aware),
  `workers=1 threads=4` (one shared backend; SSE-safe).
* **`.env.example`** documents every variable (`NEVERMIND_*`, `GITHUB_CLIENT_ID/SECRET`,
  `NEVERMIND_SESSION_SECRET`). Copy to `.env` — Compose reads it automatically; the
  app itself never parses `.env`.
* **`render.yaml`** (Docker blueprint) and the plain `Dockerfile` remain available
  for Render / Fly / any container host.

## Project layout

```
run.py              entry point → http://0.0.0.0:8317
guardian.py         watchdog: health-ping + auto-restart
agentos/
  server.py         stdlib HTTP API + SSE + static host + GitHub OAuth
  orchestrator.py   plan → deliberate → gate → execute → verify → deliver
  deliberation.py   evidence-based multi-agent protocol (no quarrels)
  constitution.py   C1–C14 articles, enforced on every message
  syllabus.py       official CBSE 2026-27 syllabus knowledge base
  generators.py     question paper / worksheet / lesson plan / letter skills
  memory.py         semantic + episodic + procedural memory (SQLite)
  seed.py           idempotent agents, skills, KG and syllabus seeding
static/
  index.html        launch landing page
  app.html          Control Center (multi-agent UI)
docs/ARCHITECTURE.md  full architecture reference
data/               SQLite DB + OAuth config (git-ignored)
output/             generated artifacts (git-ignored)
```

## License

All rights reserved by the repository owner.
