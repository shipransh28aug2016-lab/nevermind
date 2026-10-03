# NeverMind — offline-first multi-agent OS (stdlib Python only)
FROM python:3.12-slim

# tzdata for IST-friendly timestamps; curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# code first (layer-stable); runtime data lives in a mounted volume
COPY agentos/ agentos/
COPY static/ static/
COPY docs/ docs/
COPY run.py guardian.py README.md ./

# runtime dirs (overridden by a mounted volume in production)
RUN mkdir -p data output

ENV NEVERMIND_HOST=0.0.0.0 \
    NEVERMIND_PORT=8317 \
    PYTHONUNBUFFERED=1

EXPOSE 8317

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8317/api/health || exit 1

CMD ["python3", "run.py"]
