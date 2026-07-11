# examples/ — reference adapters

Minimal, **runnable** implementations of the protocol checkpoints and cross-project
aggregation, so "adopting the paradigm" goes from *read the spec and implement it
yourself* to *install a script*. Pure Python stdlib, zero dependencies.

## Files

- `memory_adapter.py` — CLI implementing `recall` / `log` / `consolidate`,
  mapped to `on_session_start` / `on_milestone` / `on_day_end`. Supports `--tag`
  for tag-based associative recall.
- `aggregate.py` — cross-project deep-layer aggregation. Reads deep reflections
  from multiple project libraries, produces a read-only Markdown report with
  timeline, risk clusters, and cross-project recurring theme detection.

## Quick test

```bash
# make a throwaway memory dir from the template
cp -r ../_template /tmp/demo-memory
python memory_adapter.py recall /tmp/demo-memory
python memory_adapter.py log /tmp/demo-memory --version V0.1 --summary "first task" --entry "kickoff"
python memory_adapter.py consolidate /tmp/demo-memory \
    --topic "kickoff" \
    --review "project just started" \
    --plan "ship the smallest useful slice first" \
    --risk "scope creep before first validation" \
    --forecast "first slice reveals real constraints within a week"

# tag-based associative recall (after adding tags to task records)
python memory_adapter.py recall /tmp/demo-memory --tag 鉴权

# cross-project aggregation
python aggregate.py /tmp/demo-memory --output report.md
cat report.md
```

## Wiring into an agent framework

Treat the subcommands as the hook contract from `../INTEGRATION.md`:

| Hook | When | Call |
|---|---|---|
| `on_session_start` | session begins / task accepted | `recall <dir>` → inject stdout into the model context |
| `on_milestone` | one independently-verifiable output done | `log <dir> --version … --summary … --tags "#auth #deploy"` |
| `on_day_end` | end of day / major node | `consolidate <dir> --topic … --review … --plan … --risk … --forecast …` |
| (ad-hoc) | need cross-project overview | `aggregate <dir1> <dir2> …` → read-only report |

`recall` prints a structured summary to stdout — capture it and feed it to your
model as the first message. `log` / `consolidate` write files to disk and print
confirmation + a stderr reminder of the remaining discipline. `aggregate`
produces a read-only report and never modifies any project library.

## Locale

Auto-detects Chinese layer dirs (`表层/中层/深层`) or English (`Surface/Middle/Deep`).
See `../SCHEMA.md` → "Localization". Copy `../_template-en/` for the English layout.

## Why scripts and not a library

The paradigm's value is the **discipline** (when to read/write which layer), not
code. Small files you can read in five minutes keep that property. If you need
a library, these files are small enough to vendor and extend.

## Boundary

These adapters enforce the *mechanics* (which file to read/write, which template
to fill). They cannot enforce the *quality* of the deep reflection — that depends
on the model. Weaker models produce shallower reflections → slower evolution.
See `../README.md` → "适用边界 / Boundaries".