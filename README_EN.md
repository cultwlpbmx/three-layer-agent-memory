# Three-Layer Agent Memory

> A filesystem-native, version-controllable **long-memory paradigm for AI agents**.
>
> [中文](README.md) | [English](README_EN.md)
> Keeping agents on long horizons **lossless in tenets, undiluted in memory, capable of self-evolution**.

**Abstract:** A minimal, framework-agnostic memory architecture for long-horizon AI agents. Memory is split by *stability* into three layers — **Surface** (stable tenets/philosophy/needs), **Middle** (timestamped task logs), **Deep** (agent metacognition & reflection). A small **recall/writeback protocol** binds when each layer is read and written. The Deep layer plus the rolling index forms a persisted self-improvement loop — the agent reads its own past reflections, mines recurring failure modes, and rewrites its tenets. Storage is plain Markdown on disk: human-readable, git-diffable, zero infrastructure. This repo contains the protocol spec, storage schema, template kit, integration guide, and a sanitized case study.

---

## What Is This

A **universal long-memory paradigm for any AI agent**. It takes "memory" out of the model context window and externalizes it into a three-layer Markdown structure on disk, with a lightweight protocol governing when each layer is read and written.

It is not a database, not RAG, not a vector store. It is the **minimal persistable form of a cognitive architecture**:

| Cognitive Science Concept | Paradigm Equivalent | Physical Form |
|---|---|---|
| Semantic memory (slow-changing facts/beliefs) | Surface | `Surface/00-overview.md` |
| Episodic memory (timestamped events) | Middle | `Middle/YYYY-MM-DD_*.md` (with tags associative index) |
| Metacognition (reflection on self) | Deep | `Deep/AI-deep-reflection.md` |
| Working memory initialization | Mandatory startup protocol | recall 6 steps |
| Memory consolidation (replay/rewrite during sleep) | Log to middle + daily update surface/deep + **extract recurring patterns** | writeback + consolidate |
| Memory compression/archiving (prevent bloat) | Middle archive mechanism | `Middle/archive/` (compress to summary rows when exceeding threshold) |
| Associative memory (scene-triggered recall) | Tag-based associative lookup | `--tag` parameter filters by tag |
| Cross-project memory transfer | Global deep layer | `~/.agent-memory/global-deep/` |
| Metacognitive boundary (knowing what you don't know) | Unknowns & open questions | `Surface/02-unknowns.md` |

## Why It's Needed

Single-session context is limited; long task horizons get compressed and forgotten. AI will **lose project tenets**, drift off course, repeat the same mistakes, and narrate "what was done" eloquently while failing to provide "a structurally better path."

This paradigm counters that with an externalized, stability-layered memory body. The core insight:

> **Memory should be layered by "how stable it is," not by "what category it belongs to."**
> The less likely something is to change, the earlier it should be read. The more volatile, the later it should be written and the more frequently refreshed.

## Three-Layer Structure

```
<project>/
├── Surface/                   # Stable. Read at startup to recover tenets.
│   ├── 00-overview.md         # Name/purpose/tenets/philosophy/needs/preferences/server guide/summary/outline
│   ├── 01-todo.md             # High-frequency updates, separate file
│   └── 02-unknowns.md          # Cognitive gaps + open questions (recommended, optional)
├── Middle/                    # Flow. One task record per milestone, with tags line (associative lookup).
│   ├── INDEX-task-log.md      # Timeline index, new entries prepended
│   ├── YYYY-MM-DD_<version-or-topic>_<short>.md
│   ├── _task-template.md       # Kept for copying
│   └── archive/               # Archive zone (compressed to summary rows when >20 entries)
└── Deep/                      # Reflection. AI examination beyond normal human cognition.
    └── AI-deep-reflection.md   # Appended by date section, no file splitting, no old section deletion

~/.agent-memory/global-deep/   # User-level, cross-project experience laws (not inside any project library)
└── global-reflection.md        # Read first on new project recall, inherits all project experience
```

## Protocol (3 checkpoints the agent must follow)

1. **Startup / task start** → recall: read surface overview → todo → unknowns (if present) → middle recent 1–2 entries → deep tail → global deep tail (if configured).
2. **Milestone complete** → writeback: create a new task record in middle (with **agent signature** + tags line), prepend pointer to INDEX.
3. **Day end / major node** → consolidate: update surface todo and summary, **extract recurring patterns from middle as experience laws**, **append** a reflection to deep (with agent signature + status review / better path / risks / forecast). If laws are cross-project, also write to global deep.

See [`PROTOCOL.md`](PROTOCOL.md).

## Self-Evolution Mechanism

Deep + INDEX form a **persisted self-improvement loop**: each reflection is appended to `AI-deep-reflection.md`, mandatory reading on next startup. During consolidate, the system **extracts cross-task recurring patterns** (N>=2 only) and converts them into experience laws. Repeatedly appearing risks get identified as structural problems, driving updates to surface tenets/rules. Cross-project-universal laws are written to global deep, letting new projects inherit all prior projects' experience. This is the agent's "evolution" — not changing weights, but changing its own **beliefs and behavioral rules**.

See [`EVOLUTION.md`](EVOLUTION.md).

## Repository Contents

| File | Description |
|---|---|
| [`PROTOCOL.md`](PROTOCOL.md) | Protocol spec: recall / writeback / consolidate checkpoints (incl. extraction protocol) |
| [`SCHEMA.md`](SCHEMA.md) | Storage schema: layout / naming / fields / tags / archive / global deep / localization |
| [`PARADIGM.md`](PARADIGM.md) | Paradigm positioning: why this is a program paradigm (9-row cognitive system mapping) |
| [`EVOLUTION.md`](EVOLUTION.md) | Self-evolution mechanism (5-action loop + extraction rules + 4 anti-degradation rules) |
| [`INTEGRATION.md`](INTEGRATION.md) | Integration: hook contract + global deep + aggregate view + auth discovery |
| [`case-study.md`](case-study.md) | Sanitized case study |
| [`adapters/claude-code.md`](adapters/claude-code.md) | Claude Code adapter |
| [`three_layer_memory/`](three_layer_memory/) | **v0.5 Python library**: importable `Memory`/`recall`/`log`/`consolidate`/`init`/`snapshot`/`validate`, zero dependencies, `log`/`consolidate` with `agent` signature param |
| [`examples/mcp_server.py`](examples/mcp_server.py) | **v0.5 MCP server**: 7 tools, any MCP client connects with zero code, cross-agent shared memory, with agent signature |
| [`examples/memory_adapter.py`](examples/memory_adapter.py) | CLI (thin wrapper over library) |
| [`examples/aggregate.py`](examples/aggregate.py) | Cross-project deep-layer aggregation (read-only report) |
| [`scripts/secret-scan.sh`](scripts/secret-scan.sh) | Pre-push secret scan |
| [`.github/workflows/secret-scan.yml`](.github/workflows/secret-scan.yml) | Optional CI |
| [`_template/`](_template/) | Chinese template (canonical) |
| [`_template-en/`](_template-en/) | English template |

## Applicable Boundaries

This paradigm is good at:
- Long-horizon projects (weeks+), multi-session, multi-agent relay workflows
- Projects with clear tenets/philosophy that need anchoring against drift
- Projects that need traceable "why did we make this decision" audit trails

This paradigm is not good at:
- One-shot Q&A, short tasks (overhead exceeds benefit)
- Pure retrieval tasks (vector RAG is more direct)
- Sandboxed agents with no filesystem access (need adapter for remote storage)

**Honest boundary**: This paradigm only enforces *mechanics* (which file to read/write, which template to use), **not reflection quality**. How deep the deep-layer four sections go depends on the model's reflection ability — **the weaker the model, the slower the evolution**. Weak models will write the deep layer as diary entries, degrading the evolution loop into "journaling." The extraction protocol (N>=2 only, evidence chain enforced) is a countermeasure but not a cure — it prevents "arbitrary extraction," not "inability to extract." It does not conflict with RAG/vector retrieval — the latter solves "find relevant knowledge," this paradigm solves "maintain direction and self," and they can be stacked. Global deep, tags, archive, unknowns are all **optional enhancements**; the four core invariants remain unchanged.

## Quick Start

### Option A: Python library (one-line integration for any Python agent)

```bash
git clone https://github.com/cultwlpbmx/three-layer-agent-memory.git
cd three-layer-agent-memory
pip install -e .            # zero runtime dependencies
```

```python
from three_layer_memory import Memory, init, snapshot

# One-shot library creation (scaffold from template)
init("/path/to/my-project-memory", locale="en")

# Agent gets three-question answers + full context in one line
m = Memory("/path/to/my-project-memory")
r = m.recall()                      # on_session_start → {overview, todo, unknowns, recent_middle, last_deep, ...}
print(r.as_prompt_block())           # inject into model context

# Log milestone to middle (unique filename, zero collision for concurrent agents)
m.log(version="V0.1", summary="first task", tags=("#auth", "#deploy"), agent="claude-code")

# Day end: append deep reflection (append-only, atomic append)
m.consolidate(topic="kickoff", review="...", plan="...", risk="...", forecast="...", agent="claude-code")

# Validate + visual snapshot
print(m.validate())                 # schema validation
snapshot("/path/to/...", "out.html")  # single-page HTML, opens in browser
```

The three basic questions (what is this project / where are we / what's next) are already answered by `recall()`'s `overview` + `todo` + `last_deep` — no separate brief needed.

### Option B: MCP server (cross-agent + cross-model shared memory)

```bash
pip install -e ".[mcp]"            # install mcp optional dependency
python examples/mcp_server.py       # stdio MCP server
```

Any MCP client (Claude Desktop / Cursor / Codex / Windsurf / Cline) connects with one line in MCP config:

```json
{
  "mcpServers": {
    "three-layer-agent-memory": {
      "command": "python",
      "args": ["<path-to-repo>/examples/mcp_server.py"]
    }
  }
}
```

7 tools: `three_layer_recall` / `_log` / `_consolidate` / `_snapshot` / `_init` / `_validate` / `_aggregate`.
**Agents and models are transients, memory persists** — switching agents doesn't lose memory, which is structurally impossible for Mem0/Letta (per-agent runtime).

### Option C: CLI (5-minute readable paradigm facade)

```bash
python examples/memory_adapter.py init /path/to/my-project-memory --locale en
python examples/memory_adapter.py recall /path/to/my-project-memory --budget 2000
python examples/memory_adapter.py log /path/to/my-project-memory --version V0.1 --summary "first task" --tags "#auth #deploy" --agent claude-code
python examples/memory_adapter.py consolidate /path/to/my-project-memory --topic "..." --review "..." --plan "..." --risk "..." --forecast "..." --agent claude-code
python examples/memory_adapter.py validate /path/to/my-project-memory
python examples/memory_adapter.py snapshot /path/to/my-project-memory out.html
```

### Concurrent Write Coordination (resolved by structure)

Multiple agents writing to the same memory library don't need locks — resolved by design:
- Middle-layer task records are uniquely named (date+version+summary) → zero collision for concurrent writes
- Deep layer is append-only → atomic append is safe
- Surface todo by design only written by single consolidate writer (agent proposes in middle, consolidate merges)
- recall reads recent INDEX = implicit coordination (agent knows what others just did)

Optional `Memory.claim()` lock is an escape hatch, v0.5 is a stub, real locking deferred to v0.6 when real concurrent conflicts emerge.

### Configure Global Deep (cross-project memory)

```bash
mkdir -p ~/.agent-memory/global-deep
echo "# Global reflection" > ~/.agent-memory/global-deep/global-reflection.md
# recall will auto-read the tail section, consolidate can write cross-project laws
```

### Pre-Push Secret Scan

```bash
./scripts/secret-scan.sh   # confirm no real secrets in the library
```

## Commercial

Cloud services for cross-device and cross-agent memory sharing:

| Feature | Free | Pro ¥9.9/mo (¥99/yr) | Team ¥49/mo (¥499/yr) |
|---|---|---|---|
| Local library + CLI | ✅ | ✅ | ✅ |
| GitHub code repo | ✅ | ✅ | ✅ |
| OSS cloud sync | ❌ | ✅ | ✅ |
| Auto-sync (agent-transparent) | ❌ | ✅ | ✅ |
| Web console | ❌ | ✅ | ✅ |
| MCP server | local | ✅ | ✅ |
| Multi-user collaboration | ❌ | ❌ | ✅ |
| Cross-project transfer | ❌ | ❌ | ✅ |
| Meta-cognition + prediction | ❌ | ❌ | ✅ |
| Projects | 3 | 20 | unlimited |
| Storage | - | 2GB | 10GB |

**Usage:**

```python
from three_layer_memory import Memory
from three_layer_memory.auto_sync import AutoSync

# Free user (local)
m = Memory("/path/to/project-memory")
r = m.recall()

# Pro user (cloud sync)
m = AutoSync(Memory("/path/to/project"),
    api_key="tlam_sk_xxxx",
    device_id="my-laptop")
r = m.recall()    # auto pull
m.log(...)        # auto push
```

**Console**: [wlpworld.com](https://wlpworld.com) (ICP filed, full-site HTTPS)

**Core philosophy**: Memory is cognition, cognition is memory. We sell not storage, but cognitive assets — making cognition persist across devices and agents.

## License

MIT — see [`LICENSE`](LICENSE). If you built your own agent memory library with this, feel free to open an issue and share the link.

## Origin

This paradigm was distilled from a real long-horizon project (family education AI agent, Flutter + FastAPI + MongoDB) — that project ran dozens of versions over months, relying on this structure to maintain direction anchoring without vector databases or additional services. Case study: [`case-study.md`](case-study.md) (sanitized).
