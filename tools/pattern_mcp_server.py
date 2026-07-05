#!/usr/bin/env python3
"""MCP server for the GoF Pattern Playground.

Exposes the playground's pattern knowledge and checker as MCP tools so any
MCP client (Claude Code, claude.ai) can run wiring drills, scenario quizzes,
and sabotage-repair exercises in conversation — same data, same checker
semantics as the browser UI.

Single source of truth: pattern-playground.html. The data blocks (VERBS,
PATTERNS incl. real-uses/scenarios, MEMBERS, FIXTASKS, SEQ) are extracted
from the page at startup by evaluating just its data sections in node, so
server and UI cannot drift.

Setup:    pip install --user mcp        (node must be on PATH)
Register: repo .mcp.json (project scope) — {"command": "python3", "args": ["tools/pattern_mcp_server.py"]}
Run:      python3 tools/pattern_mcp_server.py   (stdio transport)
"""
import json
import random
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

HTML = Path(__file__).resolve().parent.parent / "pattern-playground.html"

_NODE_EXTRACT = r"""
const fs=require('fs');
const src=fs.readFileSync(process.argv[1],'utf8');
function cut(startRe,endRe){
  const s=src.search(startRe); if(s<0) throw new Error('start marker missing: '+startRe);
  const e=src.slice(s).search(endRe); if(e<0) throw new Error('end marker missing: '+endRe);
  return src.slice(s,s+e);
}
const data=cut(/const VERBS = \[/, /\/\* =+\s*\n\s*STATE/);
const seq =cut(/const SEQ=\{/, /\nfunction seqSVG/);
console.log(eval(data+'\n'+seq+
  ';JSON.stringify({VERBS,KINDS,PATTERNS,MEMBERS,KIND_DEFAULT_MEMBERS,FIXTASKS,SEQ})'));
"""


def load_data():
    out = subprocess.run(["node", "-e", _NODE_EXTRACT, str(HTML)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


D = load_data()
PAT = {p["id"]: p for p in D["PATTERNS"]}
VERB_IDS = {v["id"] for v in D["VERBS"]}
VERB_ALIAS = {v["label"]: v["id"] for v in D["VERBS"]} | {v["id"]: v["id"] for v in D["VERBS"]}
CATEGORY = {"C": "Creational", "S": "Structural", "B": "Behavioral"}
SEQ_KIND = {"c": "call", "n": "create (new)", "r": "return"}

mcp = FastMCP("gof-pattern-playground")


def _norm_edge(e):
    if not (isinstance(e, (list, tuple)) and len(e) == 3):
        raise ValueError(f"edge must be [source, verb, target], got {e!r}")
    src, verb, dst = (str(x).strip() for x in e)
    if verb not in VERB_ALIAS:
        raise ValueError(f"unknown verb {verb!r} — see list_verbs()")
    return [src, VERB_ALIAS[verb], dst]


def _members(role, pattern):
    """MEMBERS is nested per pattern: {pattern_id: {role: [lines]}}; fall back to
    any other pattern defining the role, then to the kind defaults (same order
    the UI's roleMembers() resolves)."""
    hit = D["MEMBERS"].get(pattern["id"], {}).get(role)
    if hit:
        return hit
    for table in D["MEMBERS"].values():
        if role in table:
            return table[role]
    kind = dict(pattern["roles"]).get(role)
    return D["KIND_DEFAULT_MEMBERS"].get(kind)


@mcp.tool()
def list_patterns() -> list[dict]:
    """All 23 GoF patterns: id, name, category, intent, recognition trigger."""
    return [{"id": p["id"], "name": p["name"], "category": CATEGORY[p["cat"]],
             "intent": p["intent"], "trigger": p["trigger"]} for p in D["PATTERNS"]]


@mcp.tool()
def list_verbs() -> list[dict]:
    """The 14 relationship verbs edges are typed with (a pattern IS its typed edge set)."""
    return [{"id": v["id"], "label": v["label"], "group": v["grp"]} for v in D["VERBS"]]


@mcp.tool()
def get_pattern(pattern_id: str) -> dict:
    """Full canonical spec for one pattern: participants (with kind + UML members),
    the canonical typed edge set, intent, what it lets vary, trigger, real-world
    uses, and the confusable-neighbor contrast."""
    p = PAT.get(pattern_id)
    if not p:
        raise ValueError(f"unknown pattern {pattern_id!r} — see list_patterns()")
    return {
        "id": p["id"], "name": p["name"], "category": CATEGORY[p["cat"]],
        "intent": p["intent"], "lets_you_vary": p["varies"], "trigger": p["trigger"],
        "vs_neighbor": p["neighbor"], "real_uses": p.get("ex", []),
        "roles": [{"name": r, "kind": k, "members": _members(r, p)} for r, k in p["roles"]],
        "decoy_roles": [{"name": r, "kind": k} for r, k in p.get("decoys", [])],
        "edges": p["edges"],
    }


@mcp.tool()
def get_sequence(pattern_id: str) -> dict:
    """The pattern's runtime story (GoF interaction diagram as data): lifelines
    left-to-right and the ordered message list (call / create / return, self-calls)."""
    s = D["SEQ"].get(pattern_id)
    if not s:
        raise ValueError(f"unknown pattern {pattern_id!r} — see list_patterns()")
    parts = s["parts"]
    msgs = [{"from": parts[f], "to": parts[t], "message": lbl,
             "kind": "self-call" if f == t else SEQ_KIND[k]}
            for f, t, lbl, k in s["msgs"]]
    return {"pattern": PAT[pattern_id]["name"], "lifelines": parts,
            "messages": msgs, "note": s.get("note")}


@mcp.tool()
def check_wiring(pattern_id: str, edges: list[list[str]]) -> dict:
    """Check a proposed wiring against the canonical pattern. Each edge is
    [source_role, verb, target_role] (verb id or label). Returns the same
    finding categories as the playground UI: missing / extra / wrong_verb /
    reversed. correct=true means the edge set IS the pattern."""
    p = PAT.get(pattern_id)
    if not p:
        raise ValueError(f"unknown pattern {pattern_id!r} — see list_patterns()")
    user = [_norm_edge(e) for e in edges]
    spec = [list(e) for e in p["edges"]]
    claimed_u, claimed_s, findings = set(), set(), []

    for i, u in enumerate(user):          # exact matches
        for j, s in enumerate(spec):
            if j not in claimed_s and u == s:
                claimed_u.add(i); claimed_s.add(j); break
    for i, u in enumerate(user):          # same endpoints, wrong verb
        if i in claimed_u: continue
        for j, s in enumerate(spec):
            if j in claimed_s: continue
            if u[0] == s[0] and u[2] == s[2]:
                claimed_u.add(i); claimed_s.add(j)
                findings.append({"type": "wrong_verb", "edge": u,
                                 "hint": f"{u[0]} → {u[2]} exists in {p['name']}, but the verb should be '{s[1]}', not '{u[1]}'."})
                break
    for i, u in enumerate(user):          # reversed direction
        if i in claimed_u: continue
        for j, s in enumerate(spec):
            if j in claimed_s: continue
            if u[0] == s[2] and u[2] == s[0] and u[1] == s[1]:
                claimed_u.add(i); claimed_s.add(j)
                findings.append({"type": "reversed", "edge": u,
                                 "hint": f"'{u[1]}' points the wrong way: it should run {s[0]} → {s[2]}."})
                break
    for j, s in enumerate(spec):
        if j not in claimed_s:
            findings.append({"type": "missing", "edge": s,
                             "hint": f"Missing: {s[0]} —{s[1]}→ {s[2]}."})
    for i, u in enumerate(user):
        if i not in claimed_u:
            findings.append({"type": "extra", "edge": u,
                             "hint": f"Extra: {u[0]} —{u[1]}→ {u[2]} is not part of {p['name']}."})

    return {"pattern": p["name"], "correct": not findings, "findings": findings,
            "summary": f"✓ {p['name']} correctly wired — {p['intent']}" if not findings
                       else f"{len(findings)} issue(s) — the edge set is the pattern."}


_ID_NOISE = {"static", "private", "abstract", "the", "uses", "new"}


def _line_ids(line: str) -> list[str]:
    import re
    ids = [w.lower() for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", line.split("//")[0])]
    return [w for w in ids if w not in _ID_NOISE] or ids


@mcp.tool()
def check_members(pattern_id: str, members: dict[str, list[str]]) -> dict:
    """Check method/field placement for a pattern: members maps role name →
    list of member lines the student put on it (free-form, e.g. '+ getInstance()').
    Matching is lenient — a canonical member counts as present if one of its
    identifiers appears somewhere in the student's lines for that role. Reports
    canonical members that are missing, and roles the student forgot entirely.
    Extra members are allowed (noted, never an error)."""
    p = PAT.get(pattern_id)
    if not p:
        raise ValueError(f"unknown pattern {pattern_id!r} — see list_patterns()")
    canon = D["MEMBERS"].get(pattern_id, {})
    role_names = {r for r, _ in p["roles"]}
    findings = []
    for role in members:
        if role not in role_names:
            findings.append({"type": "unknown_role", "role": role,
                             "hint": f"{p['name']} has no participant named {role!r}."})
    for role, lines in canon.items():
        if role not in role_names:
            continue
        student = " ".join(members.get(role, [])).lower()
        if not student:
            findings.append({"type": "missing_role_members", "role": role,
                             "hint": f"{role} has no members — it needs: {' · '.join(lines)}"})
            continue
        for line in lines:
            if not any(i in student for i in _line_ids(line)):
                findings.append({"type": "missing_member", "role": role, "member": line,
                                 "hint": f"{role} is missing its load-bearing member: {line}"})
    return {"pattern": p["name"], "correct": not findings, "findings": findings,
            "summary": f"✓ every participant of {p['name']} carries its load-bearing members"
                       if not findings else f"{len(findings)} member issue(s)."}


@mcp.tool()
def sabotage(pattern_id: str = "") -> dict:
    """Produce a sabotaged wiring for a repair drill (1–3 mutations: wrong verb,
    reversed edge, or removed edge). Empty pattern_id = random pattern. Have the
    student repair it, then verify with check_wiring. Don't reveal mutation details."""
    p = PAT.get(pattern_id) if pattern_id else random.choice(D["PATTERNS"])
    if not p:
        raise ValueError(f"unknown pattern {pattern_id!r} — see list_patterns()")
    es = [list(e) for e in p["edges"]]
    muts = random.randint(1, min(3, len(es)))
    for _ in range(muts):
        j = random.randrange(len(es))
        kind = random.randrange(3)
        if kind == 0:
            es[j][1] = random.choice([v["id"] for v in D["VERBS"] if v["id"] != es[j][1]])
        elif kind == 1:
            es[j] = [es[j][2], es[j][1], es[j][0]]
        elif len(es) > 1:
            es.pop(j)
    return {"pattern_id": p["id"], "pattern": p["name"],
            "roles": [{"name": r, "kind": k} for r, k in p["roles"]],
            "sabotaged_edges": es, "mutation_count": muts,
            "instructions": "Diagnose and repair this wiring, then check with check_wiring."}


@mcp.tool()
def quiz_scenario() -> dict:
    """A scenario-recognition drill: a real-world problem shape plus four candidate
    patterns (the confusable neighbor is always among them). The answer field is for
    the quizmaster only — do not reveal it until the student commits."""
    p = random.choice([p for p in D["PATTERNS"] if p.get("sc")])
    ids = {p["id"]}
    if p.get("nb"):
        ids.add(p["nb"])
    while len(ids) < 4:
        ids.add(random.choice(D["PATTERNS"])["id"])
    choices = random.sample(sorted(ids), k=len(ids))
    return {"scenario": p["sc"],
            "choices": [{"id": i, "name": PAT[i]["name"]} for i in choices],
            "answer": p["id"], "why": p["trigger"], "vs_neighbor": p["neighbor"]}


if __name__ == "__main__":
    if not HTML.exists():
        sys.exit(f"pattern-playground.html not found at {HTML}")
    mcp.run()
