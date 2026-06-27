# Template kit (English)

Copy this directory, rename it to your project name, and you have a project
library that follows the three-layer memory paradigm. English-named counterpart
of `../_template/` (Chinese). The paradigm is locale-neutral — pick whichever
layout your team prefers (see `../SCHEMA.md` → "Localization").

## After copying you should have

```
<project>/
├── Surface/
│   ├── 00-overview.md
│   └── 01-todo.md
├── Middle/
│   ├── INDEX-task-log.md
│   └── _task-template.md        # keep for copying, don't delete
└── Deep/
    └── AI-deep-reflection.md
```

## Fill order

1. `Surface/00-overview.md` — fill at least through "Core purpose"; verbatim-preserve
   tenets/philosophy if you have them, otherwise leave placeholders.
2. Add a pointer row in your library root `INDEX.md`.
3. `Surface/01-todo.md` — list current todos.
4. Write your first `Middle/` task record (copy `_task-template.md`).
5. `Deep/AI-deep-reflection.md` — a first holistic review of the project is a good opener.

## Protocol

Then have your agent follow the three checkpoints in `../PROTOCOL.md`. No runtime
dependencies. The reference adapter (`../examples/memory_adapter.py`) auto-detects
this English layout.