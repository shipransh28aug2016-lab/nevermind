"""SQLite persistence — durable source of truth (stdlib sqlite3, zero deps)."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from .config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  command TEXT NOT NULL,
  lang TEXT DEFAULT 'en',
  status TEXT NOT NULL,
  plan_json TEXT,
  decision_json TEXT,
  quality_json TEXT,
  summary TEXT,
  summary_hi TEXT,
  artifacts_json TEXT DEFAULT '[]',
  rounds INTEGER DEFAULT 0,
  steps INTEGER DEFAULT 0,
  cost REAL DEFAULT 0.0,
  confidence REAL DEFAULT 0.0,
  created_at REAL,
  updated_at REAL
);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT NOT NULL,
  round INTEGER,
  mtype TEXT NOT NULL,
  from_agent TEXT,
  to_agent TEXT,
  body TEXT,
  payload_json TEXT,
  ts REAL
);
CREATE INDEX IF NOT EXISTS idx_messages_task ON messages(task_id);

CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT,
  intent TEXT,
  action TEXT,
  confidence REAL,
  risk REAL,
  reversibility TEXT,
  autonomy_level INTEGER,
  mode TEXT,
  reasoning TEXT,
  requires_approval INTEGER DEFAULT 0,
  ts REAL
);

CREATE TABLE IF NOT EXISTS artifacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT,
  name TEXT,
  kind TEXT,
  path TEXT,
  status TEXT,
  sha TEXT,
  bytes INTEGER,
  ts REAL
);

CREATE TABLE IF NOT EXISTS memories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  layer TEXT NOT NULL,           -- episodic | semantic | procedural | performance | decision
  key TEXT,
  content TEXT,
  confidence REAL DEFAULT 0.5,
  source TEXT,
  status TEXT DEFAULT 'active',  -- active | candidate | deprecated | protected
  hits INTEGER DEFAULT 0,
  created_at REAL,
  updated_at REAL
);

CREATE TABLE IF NOT EXISTS kg_nodes (
  id TEXT PRIMARY KEY,
  ntype TEXT,                    -- agent | skill | tool | validator | domain | knowledge | artifact
  label TEXT,
  props_json TEXT,
  created_at REAL
);

CREATE TABLE IF NOT EXISTS kg_edges (
  src TEXT,
  dst TEXT,
  etype TEXT,
  props_json TEXT,
  PRIMARY KEY (src, dst, etype)
);

CREATE TABLE IF NOT EXISTS skills (
  id TEXT PRIMARY KEY,
  name TEXT,
  category TEXT,
  version TEXT DEFAULT '1.0.0',
  triggers_json TEXT,
  input_schema_json TEXT,
  output_schema_json TEXT,
  validators_json TEXT,
  autonomy INTEGER DEFAULT 2,
  risk REAL DEFAULT 0.1,
  status TEXT DEFAULT 'active',
  runs INTEGER DEFAULT 0,
  successes INTEGER DEFAULT 0,
  last_score REAL,
  created_at REAL,
  updated_at REAL
);

CREATE TABLE IF NOT EXISTS rsi_proposals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT,                     -- skill | prompt | procedure | routing | validator | cost
  title TEXT,
  hypothesis TEXT,
  evidence_json TEXT,
  status TEXT DEFAULT 'candidate', -- candidate | testing | promoted | rejected | sandboxed
  baseline_score REAL,
  candidate_score REAL,
  regression_cost TEXT,
  anti_habit_check TEXT,
  version_before TEXT,
  version_after TEXT,
  ts REAL
);

CREATE TABLE IF NOT EXISTS golden_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  proposal_id INTEGER,
  test_name TEXT,
  passed INTEGER,
  detail TEXT,
  ts REAL
);

CREATE TABLE IF NOT EXISTS approvals (
  id TEXT PRIMARY KEY,
  task_id TEXT,
  action TEXT,
  reason TEXT,
  risk REAL,
  preview TEXT,
  status TEXT DEFAULT 'pending',  -- pending | approved | rejected
  feedback TEXT,                  -- HITL reject feedback → revision loop
  created_at REAL,
  resolved_at REAL
);

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor TEXT,
  action TEXT,
  ref TEXT,
  detail_json TEXT,
  ts REAL
);

CREATE TABLE IF NOT EXISTS settings (
  k TEXT PRIMARY KEY,
  v TEXT
);
"""


class DB:
    def __init__(self, path: str = DB_PATH) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            # -- migration: approvals.feedback (HITL revision loop) -------------
            cols = {r["name"] for r in self._q("PRAGMA table_info(approvals)")}
            if "feedback" not in cols:
                try:
                    self._exec("ALTER TABLE approvals ADD COLUMN feedback TEXT")
                except Exception:
                    pass
            self._conn.commit()

    # -- helpers ----------------------------------------------------------
    def _exec(self, sql: str, args: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, args)
            self._conn.commit()
            return cur

    def _q(self, sql: str, args: tuple = ()) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    def _q1(self, sql: str, args: tuple = ()) -> Optional[Dict[str, Any]]:
        rows = self._q(sql, args)
        return rows[0] if rows else None

    # -- tasks ------------------------------------------------------------
    def create_task(self, task: Dict[str, Any]) -> None:
        self._exec(
            "INSERT OR REPLACE INTO tasks(id,command,lang,status,plan_json,decision_json,"
            "quality_json,summary,summary_hi,artifacts_json,rounds,steps,cost,confidence,"
            "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                task["id"], task["command"], task.get("lang", "en"), task["status"],
                json.dumps(task.get("plan"), ensure_ascii=False),
                json.dumps(task.get("decision"), ensure_ascii=False),
                json.dumps(task.get("quality"), ensure_ascii=False),
                task.get("summary"), task.get("summary_hi"),
                json.dumps(task.get("artifacts", []), ensure_ascii=False),
                task.get("rounds", 0), task.get("steps", 0), task.get("cost", 0.0),
                task.get("confidence", 0.0),
                task.get("created_at", time.time()), time.time(),
            ),
        )

    def update_task(self, task_id: str, **fields: Any) -> None:
        if not fields:
            return
        cols, vals = [], []
        for k, v in fields.items():
            if k in ("plan", "decision", "quality", "artifacts"):
                k = {"plan": "plan_json", "decision": "decision_json",
                     "quality": "quality_json", "artifacts": "artifacts_json"}[k]
                v = json.dumps(v, ensure_ascii=False)
            cols.append(f"{k}=?")
            vals.append(v)
        cols.append("updated_at=?")
        vals.append(time.time())
        self._exec(f"UPDATE tasks SET {', '.join(cols)} WHERE id=?", tuple(vals + [task_id]))

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        row = self._q1("SELECT * FROM tasks WHERE id=?", (task_id,))
        return self._hydrate(row) if row else None

    def list_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [self._hydrate(r) for r in
                self._q("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,))]

    @staticmethod
    def _hydrate(row: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(row)
        for src, dst in (("plan_json", "plan"), ("decision_json", "decision"),
                         ("quality_json", "quality"), ("artifacts_json", "artifacts")):
            if src in out:
                try:
                    out[dst] = json.loads(out.pop(src) or "null")
                except json.JSONDecodeError:
                    out[dst] = None
        return out

    # -- deliberation -----------------------------------------------------
    def add_message(self, task_id: str, round_: int, mtype: str, frm: str, to: str,
                    body: str, payload: Optional[Dict[str, Any]] = None) -> int:
        cur = self._exec(
            "INSERT INTO messages(task_id,round,mtype,from_agent,to_agent,body,payload_json,ts)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (task_id, round_, mtype, frm, to, body, json.dumps(payload or {}, ensure_ascii=False), time.time()),
        )
        return cur.lastrowid or 0

    def messages_for(self, task_id: str) -> List[Dict[str, Any]]:
        rows = self._q("SELECT * FROM messages WHERE task_id=? ORDER BY id", (task_id,))
        for r in rows:
            try:
                r["payload"] = json.loads(r.pop("payload_json") or "{}")
            except json.JSONDecodeError:
                r["payload"] = {}
        return rows

    # -- decisions / audit ------------------------------------------------
    def add_decision(self, d: Dict[str, Any]) -> int:
        cur = self._exec(
            "INSERT INTO decisions(task_id,intent,action,confidence,risk,reversibility,"
            "autonomy_level,mode,reasoning,requires_approval,ts) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (d.get("task_id"), d.get("intent"), d.get("action"), d.get("confidence", 0),
             d.get("risk", 0), d.get("reversibility"), d.get("autonomy_level", 1),
             d.get("mode"), d.get("reasoning"), 1 if d.get("requires_approval") else 0, time.time()),
        )
        return cur.lastrowid or 0

    def audit(self, actor: str, action: str, ref: str = "", detail: Optional[Dict[str, Any]] = None) -> None:
        self._exec("INSERT INTO audit_log(actor,action,ref,detail_json,ts) VALUES(?,?,?,?,?)",
                   (actor, action, ref, json.dumps(detail or {}, ensure_ascii=False), time.time()))

    def audit_tail(self, limit: int = 120) -> List[Dict[str, Any]]:
        rows = self._q("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))
        for r in rows:
            try:
                r["detail"] = json.loads(r.pop("detail_json") or "{}")
            except json.JSONDecodeError:
                r["detail"] = {}
        return rows

    def decisions_for(self, task_id: str) -> List[Dict[str, Any]]:
        return self._q("SELECT * FROM decisions WHERE task_id=? ORDER BY id", (task_id,))

    # -- artifacts --------------------------------------------------------
    def add_artifact(self, a: Dict[str, Any]) -> None:
        self._exec(
            "INSERT INTO artifacts(task_id,name,kind,path,status,sha,bytes,ts) VALUES(?,?,?,?,?,?,?,?)",
            (a.get("task_id"), a.get("name"), a.get("kind"), a.get("path"), a.get("status"),
             a.get("sha", ""), a.get("bytes", 0), time.time()))

    # -- memory -----------------------------------------------------------
    def add_memory(self, layer: str, key: str, content: str, confidence: float = 0.5,
                   source: str = "system", status: str = "active") -> int:
        cur = self._exec(
            "INSERT INTO memories(layer,key,content,confidence,source,status,hits,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?,0,?,?)",
            (layer, key, content, confidence, source, status, time.time(), time.time()))
        return cur.lastrowid or 0

    def update_memory(self, mid: int, **fields: Any) -> None:
        cols, vals = [], []
        for k, v in fields.items():
            cols.append(f"{k}=?")
            vals.append(v)
        cols.append("updated_at=?")
        vals.append(time.time())
        self._exec(f"UPDATE memories SET {', '.join(cols)} WHERE id=?", tuple(vals + [mid]))

    def memories(self, layer: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        if layer:
            return self._q("SELECT * FROM memories WHERE layer=? ORDER BY updated_at DESC LIMIT ?",
                           (layer, limit))
        return self._q("SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?", (limit,))

    def bump_memory_hits(self, mid: int) -> None:
        self._exec("UPDATE memories SET hits=hits+1 WHERE id=?", (mid,))

    def find_memories(self, needle: str) -> List[Dict[str, Any]]:
        return self._q("SELECT * FROM memories WHERE content LIKE ? AND status='active' "
                       "ORDER BY confidence DESC LIMIT 10", (f"%{needle}%",))

    # -- knowledge graph ----------------------------------------------------
    def add_node(self, nid: str, ntype: str, label: str, props: Optional[Dict[str, Any]] = None) -> None:
        self._exec("INSERT OR REPLACE INTO kg_nodes(id,ntype,label,props_json,created_at) VALUES(?,?,?,?,?)",
                   (nid, ntype, label, json.dumps(props or {}, ensure_ascii=False), time.time()))

    def add_edge(self, src: str, dst: str, etype: str, props: Optional[Dict[str, Any]] = None) -> None:
        self._exec("INSERT OR REPLACE INTO kg_edges(src,dst,etype,props_json) VALUES(?,?,?,?)",
                   (src, dst, etype, json.dumps(props or {}, ensure_ascii=False)))

    def graph(self) -> Dict[str, List[Dict[str, Any]]]:
        nodes = self._q("SELECT * FROM kg_nodes")
        edges = self._q("SELECT * FROM kg_edges")
        for n in nodes:
            try:
                n["props"] = json.loads(n.pop("props_json") or "{}")
            except json.JSONDecodeError:
                n["props"] = {}
        for e in edges:
            try:
                e["props"] = json.loads(e.pop("props_json") or "{}")
            except json.JSONDecodeError:
                e["props"] = {}
        return {"nodes": nodes, "edges": edges}

    def neighbors(self, nid: str, etype: Optional[str] = None) -> List[Dict[str, Any]]:
        if etype:
            return self._q("SELECT * FROM kg_edges WHERE src=? AND etype=?", (nid, etype))
        return self._q("SELECT * FROM kg_edges WHERE src=? OR dst=?", (nid, nid))

    def find_nodes(self, ntype: Optional[str] = None, like: str = "") -> List[Dict[str, Any]]:
        sql, args = "SELECT * FROM kg_nodes WHERE 1=1", []
        if ntype:
            sql += " AND ntype=?"
            args.append(ntype)
        if like:
            sql += " AND (id LIKE ? OR label LIKE ?)"
            args.extend([f"%{like}%", f"%{like}%"])
        rows = self._q(sql, tuple(args))
        for n in rows:
            try:
                n["props"] = json.loads(n.pop("props_json") or "{}")
            except json.JSONDecodeError:
                n["props"] = {}
        return rows

    # -- skills -------------------------------------------------------------
    def upsert_skill(self, s: Dict[str, Any]) -> None:
        now = time.time()
        self._exec(
            "INSERT INTO skills(id,name,category,version,triggers_json,input_schema_json,"
            "output_schema_json,validators_json,autonomy,risk,status,runs,successes,last_score,"
            "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, category=excluded.category, "
            "triggers_json=excluded.triggers_json, input_schema_json=excluded.input_schema_json, "
            "output_schema_json=excluded.output_schema_json, validators_json=excluded.validators_json, "
            "autonomy=excluded.autonomy, risk=excluded.risk, updated_at=excluded.updated_at",
            (s["id"], s["name"], s["category"], s.get("version", "1.0.0"),
             json.dumps(s.get("triggers", []), ensure_ascii=False),
             json.dumps(s.get("input_schema", {}), ensure_ascii=False),
             json.dumps(s.get("output_schema", {}), ensure_ascii=False),
             json.dumps(s.get("validators", []), ensure_ascii=False),
             s.get("autonomy", 2), s.get("risk", 0.1), s.get("status", "active"),
             s.get("runs", 0), s.get("successes", 0), s.get("last_score"),
             now, now))

    def skills(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = self._q("SELECT * FROM skills ORDER BY category, name") if not status else \
            self._q("SELECT * FROM skills WHERE status=? ORDER BY category, name", (status,))
        for s in rows:
            for k in ("triggers", "input_schema", "output_schema", "validators"):
                try:
                    s[k] = json.loads(s.pop(f"{k}_json") or "[]")
                except json.JSONDecodeError:
                    s[k] = []
        return rows

    def record_skill_run(self, skill_id: str, ok: bool, score: float) -> None:
        self._exec(
            "UPDATE skills SET runs=runs+1, successes=successes+CASE WHEN ? THEN 1 ELSE 0 END, "
            "last_score=?, updated_at=? WHERE id=?",
            (1 if ok else 0, score, time.time(), skill_id))

    # -- RSI -----------------------------------------------------------------
    def add_rsi(self, p: Dict[str, Any]) -> int:
        cur = self._exec(
            "INSERT INTO rsi_proposals(kind,title,hypothesis,evidence_json,status,baseline_score,"
            "candidate_score,regression_cost,anti_habit_check,version_before,version_after,ts)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (p.get("kind"), p.get("title"), p.get("hypothesis"),
             json.dumps(p.get("evidence", []), ensure_ascii=False), p.get("status", "candidate"),
             p.get("baseline_score"), p.get("candidate_score"), p.get("regression_cost"),
             p.get("anti_habit_check"), p.get("version_before"), p.get("version_after"), time.time()))
        return cur.lastrowid or 0

    def update_rsi(self, pid: int, **fields: Any) -> None:
        cols, vals = [], []
        for k, v in fields.items():
            cols.append(f"{k}=?")
            vals.append(v)
        self._exec(f"UPDATE rsi_proposals SET {', '.join(cols)} WHERE id=?", tuple(vals + [pid]))

    def rsi_list(self, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self._q("SELECT * FROM rsi_proposals ORDER BY id DESC LIMIT ?", (limit,))
        for r in rows:
            try:
                r["evidence"] = json.loads(r.pop("evidence_json") or "[]")
            except json.JSONDecodeError:
                r["evidence"] = []
        return rows

    def add_golden(self, proposal_id: int, test_name: str, passed: bool, detail: str) -> None:
        self._exec("INSERT INTO golden_results(proposal_id,test_name,passed,detail,ts) VALUES(?,?,?,?,?)",
                   (proposal_id, test_name, 1 if passed else 0, detail, time.time()))

    def golden_for(self, proposal_id: int) -> List[Dict[str, Any]]:
        return self._q("SELECT * FROM golden_results WHERE proposal_id=? ORDER BY id", (proposal_id,))

    # -- approvals -----------------------------------------------------------
    def add_approval(self, a: Dict[str, Any]) -> None:
        self._exec("INSERT INTO approvals(id,task_id,action,reason,risk,preview,status,created_at)"
                   " VALUES(?,?,?,?,?,?,?,?)",
                   (a["id"], a["task_id"], a["action"], a["reason"], a.get("risk", 0.5),
                    a.get("preview", ""), "pending", time.time()))

    def approvals(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        if status:
            return self._q("SELECT * FROM approvals WHERE status=? ORDER BY created_at DESC", (status,))
        return self._q("SELECT * FROM approvals ORDER BY created_at DESC")

    def resolve_approval(self, aid: str, status: str,
                         feedback: Optional[str] = None) -> Optional[Dict[str, Any]]:
        row = self._q1("SELECT * FROM approvals WHERE id=?", (aid,))
        if row and row["status"] == "pending":
            self._exec("UPDATE approvals SET status=?, feedback=?, resolved_at=? WHERE id=?",
                       (status, (feedback or "").strip() or None, time.time(), aid))
        return self._q1("SELECT * FROM approvals WHERE id=?", (aid,))

    # -- settings --------------------------------------------------------------
    def get_setting(self, k: str, default: Any = None) -> Any:
        row = self._q1("SELECT v FROM settings WHERE k=?", (k,))
        if not row:
            return default
        try:
            return json.loads(row["v"])
        except json.JSONDecodeError:
            return default

    def set_setting(self, k: str, v: Any) -> None:
        self._exec("INSERT OR REPLACE INTO settings(k,v) VALUES(?,?)",
                   (k, json.dumps(v, ensure_ascii=False)))


DBI = DB()
