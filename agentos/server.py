"""HTTP API + SSE server — stdlib only (ThreadingHTTPServer).

Endpoints:
  GET  /                      → launch landing page
  GET  /app.html              → control center (dashboard)
  GET  /api/auth/status|github|me|logout  → GitHub OAuth login flow
  GET  /api/bootstrap         → initial state
  POST /api/command           → issue text/voice command
  GET  /api/events            → SSE stream
  GET  /api/tasks, /api/tasks/{id}
  GET  /api/files              → file library (📁 Files screen)
  GET  /api/skills, /api/kg, /api/memory, /api/rsi, /api/audit, /api/approvals
  POST /api/approvals/{id}    → approve | reject
  POST /api/rsi/{id}/promote|reject
  GET  /api/constitution
  POST /api/settings          → language / autonomy / llm / kill / pause
  POST /api/control           → {action: pause|resume|kill|reset_kill}
  GET  /api/artifacts/{task}/{name}  → view artifact inline
  GET  /api/artifacts/download/{filename}  → FORCED download (Content-Disposition:
       attachment; filename="...") — permanent fix for the broken OPEN button
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import queue
import secrets
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional

from .config import DATA_DIR, HOST, OUTPUT_DIR, PORT, STATIC_DIR
from .constitution import ARTICLES, ConstitutionGuard
from .db import DBI
from .events import BUS
from .knowledge_graph import KnowledgeGraph
from .memory import MemorySystem, LAYERS
from . import syllabus as SYL
from .orchestrator import Orchestrator, detect_lang
from .rsi import RSIEngine
from .seed import seed_system
from .skills import SkillRegistry

# singletons
KG = KnowledgeGraph(DBI)
SKILLS = SkillRegistry(DBI, KG)
MEMORY = MemorySystem(DBI)
ORCH = Orchestrator(DBI, KG, SKILLS, MEMORY)
RSI = RSIEngine(DBI, SKILLS)
SEED_LOCK = threading.Lock()
_seeded = False


def ensure_seed() -> None:
    global _seeded
    with SEED_LOCK:
        if not _seeded:
            seed_system(DBI, KG, SKILLS, MEMORY)
            _seeded = True


# ------------------------------------------------------- GitHub OAuth (login)
_AUTH_PENDING: Dict[str, float] = {}          # state -> expiry (unix ts)


def _oauth_creds() -> tuple:
    """(client_id, client_secret) from env or data/github_oauth.json."""
    cid = os.environ.get("GITHUB_CLIENT_ID", "").strip()
    sec = os.environ.get("GITHUB_CLIENT_SECRET", "").strip()
    if not cid:
        try:
            with open(os.path.join(DATA_DIR, "github_oauth.json"),
                      encoding="utf-8") as f:
                d = json.load(f)
            cid = str(d.get("client_id", "")).strip()
            sec = str(d.get("client_secret", "")).strip()
        except Exception:
            pass
    return cid, sec


def _session_secret() -> bytes:
    env = os.environ.get("NEVERMIND_SESSION_SECRET", "").strip()
    if env:
        return env.encode()
    path = os.path.join(DATA_DIR, ".session_secret")
    try:
        with open(path, "rb") as f:
            s = f.read().strip()
        if s:
            return s
    except OSError:
        pass
    s = secrets.token_hex(32).encode()
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(s)
    except FileExistsError:
        try:
            with open(path, "rb") as f:
                s = f.read().strip() or s
        except OSError:
            pass
    return s


def _sign_session(payload: Dict[str, Any]) -> str:
    raw = base64.urlsafe_b64encode(
        json.dumps(payload, ensure_ascii=False).encode()).decode().rstrip("=")
    mac = hmac.new(_session_secret(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{mac}"


def _verify_session(token: str) -> Optional[Dict[str, Any]]:
    try:
        raw, mac = token.split(".", 1)
        want = hmac.new(_session_secret(), raw.encode(),
                        hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, want):
            return None
        payload = json.loads(base64.urlsafe_b64decode(
            raw + "=" * (-len(raw) % 4)))
        if float(payload.get("exp", 0)) < time.time():
            return None
        return payload
    except Exception:
        return None


class Handler(BaseHTTPRequestHandler):
    server_version = "NeverMindHTTP/1.0"
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------------
    def log_message(self, fmt: str, *args: Any) -> None:  # quiet
        pass

    # -- helpers -------------------------------------------------------
    def _json(self, obj: Any, status: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length > 16 * 1024 * 1024:   # voice clips: ≤8 MB audio → ~11 MB b64
            raise ValueError("payload too large")
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _static(self, rel: str) -> None:
        path = os.path.normpath(os.path.join(STATIC_DIR, rel))
        if not path.startswith(STATIC_DIR) or not os.path.isfile(path):
            self._json({"error": "not found"}, 404)
            return
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ------------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            qs = urllib.parse.parse_qs(parsed.query)

            if path == "/" or path == "/index.html":
                return self._static("index.html")
            if path == "/app" or path == "/app.html":
                return self._static("app.html")

            # ---- GitHub OAuth (launch login) --------------------------
            if path == "/api/auth/status":
                cid, _ = _oauth_creds()
                return self._json({"provider": "github", "configured": bool(cid)})
            if path == "/api/auth/github":
                cid, _ = _oauth_creds()
                if not cid:
                    return self._json(
                        {"error": "GitHub OAuth not configured yet — set GITHUB_CLIENT_ID "
                                  "/ GITHUB_CLIENT_SECRET env or data/github_oauth.json"},
                        400)
                state = secrets.token_hex(16)
                _AUTH_PENDING[state] = time.time() + 600
                host = self.headers.get("Host") or f"{HOST}:{PORT}"
                fwd = (self.headers.get("X-Forwarded-Proto") or "").lower()
                scheme = "https" if (fwd == "https" or
                                     host.endswith(".e2b.app")) else "http"
                redirect_uri = f"{scheme}://{host}/api/auth/github/callback"
                url = ("https://github.com/login/oauth/authorize"
                       f"?client_id={urllib.parse.quote(cid)}"
                       f"&redirect_uri={urllib.parse.quote(redirect_uri, safe='')}"
                       f"&state={state}&scope=read:user")
                self.send_response(302)
                self.send_header("Location", url)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if path == "/api/auth/github/callback":
                state = (qs.get("state") or [""])[0]
                code = (qs.get("code") or [""])[0]
                exp = _AUTH_PENDING.pop(state, None)
                if not exp or exp < time.time() or not code:
                    return self._json({"error": "invalid or expired OAuth state"}, 400)
                cid, sec = _oauth_creds()
                if not cid or not sec:
                    return self._json({"error": "OAuth credentials missing"}, 400)
                try:
                    req = urllib.request.Request(
                        "https://github.com/login/oauth/access_token",
                        data=urllib.parse.urlencode(
                            {"client_id": cid, "client_secret": sec,
                             "code": code}).encode(),
                        headers={"Accept": "application/json",
                                 "User-Agent": "NeverMind"})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        tok = json.loads(resp.read().decode()).get("access_token") or ""
                    if not tok:
                        return self._json({"error": "GitHub token exchange failed"}, 502)
                    ureq = urllib.request.Request(
                        "https://api.github.com/user",
                        headers={"Authorization": f"Bearer {tok}",
                                 "Accept": "application/vnd.github+json",
                                 "User-Agent": "NeverMind"})
                    with urllib.request.urlopen(ureq, timeout=15) as resp:
                        user = json.loads(resp.read().decode())
                except Exception as e:
                    return self._json({"error": f"GitHub request failed: {e}"}, 502)
                payload = {"login": user.get("login") or "user",
                           "name": user.get("name") or user.get("login") or "User",
                           "avatar": user.get("avatar_url") or "",
                           "exp": time.time() + 7 * 86400}
                self.send_response(302)
                self.send_header(
                    "Set-Cookie",
                    f"nm_session={_sign_session(payload)}; Path=/; "
                    "HttpOnly; SameSite=Lax; Max-Age=604800")
                self.send_header("Location", "/app.html")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if path == "/api/auth/me":
                cookie = self.headers.get("Cookie") or ""
                token = None
                for part in cookie.split(";"):
                    part = part.strip()
                    if part.startswith("nm_session="):
                        token = part[len("nm_session="):]
                        break
                payload = _verify_session(token) if token else None
                if not payload:
                    return self._json({"authenticated": False}, 401)
                return self._json({"authenticated": True,
                                   "user": {"login": payload.get("login"),
                                            "name": payload.get("name"),
                                            "avatar": payload.get("avatar")}})
            if path == "/api/auth/logout":
                self.send_response(302)
                self.send_header("Set-Cookie",
                                 "nm_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0")
                self.send_header("Location", "/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if path.startswith("/static/"):
                return self._static(path[len("/static/"):])

            if path == "/api/health":
                # ultra-light wake probe — used by the UI and the guardian watchdog
                return self._json({"ok": True, "ts": time.time(), "alive": True})
            if path == "/api/bootstrap":
                return self._json(self._bootstrap())
            if path == "/api/events":
                return self._sse(qs)
            if path == "/api/tasks":
                return self._json({"tasks": DBI.list_tasks(80)})
            if path.startswith("/api/tasks/"):
                tid = path.split("/")[3]
                task = DBI.get_task(tid)
                if not task:
                    return self._json({"error": "not found"}, 404)
                return self._json({
                    "task": task,
                    "messages": DBI.messages_for(tid),
                    "decisions": DBI.decisions_for(tid),
                })
            if path == "/api/skills":
                return self._json({"skills": SKILLS.list_manifests()})
            if path == "/api/kg":
                g = KG.graph()
                g["report"] = KG.degree_report()
                return self._json(g)
            if path == "/api/memory":
                return self._json({"stats": MEMORY.stats(),
                                   "memories": MEMORY.all(),
                                   "layers": LAYERS})
            if path == "/api/rsi":
                return self._json({"proposals": DBI.rsi_list(80),
                                   "golden_suite": [t["name"] for t in RSI.golden_suite()]})
            if path == "/api/audit":
                return self._json({"audit": DBI.audit_tail(150),
                                   "decisions": DBI._q(
                                       "SELECT * FROM decisions ORDER BY id DESC LIMIT 80")})
            if path == "/api/approvals":
                return self._json({"approvals": DBI.approvals()})
            if path == "/api/constitution":
                return self._json(ConstitutionGuard.brief())
            if path == "/api/settings":
                return self._json({"settings": self._settings_safe()})
            if path == "/api/syllabus":
                return self._json({"syllabus": SYL.payload()})
            if path == "/api/files":
                return self._json(self._file_library())
            if path == "/api/output_files":
                files = []
                for name in sorted(os.listdir(OUTPUT_DIR), reverse=True)[:200]:
                    p = os.path.join(OUTPUT_DIR, name)
                    if os.path.isfile(p):
                        files.append({"name": name, "bytes": os.path.getsize(p)})
                return self._json({"files": files})
            if path.startswith("/api/artifacts/"):
                parts = path.split("/")
                # ---- forced-download route (permanent OPEN-button fix) --------
                # GET /api/artifacts/download/{filename}   → output/<filename>
                # GET /api/artifacts/download/{task}/{name} → output/{task}_{name}
                # Served with Content-Disposition: attachment so the browser
                # SAVES .md/.json/.txt files instead of navigating/blanking.
                if len(parts) >= 4 and parts[3] == "download":
                    if len(parts) == 5:
                        raw = urllib.parse.unquote(parts[4])
                    elif len(parts) == 6:
                        raw = f"{urllib.parse.unquote(parts[4])}_" \
                              f"{urllib.parse.unquote(parts[5])}"
                    else:
                        return self._json({"error": "bad download path"}, 400)
                    return self._send_attachment(raw)
                if len(parts) == 5:      # /api/artifacts/{task}/{name}
                    safe = os.path.basename(urllib.parse.unquote(parts[4]))
                    fp = os.path.join(OUTPUT_DIR, f"{parts[3]}_{safe}")
                    if not os.path.isfile(fp):
                        # allow listing by task
                        return self._json({"error": "artifact not found"}, 404)
                    with open(fp, "rb") as f:
                        data = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/markdown; charset=utf-8")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                if len(parts) == 4:      # /api/artifacts/{task} → list
                    tid = parts[3]
                    out = []
                    prefix = f"{tid}_"
                    for name in os.listdir(OUTPUT_DIR):
                        if name.startswith(prefix):
                            out.append({"name": name[len(prefix):],
                                        "path": f"/api/artifacts/{tid}/{name[len(prefix):]}"})
                    return self._json({"artifacts": out})

            return self._json({"error": "unknown endpoint"}, 404)
        except BrokenPipeError:
            pass
        except ValueError as e:
            try:
                self._json({"error": str(e)}, 413 if "too large" in str(e) else 400)
            except Exception:
                pass
        except Exception as e:  # pragma: no cover
            try:
                self._json({"error": str(e)}, 500)
            except Exception:
                pass

    # ------------------------------------------------------------------
    def _file_library(self) -> Dict[str, Any]:
        """GET /api/files — the 📁 Files screen: every artifact joined with
        on-disk truth (real size, exists flag), canonical server path plus
        view/download URLs. Answers "where did my download go?": `dir` below
        is the permanent server copy; DOWNLOAD gives a second copy in the
        user's browser Downloads folder."""
        rows = DBI._q(
            "SELECT task_id, name, kind, path, status, sha, bytes, ts "
            "FROM artifacts ORDER BY ts DESC LIMIT 500")
        files = []
        seen = set()
        for r in rows:
            disk = os.path.basename(r.get("path") or "")
            fp = os.path.join(OUTPUT_DIR, disk) if disk else ""
            on = bool(disk) and os.path.isfile(fp)
            if disk:
                seen.add(disk)
            files.append({
                "name": r.get("name") or disk,
                "task_id": r.get("task_id") or "",
                "kind": r.get("kind") or "file",
                "status": r.get("status") or "",
                "sha": r.get("sha") or "",
                "bytes": (os.path.getsize(fp) if on
                          else int(r.get("bytes") or 0)),
                "ts": r.get("ts") or 0.0,
                "exists": on,
                "server_path": fp if on else "",
                "view": (f"/api/artifacts/{r.get('task_id')}/"
                         f"{urllib.parse.quote(r.get('name') or disk)}") if on else "",
                "download": (f"/api/artifacts/download/"
                             f"{urllib.parse.quote(disk)}") if on else "",
            })
        # disk-only files (defensive: every file should have a DB row)
        try:
            for n in os.listdir(OUTPUT_DIR):
                fp2 = os.path.join(OUTPUT_DIR, n)
                if not os.path.isfile(fp2) or n in seen:
                    continue
                files.append({
                    "name": n,
                    "task_id": (n.split("_")[0] if n.startswith("T-") else ""),
                    "kind": "file", "status": "", "sha": "",
                    "bytes": os.path.getsize(fp2),
                    "ts": os.path.getmtime(fp2), "exists": True,
                    "server_path": fp2, "view": "",
                    "download": f"/api/artifacts/download/{urllib.parse.quote(n)}",
                })
        except OSError:
            pass
        files.sort(key=lambda f: f.get("ts") or 0.0, reverse=True)
        kinds: Dict[str, int] = {}
        total = 0
        for f in files:
            kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
            total += int(f["bytes"] or 0)
        return {"files": files, "count": len(files), "bytes": total,
                "kinds": kinds, "dir": os.path.realpath(OUTPUT_DIR)}

    # ------------------------------------------------------------------
    _ATTACH_CT = {".md": "text/markdown; charset=utf-8",
                  ".json": "application/json; charset=utf-8",
                  ".txt": "text/plain; charset=utf-8",
                  ".csv": "text/csv; charset=utf-8",
                  ".html": "text/html; charset=utf-8",
                  ".pdf": "application/pdf"}

    def _send_attachment(self, filename: str) -> None:
        """Serve output/<filename> as a FORCED browser download.

        The header `Content-Disposition: attachment; filename="..."` is the
        permanent fix for the UI OPEN button: browsers (and the sandboxed
        preview iframe, which blocks target=_blank) must SAVE the artifact
        to the user's device rather than try to render it in a tab.
        """
        # traversal guard: pure basename only, then realpath must stay in output/
        safe = os.path.basename(filename.replace("\\", "/"))
        if not safe or safe != filename or safe in (".", ".."):
            return self._json({"error": "invalid filename"}, 400)
        fp = os.path.realpath(os.path.join(OUTPUT_DIR, safe))
        if not fp.startswith(os.path.realpath(OUTPUT_DIR) + os.sep):
            return self._json({"error": "invalid path"}, 400)
        if not os.path.isfile(fp):
            return self._json({"error": "file not found"}, 404)
        with open(fp, "rb") as f:
            data = f.read()
        ext = os.path.splitext(safe)[1].lower()
        ctype = (self._ATTACH_CT.get(ext)
                 or mimetypes.guess_type(safe)[0]
                 or "application/octet-stream")
        # header-injection guard: single-line ASCII filename in the header
        fname = (safe.encode("ascii", "replace").decode("ascii")
                 .replace('"', "").replace("\r", "").replace("\n", ""))
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    # ------------------------------------------------------------------
    def do_POST(self) -> None:  # noqa: N802
        try:
            path = urllib.parse.urlparse(self.path).path
            body = self._read_json()

            if path == "/api/command":
                text = (body.get("text") or "").strip()
                if not text:
                    return self._json({"error": "empty command"}, 400)
                lang = body.get("lang") or detect_lang(text)
                task_id = ORCH.submit(text, lang=lang)
                return self._json({"task_id": task_id, "lang": lang}, 201)

            if path.startswith("/api/approvals/"):
                aid = path.split("/")[3]
                decision = body.get("decision")
                if decision not in ("approved", "rejected"):
                    return self._json({"error": "decision must be approved|rejected"}, 400)
                feedback = (body.get("feedback") or "").strip()
                if decision == "rejected" and not feedback:
                    return self._json({"error": "feedback required when rejecting "
                                                "(revision loop)"}, 400)
                row = DBI.resolve_approval(aid, decision, feedback or None)
                if not row:
                    return self._json({"error": "not found"}, 404)
                DBI.audit("user", f"approval_{decision}", aid,
                          {"feedback": feedback} if feedback else {})
                BUS.publish("approval.resolved",
                            {"id": aid, "decision": decision,
                             "feedback": feedback or None},
                            task_id=row.get("task_id"))
                if decision == "rejected" and feedback:
                    BUS.publish("approval.feedback",
                                {"id": aid, "feedback": feedback},
                                task_id=row.get("task_id"))
                return self._json({"approval": row})

            if path == "/api/voice":
                return self._transcribe(body)

            if path.startswith("/api/rsi/") and path.endswith("/promote"):
                pid = int(path.split("/")[3])
                res = RSI.promote(pid)
                return self._json(res, 200 if res.get("ok") else 409)
            if path.startswith("/api/rsi/") and path.endswith("/reject"):
                pid = int(path.split("/")[3])
                res = RSI.reject(pid, body.get("reason", "user rejected"))
                return self._json(res)

            if path == "/api/settings":
                return self._save_settings(body)

            if path == "/api/control":
                action = body.get("action")
                if action == "pause":
                    ORCH.set_pause(True)
                    DBI.set_setting("paused", True)
                elif action == "resume":
                    ORCH.set_pause(False)
                    DBI.set_setting("paused", False)
                elif action == "kill":
                    ORCH.set_kill(True)
                    DBI.set_setting("kill", True)
                elif action == "reset_kill":
                    ORCH.set_kill(False)
                    DBI.set_setting("kill", False)
                else:
                    return self._json({"error": "unknown action"}, 400)
                DBI.audit("user", f"control_{action}", "", {})
                return self._json({"ok": True, "action": action})

            if path.startswith("/api/artifacts/") and path.endswith("/refresh"):
                return self._json({"ok": True})

            return self._json({"error": "unknown endpoint"}, 404)
        except BrokenPipeError:
            pass
        except Exception as e:  # pragma: no cover
            try:
                self._json({"error": str(e)}, 500)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Voice → text: OpenAI Whisper transcription (mike pipeline).
    # Browser records audio → POST /api/voice {audio_b64,mime,lang} → this
    # uploads it to {base}/audio/transcriptions → returns {"text": ...}.
    # Zero-key: 400 no_key so the UI falls back to browser STT (offline-first).
    # ------------------------------------------------------------------
    def _transcribe(self, body: Dict[str, Any]):
        import base64 as _b64
        import uuid as _uuid
        import urllib.request as _urlreq
        import urllib.error as _urlerr

        audio_b64 = body.get("audio_b64")
        if not isinstance(audio_b64, str) or not audio_b64:
            return self._json({"error": "audio_b64 required"}, 400)
        mime = (body.get("mime") or "audio/webm").split(";")[0].strip() or "audio/webm"
        if not mime.startswith("audio/"):
            return self._json({"error": "mime must be audio/*"}, 400)
        lang = body.get("lang") if body.get("lang") in ("en", "hi") else None
        try:
            audio = _b64.b64decode(audio_b64, validate=True)
        except Exception:
            return self._json({"error": "invalid base64 audio"}, 400)
        if len(audio) < 400:
            return self._json({"error": "audio too short — hold the mic longer"}, 400)
        if len(audio) > 8 * 1024 * 1024:
            return self._json({"error": "audio exceeds 8 MB"}, 413)

        voice = DBI.get_setting("voice", {}) or {}
        llm = DBI.get_setting("llm", {}) or {}
        key = voice.get("api_key") or llm.get("api_key")
        if not key:
            return self._json({
                "error": "no_key",
                "hint": "Whisper needs an OpenAI API key — Settings → API key. "
                        "Without a key the mic falls back to browser STT."}, 400)
        base = (voice.get("base_url") or llm.get("base_url")
                or "https://api.openai.com/v1").rstrip("/")
        if "api.openai.com" in base and not base.endswith("/v1"):
            base += "/v1"
        model = voice.get("model") or "whisper-1"
        url = base + "/audio/transcriptions"

        ext = {"audio/webm": "webm", "audio/mp4": "m4a", "audio/ogg": "ogg",
               "audio/mpeg": "mp3", "audio/wav": "wav",
               "audio/x-wav": "wav"}.get(mime, "webm")
        bnd = "----nevermind" + _uuid.uuid4().hex
        head = (f"--{bnd}\r\nContent-Disposition: form-data; name=\"file\"; "
                f"filename=\"audio.{ext}\"\r\nContent-Type: {mime}\r\n\r\n").encode()
        mid = (f"\r\n--{bnd}\r\nContent-Disposition: form-data; "
               f"name=\"model\"\r\n\r\n{model}\r\n").encode()
        lang_part = (f"--{bnd}\r\nContent-Disposition: form-data; "
                     f"name=\"language\"\r\n\r\n{lang}\r\n").encode() if lang else b""
        tail = f"--{bnd}--\r\n".encode()
        payload = head + audio + mid + lang_part + tail

        req = _urlreq.Request(url, data=payload, method="POST", headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": f"multipart/form-data; boundary={bnd}",
        })
        try:
            with _urlreq.urlopen(req, timeout=45) as resp:
                out = json.loads(resp.read().decode("utf-8", "replace"))
        except _urlerr.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            DBI.audit("system", "voice_transcribe_fail", "",
                      {"status": e.code, "detail": detail[:160]})
            return self._json({"error": f"whisper_http_{e.code}", "detail": detail}, 502)
        except Exception as e:
            DBI.audit("system", "voice_transcribe_fail", "", {"error": str(e)[:160]})
            return self._json({"error": "whisper_unreachable", "detail": str(e)[:300],
                               "hint": "no network to the transcription API"}, 502)

        text = (out.get("text") or "").strip()
        DBI.audit("user", "voice_transcribe", "",
                  {"chars": len(text), "model": model, "lang": lang or "auto"})
        if not text:
            return self._json({"error": "empty_transcript",
                               "hint": "Whisper heard audio but no words — "
                                       "speak longer/closer"}, 422)
        return self._json({"text": text, "model": model,
                           "provider": "openai-whisper"})

    def _settings_safe(self) -> Dict[str, Any]:
        s = DBI.get_setting("llm", {}) or {}
        masked = dict(s)
        if masked.get("api_key"):
            masked["api_key"] = masked["api_key"][:6] + "…" + masked["api_key"][-3:]
            masked["api_key_set"] = True
        else:
            masked.pop("api_key", None)
            masked["api_key_set"] = False
        return {
            "autonomy_mode": DBI.get_setting("autonomy_mode", "SEMI_AUTONOMOUS"),
            "language": DBI.get_setting("language", "en"),
            "max_rounds": DBI.get_setting("max_rounds", 3),
            "kill": DBI.get_setting("kill", False),
            "paused": DBI.get_setting("paused", False),
            "llm": masked,
            # Whisper voice pipeline: shares the OpenAI key from `llm`;
            # whisper_ready tells the mic button which path to take.
            "voice": {"provider": "openai-whisper",
                      "model": (DBI.get_setting("voice", {}) or {}).get("model",
                                                                       "whisper-1"),
                      "api_key_set": masked.get("api_key_set", False),
                      "whisper_ready": bool(masked.get("api_key_set"))},
        }

    def _save_settings(self, body: Dict[str, Any]):
        if "autonomy_mode" in body:
            mode = body["autonomy_mode"]
            from .config import AUTONOMY_MODES
            if mode in AUTONOMY_MODES:
                DBI.set_setting("autonomy_mode", mode)
                ORCH.decider.autonomy_mode = mode
        if "language" in body:
            DBI.set_setting("language", body["language"])
        if "max_rounds" in body:
            try:
                DBI.set_setting("max_rounds", max(1, min(5, int(body["max_rounds"]))))
            except (TypeError, ValueError):
                pass
        if "llm" in body:
            cur = DBI.get_setting("llm", {}) or {}
            llm = body["llm"] or {}
            merged = dict(cur)
            for k in ("base_url", "model"):
                if k in llm:
                    merged[k] = llm[k]
            if "api_key" in llm:
                key = llm["api_key"]
                if key and not key.endswith("…"):  # ignore masked value round-trip
                    merged["api_key"] = key
                elif key == "":
                    merged.pop("api_key", None)
            DBI.set_setting("llm", merged)
        DBI.audit("user", "settings_update", "", {k: v for k, v in body.items()
                                                  if k != "llm"})
        return self._json({"ok": True, "settings": self._settings_safe()})

    # ------------------------------------------------------------------
    def _bootstrap(self) -> Dict[str, Any]:
        from .agents import roster
        return {
            "system": {"name": DBI.get_setting("system_name", "NeverMind"),
                       "version": DBI.get_setting("version", "1.0.0")},
            "agents": roster(),
            "settings": self._settings_safe(),
            "tasks": DBI.list_tasks(25),
            "approvals": [a for a in DBI.approvals() if a["status"] == "pending"],
            "stats": {
                "tasks_total": DBI._q1("SELECT COUNT(*) c FROM tasks")["c"],
                "tasks_completed": DBI._q1(
                    "SELECT COUNT(*) c FROM tasks WHERE status LIKE 'COMPLETED%'")["c"],
                "skills": len(SKILLS.list_manifests()),
                "memories": MEMORY.stats(),
                "rsi_open": DBI._q1("SELECT COUNT(*) c FROM rsi_proposals "
                                    "WHERE status IN ('candidate','testing')")["c"],
                "kg": KG.degree_report(),
            },
            "constitution": {"articles": len(ARTICLES)},
            "history": BUS.history(limit=60),
        }

    # ------------------------------------------------------------------
    def _sse(self, qs: Dict[str, list]) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        q = BUS.subscribe()
        task_filter = (qs.get("task") or [None])[0]
        try:
            # hello
            hello = json.dumps({"type": "hello", "ts": time.time()})
            self.wfile.write(f"data: {hello}\n\n".encode())
            self.wfile.flush()
            while True:
                try:
                    ev = q.get(timeout=20)
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                if task_filter and ev.get("task_id") not in (task_filter, None):
                    continue
                data = json.dumps(ev, ensure_ascii=False)
                self.wfile.write(f"data: {data}\n\n".encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            BUS.unsubscribe(q)


def _port_alive(timeout: float = 1.0) -> bool:
    import socket
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=timeout):
            return True
    except OSError:
        return False


def serve() -> None:
    """Bind and serve. Race-tolerant by design: profile-hook, guardian and the
    platform process wrapper may start us concurrently — the loser STANDBYs
    (never crash-loops) and takes over automatically within ~5s if the serving
    instance ever dies. The preview port therefore always has a live owner."""
    ensure_seed()
    import errno
    httpd = None
    while httpd is None:
        try:
            httpd = ThreadingHTTPServer((HOST, PORT), Handler)
        except OSError as e:
            if getattr(e, "errno", None) != errno.EADDRINUSE:
                raise
            print(f"[standby] port {PORT} already served — waiting to take over",
                  flush=True)
            while _port_alive():
                time.sleep(5)
            print("[standby] serving instance gone — re-binding", flush=True)
    httpd.daemon_threads = True
    print(f"NEVERMIND agent OS → http://{HOST}:{PORT}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()
