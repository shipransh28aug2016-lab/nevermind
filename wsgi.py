"""WSGI entry point — run NeverMind under Gunicorn or any WSGI server.

NeverMind's real HTTP stack is the stdlib ``ThreadingHTTPServer`` (keeps SSE
streaming, keep-alive and every route identical to ``python3 run.py``).
This adapter starts that stack exactly once in a daemon thread on an
internal loopback port and forwards each WSGI request to it — so the
production path and the dev path run the *same* server code.

Usage:
    gunicorn                     # auto-loads gunicorn.conf.py → wsgi:application
    gunicorn wsgi:application    # explicit

Note: use a threaded worker (gthread, default here: workers=1 threads=4).
SSE endpoints (/api/events) hold connections open — more workers would mean
more backend instances sharing the same SQLite files.
"""
from __future__ import annotations

import io
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from typing import Any, Callable, Dict, Iterable, List, Tuple

_lock = threading.Lock()
_backend_port: int | None = None

# hop-by-hop headers must not be forwarded (RFC 7230 §6.1)
_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
        "te", "trailer", "transfer-encoding", "upgrade"}


def _ensure_backend() -> int:
    """Start the real NeverMind server once on 127.0.0.1:<random free port>."""
    global _backend_port
    if _backend_port is not None:
        return _backend_port
    with _lock:
        if _backend_port is not None:
            return _backend_port
        from agentos.server import Handler, ensure_seed

        ensure_seed()                       # seed KG / skills / syllabus once
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        httpd.daemon_threads = True
        _backend_port = int(httpd.server_address[1])
        threading.Thread(target=httpd.serve_forever,
                         kwargs={"poll_interval": 0.2},
                         name="nevermind-wsgi-backend", daemon=True).start()
        return _backend_port


def _wsgi_headers(environ: Dict[str, Any]) -> List[Tuple[str, str]]:
    headers: List[Tuple[str, str]] = []
    for key, val in environ.items():
        if key.startswith("HTTP_"):
            name = key[5:].replace("_", "-").title()
            headers.append((name, val))
        elif key == "CONTENT_TYPE":
            headers.append(("Content-Type", val))
        elif key == "CONTENT_LENGTH":
            headers.append(("Content-Length", val))
    headers.append(("Host", environ.get("HTTP_HOST", "localhost")))
    headers.append(("Connection", "close"))     # one backend conn per request
    return headers


def application(environ: Dict[str, Any],
                start_response: Callable) -> Iterable[bytes]:
    """Standard WSGI application (PEP 3333)."""
    port = _ensure_backend()

    method = environ.get("REQUEST_METHOD", "GET")
    path = (environ.get("SCRIPT_NAME", "") or "") + (environ.get("PATH_INFO", "") or "/")
    qs = environ.get("QUERY_STRING") or ""
    target = f"{path}?{qs}" if qs else path

    try:
        clen = int(environ.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        clen = 0
    body = environ["wsgi.input"].read(clen) if clen else b""

    conn = HTTPConnection("127.0.0.1", port, timeout=300)
    try:
        conn.request(method, target, body=body, headers=dict(_wsgi_headers(environ)))
        resp = conn.getresponse()
    except Exception as exc:                     # backend down → honest 502
        payload = ('{"error": "NeverMind backend unreachable: %s"}'
                   % str(exc).replace('"', "'")).encode()
        start_response("502 Bad Gateway",
                       [("Content-Type", "application/json"),
                        ("Content-Length", str(len(payload)))])
        return [payload]

    status = f"{resp.status} {resp.reason}"
    resp_headers = [(k, v) for k, v in resp.getheaders()
                    if k.lower() not in _HOP]
    is_stream = (resp.getheader("Content-Type") or "").startswith("text/event-stream")
    start_response(status, resp_headers)

    if is_stream:
        # SSE: forward chunks as they arrive (worker thread blocks per stream)
        def _stream() -> Iterable[bytes]:
            try:
                while True:
                    chunk = resp.read1(4096) if hasattr(resp, "read1") else resp.read(4096)
                    if not chunk:
                        break
                    yield chunk
            finally:
                resp.close()
        return _stream()

    try:
        return [resp.read()]
    finally:
        resp.close()
