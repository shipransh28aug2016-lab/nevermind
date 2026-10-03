Phase: Proactive Goal Manager for NEVERMIND (Step 8 of the original spec).

Build:
1. Goal hierarchy: mission → goals → subgoals → tasks (SQLite tables)
2. Event detector scanning: pending tasks, deadlines, stale artifacts, failed skills
3. Priority engine: urgency × impact × dependency × confidence, adjusted by risk/cost
4. Golden rule enforcement: "Don't create work merely because you can" — suggestion
   score threshold before any proactive action (impact × confidence × relevance)
5. Scheduled cycles: hourly/daily/weekly/monthly reviews (stdlib scheduler thread)
6. Proactive suggestions surface in the Control Center as APPROVAL items when L4,
   or as READY drafts when ≤ L2

Hard limits: MAX_STEPS, MAX_COST, kill switch respect, full audit (C10).
