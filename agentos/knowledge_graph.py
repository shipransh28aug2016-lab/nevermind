"""Skill Knowledge Graph — a typed property graph over agents, skills, tools,
validators, domains and knowledge items.

Edges (semantics matter for discovery & routing):
  agent   --EXECUTES-->      skill
  skill   --REQUIRES-->      tool | skill          (dependencies, composition)
  skill   --VALIDATED_BY-->  validator             (quality gates)
  skill   --BELONGS_TO-->    domain
  skill   --IMPROVES-->      skill                 (RSI version lineage)
  skill   --SUPERSEDES-->    skill
  domain  --CONTAINS-->      knowledge
  tool    --HANDLES-->       artifact-kind
  agent   --AUTHORITY_IN-->  domain                (who may decide what)
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Dict, Iterable, List, Optional, Set

VALID_EDGE_TYPES = {
    "EXECUTES", "REQUIRES", "VALIDATED_BY", "BELONGS_TO", "IMPROVES",
    "SUPERSEDES", "AUTHORITY_IN", "CONTAINS", "HANDLES", "COMPOSES",
}


class KnowledgeGraph:
    def __init__(self, db) -> None:
        self.db = db

    # -- construction ------------------------------------------------------
    def upsert_node(self, nid: str, ntype: str, label: str, **props: Any) -> None:
        self.db.add_node(nid, ntype, label, props)

    def add_edge(self, src: str, dst: str, etype: str, **props: Any) -> None:
        assert etype in VALID_EDGE_TYPES, f"unknown edge type {etype}"
        self.db.add_edge(src, dst, etype, props)

    # -- queries -----------------------------------------------------------
    def graph(self) -> Dict[str, Any]:
        return self.db.graph()

    def out(self, nid: str, etype: Optional[str] = None) -> List[Dict[str, Any]]:
        edges = self.db.neighbors(nid, etype)
        return [e for e in edges if e["src"] == nid and (etype is None or e["etype"] == etype)]

    def in_(self, nid: str, etype: Optional[str] = None) -> List[Dict[str, Any]]:
        edges = self.db.neighbors(nid, etype)
        return [e for e in edges if e["dst"] == nid and (etype is None or e["etype"] == etype)]

    def node(self, nid: str) -> Optional[Dict[str, Any]]:
        rows = self.db.find_nodes(like=nid)
        for r in rows:
            if r["id"] == nid:
                return r
        return None

    # -- discovery ---------------------------------------------------------
    def discover_skills(self, query_tokens: Iterable[str], limit: int = 5) -> List[Dict[str, Any]]:
        """Rank skills by trigger/token overlap; fall back to composition paths."""
        tokens = {t.lower() for t in query_tokens if t}
        scored: List[Dict[str, Any]] = []
        for s in self.db.skills(status="active"):
            hay = " ".join(s.get("triggers", []) + [s["name"], s["category"]]).lower()
            hits = sum(1 for t in tokens if t and t in hay)
            score = hits / max(1, len(tokens))
            if s.get("runs", 0) > 0 and s.get("last_score"):
                score += 0.1 * s["last_score"]  # historical success bonus
            if hits:
                scored.append({"skill": s, "score": round(min(1.0, score), 3)})
        scored.sort(key=lambda x: -x["score"])
        return scored[:limit]

    def compose_path(self, start_domain: str, goal_token: str) -> List[str]:
        """BFS over skill REQUIRES edges from any skill in domain matching goal."""
        q: deque = deque()
        seen: Set[str] = set()
        for e in self.in_(start_domain, "BELONGS_TO"):
            sid = e["src"]
            if sid not in seen:
                seen.add(sid)
                q.append((sid, [sid]))
        while q:
            cur, path = q.popleft()
            node = self.node(cur)
            if node and goal_token in (node["label"] + " " + cur).lower():
                return path
            for e in self.out(cur, "REQUIRES"):
                dep = e["dst"]
                if dep not in seen:
                    seen.add(dep)
                    q.append((dep, path + [dep]))
        return []

    def authority_agent(self, domain: str) -> Optional[str]:
        for e in self.in_(domain, "AUTHORITY_IN"):
            return e["src"]
        return None

    def skill_validators(self, skill_id: str) -> List[str]:
        return [e["dst"] for e in self.out(skill_id, "VALIDATED_BY")]

    def skill_tools(self, skill_id: str) -> List[str]:
        return [e["dst"] for e in self.out(skill_id, "REQUIRES")]

    # -- analytics -----------------------------------------------------------
    def degree_report(self) -> Dict[str, Any]:
        g = self.graph()
        deg: Dict[str, int] = defaultdict(int)
        for e in g["edges"]:
            deg[e["src"]] += 1
            deg[e["dst"]] += 1
        by_type: Dict[str, int] = defaultdict(int)
        for n in g["nodes"]:
            by_type[n["ntype"]] += 1
        top = sorted(deg.items(), key=lambda x: -x[1])[:10]
        return {"node_count": len(g["nodes"]), "edge_count": len(g["edges"]),
                "nodes_by_type": dict(by_type), "top_connected": top}
