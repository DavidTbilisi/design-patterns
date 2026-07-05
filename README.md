# GoF Pattern Playground

Interactive learning lab for the 23 GoF design patterns. Core idea: **a pattern
IS its typed edge set** — participants are nodes, relationships are 14 typed
verbs, and checking a design means diffing edge sets (missing / extra /
wrong-verb / reversed).

Grown out of the Neural-OS-Research wiki (see its `wiki/career-mission/gof-design-patterns.md`
for the ingested source material); moved here 2026-07-05 as a standalone project.

## Pieces

- **`pattern-playground.html`** — self-contained, zero-dependency node editor
  (ComfyUI-style). Four modes: free playground, build-from-zero tasks, fix-the-
  sabotage tasks, scenario drill. UML member compartments per participant,
  vertical inheritance routing, per-pattern GoF sequence diagrams in the bottom
  drawer, live TypeScript skeleton codegen, localStorage progress (52 tasks).
  Serve over localhost (`python3 -m http.server`) — `file://` won't do.
  Playground mode: double-click a node header to rename, double-click its
  member compartment to edit methods.
- **`tools/pattern_mcp_server.py`** — MCP server (stdio) exposing the same data
  and checkers as 8 tools (`list_patterns`, `get_pattern`, `get_sequence`,
  `check_wiring`, `check_members`, `sabotage`, `quiz_scenario`, `list_verbs`)
  so any MCP client can run drills conversationally. Single source of truth:
  it extracts the data blocks from `pattern-playground.html` at startup via
  node — server and UI cannot drift. Registered project-scope in `.mcp.json`.
- **`tests/pattern-playground.e2e.html`** — zero-dependency e2e suite (16
  tests) driving the real page in an iframe with real PointerEvents.
- **`tools/run_playground_e2e.py`** — headless runner on Playwright
  chromium-headless-shell. `python3 tools/run_playground_e2e.py`, exit 0 = green.

## Setup

```bash
pip install --user mcp playwright
python3 -m playwright install chromium-headless-shell
# node must be on PATH (data extraction)
```

## Content grounding

Intents from the GoF book (GOF-articulo.pdf via the wiki ingest), "lets you
vary" from GoF Table 1.2, recognition triggers from the exam-compression
problem-shape table, confusable-neighbor contrasts from the drill ladder
(State↔Strategy, Adapter↔Decorator/Facade, Factory Method↔Abstract Factory,
Mediator↔Observer).
