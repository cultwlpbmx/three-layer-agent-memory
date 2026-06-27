# examples/ — reference adapter

A minimal, **runnable** implementation of the three protocol checkpoints, so
"adopting the paradigm" goes from *read the spec and implement it yourself* to
*install one script*. Pure Python stdlib, zero dependencies.

## Files

- `memory_adapter.py` — CLI implementing `recall` / `log` / `consolidate`,
  mapped to `on_session_start` / `on_milestone` / `on_day_end`.

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
```

Then look at `/tmp/demo-memory/中层/` (new task record) and `深层/AI深度思考.md`
(appended `## <date> kickoff` section).

## Wiring into an agent framework

Treat the three subcommands as the hook contract from `../INTEGRATION.md`:

| Hook | When | Call |
|---|---|---|
| `on_session_start` | session begins / task accepted | `recall <dir>` → inject stdout into the model context |
| `on_milestone` | one independently-verifiable output done | `log <dir> --version … --summary …` |
| `on_day_end` | end of day / major node | `consolidate <dir> --topic … --review … --plan … --risk … --forecast …` |

`recall` prints a structured summary to stdout — capture it and feed it to your
model as the first message. `log` / `consolidate` write files to disk and print
confirmation + a stderr reminder of the remaining discipline.

## Locale

Auto-detects Chinese layer dirs (`表层/中层/深层`) or English (`Surface/Middle/Deep`).
See `../SCHEMA.md` → "Localization". Copy `../_template-en/` for the English layout.

## Why a script and not a library

The paradigm's value is the **discipline** (when to read/write which layer), not
code. A single file you can read in five minutes keeps that property. If you need
a library, this file is small enough to vendor and extend.

## Boundary

This adapter enforces the *mechanics* (which file to read/write, which template
to fill). It cannot enforce the *quality* of the deep reflection — that depends
on the model. Weaker models produce shallower reflections → slower evolution.
See `../README.md` → "适用边界 / Boundaries".