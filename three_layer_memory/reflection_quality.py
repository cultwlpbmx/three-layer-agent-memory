"""
Reflection quality assessment — score deep-layer reflections to detect degradation.

Phase 2-4 of the cognitive upgrade: the system evaluates its own deep-layer
reflections for quality. A reflection that is a "diary entry" (no actionable
insight, no falsifiable prediction, boilerplate "optimization plan") is marked
as degradation. This is the meta-quality gate that prevents the evolution loop
from collapsing into "looks profound but says nothing."

Scoring dimensions (each 0-10, total 0-40):
  1. Completeness — are all four sections present? (现状审视/优化方案/隐患/预期)
  2. Substance — is the "optimization plan" actionable or boilerplate?
  3. Falsifiability — does "预期" contain testable predictions (not vague hopes)?
  4. Depth — does it go beyond "what we did" to "why / structural / second-order"?

Usage:
    from three_layer_memory.reflection_quality import assess_reflections, quality_report

    result = assess_reflections(project_dir)
    print(quality_report(result))
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .core import Memory


# --- boilerplate / vagueness detectors ----------------------------------------

# Phrases that signal boilerplate (套话) in optimization plans
_BOILERPLATE_PHRASES = [
    "继续优化", "进一步完善", "加强", "注意", "关注", "持续改进",
    "需要改进", "有待提高", "继续努力", "保持",
    "continue to", "further improve", "pay attention",
]

# Phrases that signal vague/non-falsifiable predictions
_VAGUE_PREDICTION_PHRASES = [
    "希望", "尽量", "争取", "可能", "或许", "大概",
    "hopefully", "try to", "maybe", "might", "perhaps",
]

# Phrases that signal falsifiable predictions (good)
_FALSIFIABLE_MARKERS = [
    "若", "如果", "如果X", "当...时", "可证伪", "验证条件", "反证条件",
    "if X then", "falsifiable", "verifiable", "observable",
    "预测", "预期", "预测①", "预测②", "观察哨",
]

# Phrases that signal depth (structural/second-order thinking)
_DEPTH_MARKERS = [
    "结构性", "二阶", "隐式", "契约", "根因", "范式", "系统性",
    "不是...而是", "本质", "深层", "根本",
    "structural", "second-order", "implicit", "root cause", "systemic",
]


def _score_completeness(section_body: str) -> tuple[int, list[str]]:
    """Score 0-10: are all four required sections present and non-trivial?"""
    score = 0
    issues: list[str] = []
    sections = {
        "现状审视": ["### 现状审视", "### Status review"],
        "优化方案": ["### 优化方案", "### Better path"],
        "隐患": ["### 隐患", "### Risks"],
        "预期": ["### 预期", "### Forecast"],
    }
    for name, headers in sections.items():
        found = any(h in section_body for h in headers)
        if found:
            # Check if section has substantive content (>50 chars after header)
            for h in headers:
                idx = section_body.find(h)
                if idx >= 0:
                    content = section_body[idx + len(h):]
                    # Find next ### or end
                    next_h = re.search(r"###|\Z", content)
                    if next_h:
                        content = content[:next_h.start()]
                    if len(content.strip()) > 50:
                        score += 2  # present + substantive
                    else:
                        score += 1  # present but thin
                        issues.append(f"{name}: section too short (<50 chars)")
                    break
        else:
            issues.append(f"{name}: section missing")
    return min(score, 10), issues


def _score_substance(section_body: str) -> tuple[int, list[str]]:
    """Score 0-10: is the optimization plan actionable or boilerplate?"""
    issues: list[str] = []
    # Find optimization plan section
    plan_match = re.search(r"### (?:优化方案|Better path)(.*?)(?=###|\Z)", section_body, re.DOTALL)
    if not plan_match:
        return 0, ["优化方案: section missing"]

    plan_text = plan_match.group(1).strip()
    if len(plan_text) < 50:
        return 2, ["优化方案: too short"]

    # Count boilerplate phrases
    boilerplate_count = sum(1 for p in _BOILERPLATE_PHRASES if p in plan_text.lower())
    # Count actionable indicators (file refs, specific changes, concrete steps)
    actionable_count = len(re.findall(r"[a-zA-Z_]+\.(?:dart|py|md|json|ts)", plan_text))
    actionable_count += len(re.findall(r"添加|删除|修改|新建|重构|补|改用", plan_text))

    if boilerplate_count >= 3 and actionable_count == 0:
        issues.append(f"优化方案: boilerplate ({boilerplate_count} vague phrases, 0 actionable)")
        return 3
    elif boilerplate_count >= 2 and actionable_count <= 1:
        issues.append(f"优化方案: mostly boilerplate ({boilerplate_count} vague, {actionable_count} actionable)")
        return 5
    elif actionable_count >= 2:
        return 9, []
    elif actionable_count >= 1:
        return 7, []
    else:
        return 6, ["优化方案: lacks concrete actions"]


def _score_falsifiability(section_body: str) -> tuple[int, list[str]]:
    """Score 0-10: does 预期 contain testable/falsifiable predictions?"""
    issues: list[str] = []
    pred_match = re.search(r"### (?:预期|Forecast)(.*?)(?=###|\Z)", section_body, re.DOTALL)
    if not pred_match:
        return 0, ["预期: section missing"]

    pred_text = pred_match.group(1).strip()
    if len(pred_text) < 50:
        return 2, ["预期: too short"]

    # Count falsifiable markers (good)
    falsifiable_count = sum(1 for m in _FALSIFIABLE_MARKERS if m in pred_text)
    # Count vague phrases (bad)
    vague_count = sum(1 for p in _VAGUE_PREDICTION_PHRASES if p in pred_text.lower())

    # Check for numbered predictions (预测①, 预测②, etc.)
    has_numbered = bool(re.search(r"预测[①②③④⑤\d]|prediction\s*\d", pred_text, re.IGNORECASE))

    if has_numbered and falsifiable_count >= 2:
        return 10, []
    elif falsifiable_count >= 2 and vague_count <= 1:
        return 8, []
    elif falsifiable_count >= 1:
        return 6, []
    elif vague_count >= 3:
        issues.append(f"预期: too many vague phrases ({vague_count}), no falsifiable markers")
        return 3
    else:
        issues.append("预期: no falsifiable predictions found")
        return 4


def _score_depth(section_body: str) -> tuple[int, list[str]]:
    """Score 0-10: does the reflection go beyond 'what we did' to structural insight?"""
    issues: list[str] = []
    depth_count = sum(1 for m in _DEPTH_MARKERS if m in section_body)
    # Check if it mentions specific files/versions (grounded) vs pure abstraction
    has_grounding = bool(re.findall(r"[a-zA-Z_]+\.(?:dart|py|md)|V\d+\.\d+", section_body))

    if depth_count >= 4 and has_grounding:
        return 10, []
    elif depth_count >= 3:
        return 8, []
    elif depth_count >= 2:
        return 6, []
    elif depth_count >= 1:
        return 5, []
    else:
        issues.append("reflection lacks structural/second-order thinking markers")
        return 3, issues


def assess_reflections(project_dir: str | Path) -> dict:
    """Assess the quality of all deep-layer reflections.

    Returns {sections: [...], total_sections: N, average_score: float,
             degraded_sections: [...], summary: str}.
    Each section: {date, scores: {completeness, substance, falsifiability, depth},
                  total: int, issues: [...], is_degraded: bool}.
    """
    project_dir = Path(project_dir)
    m = Memory(project_dir)
    deep_path = m.p["deep_file"]
    if not deep_path.exists():
        return {"sections": [], "total_sections": 0, "average_score": 0, "degraded_sections": []}

    text = deep_path.read_text(encoding="utf-8")
    # Split by ## YYYY-MM-DD
    parts = re.split(r"## (\d{4}-\d{2}-\d{2})", text)
    if len(parts) < 3:
        return {"sections": [], "total_sections": 0, "average_score": 0, "degraded_sections": []}

    sections: list[dict] = []
    for i in range(1, len(parts), 2):
        date = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        full_section = f"## {date}{body}"

        c_score, c_issues = _score_completeness(body)
        s_score, s_issues = _score_substance(body)
        f_score, f_issues = _score_falsifiability(body)
        d_score, d_issues = _score_depth(body)

        total = c_score + s_score + f_score + d_score
        all_issues = c_issues + s_issues + f_issues + d_issues
        is_degraded = total < 20  # <50% of 40

        sections.append({
            "date": date,
            "scores": {
                "completeness": c_score,
                "substance": s_score,
                "falsifiability": f_score,
                "depth": d_score,
            },
            "total": total,
            "max": 40,
            "issues": all_issues,
            "is_degraded": is_degraded,
        })

    avg = sum(s["total"] for s in sections) / len(sections) if sections else 0
    degraded = [s for s in sections if s["is_degraded"]]

    return {
        "sections": sections,
        "total_sections": len(sections),
        "average_score": round(avg, 1),
        "degraded_sections": degraded,
        "degraded_count": len(degraded),
    }


def quality_report(result: dict) -> str:
    """Render reflection quality assessment as a human/agent-readable report."""
    if not result["sections"]:
        return "[quality] no deep-layer reflections found"

    lines = [
        f"# Reflection Quality Assessment",
        f"Sections assessed: {result['total_sections']}",
        f"Average score: {result['average_score']}/40",
        f"Degraded sections (<20/40): {result['degraded_count']}",
        "",
    ]

    for s in result["sections"]:
        status = "⚠ DEGRADED" if s["is_degraded"] else "✓"
        sc = s["scores"]
        lines.append(f"## {s['date']} [{status}] {s['total']}/40")
        lines.append(f"  completeness: {sc['completeness']}/10 | substance: {sc['substance']}/10 | "
                      f"falsifiability: {sc['falsifiability']}/10 | depth: {sc['depth']}/10")
        if s["issues"]:
            for issue in s["issues"][:3]:
                lines.append(f"  - {issue}")
        lines.append("")

    if result["degraded_count"] > 0:
        lines.append(f"⚠ {result['degraded_count']} section(s) may be degraded (diary entries, not insights).")
        lines.append("→ Consider rewriting these sections with actionable plans and falsifiable predictions.")
    else:
        lines.append("✅ All sections meet quality threshold.")

    return "\n".join(lines)