# Gunicorn configuration for NeverMind (auto-loaded from the project root)
# Run: gunicorn wsgi:application
import os

# Public bind — PaaS hosts inject $PORT; explicit NEVERMIND_PORT wins.
bind = f"0.0.0.0:{os.environ.get('PORT') or os.environ.get('NEVERMIND_PORT') or '8317'}"

# workers=1 keeps ONE shared backend instance (SSE + SQLite behave predictably);
# threads handle concurrency — the real work happens in the backend's own
# ThreadingHTTPServer. Override only if you know your worker's implications.
workers = int(os.environ.get("GUNICORN_WORKERS", "1"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
worker_class = "gthread"

timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30

accesslog = "-"
errorlog = "-"
