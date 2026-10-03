Phase: PostgreSQL + pgvector semantic memory migration for NEVERMIND.

Requirements:
1. Keep the MemorySystem API unchanged (remember/recall/semantic/procedure/…)
2. Add pgvector-backed semantic search alongside existing keyword recall
3. Migration must be reversible: SQLite remains valid fallback when Postgres is absent
4. Add embedding provider abstraction: offline hashing embedder default; OpenAI-compatible embeddings when key configured
5. Memory promotion policy unchanged: semantic items need authority ≥0.7 to activate (C1)
6. Tests: promotion, recall ranking, deprecation, conflict detection
7. Never store raw API keys or student PII in embeddings

Do not weaken the constitution or RSI gates.
