"""
Static HTML snapshot generator (visualization layer).

Renders the three-layer memory into a single self-contained HTML page that
opens in any browser — no JS, no external assets, inline CSS. This is the
"用户可读文档（可视化）" need: humans read it in a browser, agents can also
parse it (it's Markdown-rendered HTML).

Not a web app. Not a service. Zero runtime — generate once, open anywhere.
"""
from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

from .core import Memory, detect_locale


_CSS = """
body { font: 15px/1.6 -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
       max-width: 880px; margin: 2rem auto; padding: 0 1.2rem; color: #1a1a1a; background: #fafaf7; }
h1 { font-size: 1.55rem; border-bottom: 2px solid #8FC8F0; padding-bottom: .4rem; margin-top: 2rem; }
h2 { font-size: 1.2rem; margin-top: 1.8rem; color: #2a6496; }
h3 { font-size: 1rem; margin-top: 1.2rem; }
.meta { color: #777; font-size: .82rem; margin-bottom: 1.5rem; }
section { background: #fff; border: 1px solid #e5e5e5; border-radius: 8px;
          padding: .9rem 1.1rem; margin: .9rem 0; }
section > h2 { margin-top: 0; }
pre { white-space: pre-wrap; word-wrap: break-word; font-family: inherit; margin: 0; }
.tagline { font-size: .85rem; color: #888; margin-top: 2rem; padding-top: .8rem;
           border-top: 1px solid #eee; }
ul.timeline { list-style: none; padding-left: 0; }
ul.timeline li { padding: .3rem 0; border-bottom: 1px dashed #eee; }
ul.timeline li:last-child { border-bottom: none; }
.warn { color: #c0392b; }
.ok { color: #27ae60; }
"""


def _esc(s: str) -> str:
    return html.escape(s or "")


def _section(title: str, body: str, cls: str = "") -> str:
    if not body:
        return ""
    body_html = _esc(body)
    # light markdown: turn lines starting with "- " into list items, "## "/"### " into h3
    lines = body_html.split("\n")
    out = []
    in_list = False
    for ln in lines:
        stripped = ln.strip()
        if stripped.startswith("### "):
            if in_list:
                out.append("</ul>"); in_list = False
            out.append(f"<h3>{stripped[4:]}</h3>")
        elif stripped.startswith("## "):
            if in_list:
                out.append("</ul>"); in_list = False
            out.append(f"<h3>{stripped[3:]}</h3>")
        elif stripped.startswith("- "):
            if not in_list:
                out.append("<ul class='timeline'>"); in_list = True
            out.append(f"<li>{stripped[2:]}</li>")
        elif stripped.startswith("| "):
            # table row — render as monospace line (good enough for INDEX/todos)
            if in_list:
                out.append("</ul>"); in_list = False
            out.append(f"<pre>{stripped}</pre>")
        else:
            if in_list:
                out.append("</ul>"); in_list = False
            if stripped:
                out.append(f"<p>{stripped}</p>")
    if in_list:
        out.append("</ul>")
    body_rendered = "\n".join(out)
    return f"<section class='{cls}'><h2>{_esc(title)}</h2>\n{body_rendered}</section>\n"


def render_snapshot_html(m: Memory) -> str:
    """Build the full HTML document string for the snapshot."""
    r = m.recall(budget=6000, recent_n=5)
    loc_label = "EN" if m.is_en else "中文"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    project_name = m.root.name

    # three-questions framing (mapped from recall fields)
    what = r.overview  # 总览 含宗旨/定位/内容摘要 → 这是什么
    where_parts = []
    # extract the 内容摘要 section from overview if present; else use overview head
    where_parts.append(r.overview)
    if r.recent_middle:
        where_parts.append("\n".join(f"- {item.get('date','?')} {item.get('summary','')}"
                                       for item in r.recent_middle))
    where = "\n".join(where_parts)

    next_parts = []
    if r.todo:
        next_parts.append(r.todo)
    if r.last_deep:
        next_parts.append("— 深层末节 —\n" + r.last_deep)
    nxt = "\n\n".join(next_parts)

    parts = [
        f"<!DOCTYPE html><html lang='{'en' if m.is_en else 'zh'}'><head>",
        f"<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>{_esc(project_name)} · 项目快照</title>",
        f"<style>{_CSS}</style></head><body>",
        f"<h1>{_esc(project_name)} · 项目快照</h1>",
        f"<div class='meta'>生成于 {now} · {loc_label} 库 · token 估算 {r.token_estimate}</div>",
    ]

    # three questions
    if m.is_en:
        parts.append(_section("What is this project", what))
        parts.append(_section("Where are we", where))
        parts.append(_section("What's next", nxt))
    else:
        parts.append(_section("📌 这是什么", what))
        parts.append(_section("📍 走到哪了", where))
        parts.append(_section("➡️ 下一步", nxt))

    # unknowns (if configured)
    if r.unknowns and r.unknowns != "(not configured)":
        title = "Unknowns & open questions" if m.is_en else "❓ 未知与开放问题"
        parts.append(_section(title, r.unknowns))

    # global deep (if configured)
    if r.global_deep:
        title = "Global deep (cross-project)" if m.is_en else "🌐 全局深层（跨项目）"
        parts.append(_section(title, r.global_deep))

    parts.append(
        f"<div class='tagline'>由 three-layer-agent-memory 生成 · "
        f"纯 Markdown · 零运行时 · "
        f"<a href='https://github.com/cultwlpbmx/three-layer-agent-memory'>范式仓库</a></div>"
    )
    parts.append("</body></html>")
    return "\n".join(parts)


def snapshot(project_dir: str | Path, output_path: str | Path,
             *, format: str = "html") -> Path:
    """Generate a single-page snapshot of the project memory.

    `format`: "html" (default, styled, browser-openable) or "md" (plain
    Markdown, agent-readable).

    Returns the written snapshot path.
    """
    m = Memory(project_dir)
    out = Path(output_path)

    if format == "md":
        r = m.recall(budget=6000, recent_n=5)
        title = f"# {m.root.name} · 项目快照\n\n"
        meta = f"> 生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')} · "
        meta += "EN" if m.is_en else "中文"
        meta += f" 库 · token 估算 {r.token_estimate}\n\n---\n\n"
        sections = []
        if m.is_en:
            sections.append("## What is this project\n\n" + r.overview)
            sections.append("## Where are we\n\n" + r.overview)
            sections.append("## What's next\n\n" + (r.todo or "") + ("\n\n— deep —\n" + r.last_deep if r.last_deep else ""))
            if r.unknowns != "(not configured)":
                sections.append("## Unknowns & open questions\n\n" + r.unknowns)
        else:
            sections.append("## 📌 这是什么\n\n" + r.overview)
            sections.append("## 📍 走到哪了\n\n" + r.overview)
            nxt = (r.todo or "") + ("\n\n— 深层末节 —\n" + r.last_deep if r.last_deep else "")
            sections.append("## ➡️ 下一步\n\n" + nxt)
            if r.unknowns != "(not configured)":
                sections.append("## ❓ 未知与开放问题\n\n" + r.unknowns)
        content = title + meta + "\n\n".join(sections) + "\n"
        out.write_text(content, encoding="utf-8")
        return out

    # default: html
    html_doc = render_snapshot_html(m)
    out.write_text(html_doc, encoding="utf-8")
    return out