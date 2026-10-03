import ast

p = "/home/user/overmind/agentos/server.py"
t = open(p, encoding="utf-8").read()


def rep(t, old, new, label):
    c = t.count(old)
    assert c == 1, "%s: %d" % (label, c)
    return t.replace(old, new)


# ---- 1. module-level helpers after ensure_seed() -------------------------
anchor = '''def ensure_seed() -> None:
    global _seeded
    with SEED_LOCK:
        if not _seeded:
            seed_system(DBI, KG, SKILLS, MEMORY)
            _seeded = True
'''
helpers = anchor + '''

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
'''
t = rep(t, anchor, helpers, "helpers")

# ---- 2. GET routes right after /app route --------------------------------
route_anchor = '''            if path == "/app" or path == "/app.html":
                return self._static("app.html")
'''
routes = route_anchor + '''
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
'''
t = rep(t, route_anchor, routes, "routes")

ast.parse(t)
open(p, "w", encoding="utf-8").write(t)
print("auth helpers + routes installed, syntax OK")
