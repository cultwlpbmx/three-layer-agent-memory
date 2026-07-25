"""
Meta-meta-cognition layer — discover blind spots across the entire reflection history.

Phase 3-1 of the cognitive upgrade: the system reads ALL deep-layer reflections
(not just the latest one) and finds patterns in HOW the agent reflects — not what
it reflects about. This is "reflection on reflection" — meta-meta-cognition.

It discovers things like:
  - "In 30 reflections, you never questioned assumption X"
  - "Your optimization plans are always file-level, never paradigm-level"
  - "Your risks are always technical, never cognitive/social/ethical"
  - "Your predictions are always vague, never falsifiable"

This is the foundation of AGI-level self-awareness: "knowing what you don't know
you don't know" — discovering the blind spots in your own reflection process.

Usage:
    from three_layer_memory.meta_meta_cognition import discover_blind_spots, blind_spot_report

    result = discover_blind_spots(project_dir)
    print(blind_spot_report(result))
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from .core import Memory
from .reflection_quality import assess_reflections


# --- reflection dimension categories ------------------------------------------

# Categories for "隐患" (risks) — what kind of risk does the agent typically identify?
_RISK_CATEGORIES = {
    "technical": ["编译", "部署", "bug", "端点", "API", "数据库", "性能", "崩溃", "技术",
                   "compile", "deploy", "database", "crash", "performance", "technical"],
    "security": ["密钥", "凭据", "安全", "漏洞", "注入", "secret", "credential", "security", "vulnerability"],
    "data_privacy": ["隐私", "数据", "telemetry", "用户数据", "privacy", "data"],
    "cognitive": ["认知", "盲区", "假设", "偏见", "思维", "cognitive", "bias", "assumption", "blind spot"],
    "social": ["团队", "沟通", "协作", "用户反馈", "team", "communication", "collaboration"],
    "ethical": ["伦理", "道德", "合规", "法律", "ethics", "compliance", "legal"],
    "architectural": ["架构", "结构", "范式", "设计", "耦合", "architecture", "structural", "design"],
}

# Categories for "优化方案" (optimization plans) — what level does the agent think at?
_PLAN_LEVELS = {
    "file_level": ["文件", "修改", "添加", "删除", "file", "edit", "add", "remove", ".dart", ".py"],
    "module_level": ["模块", "组件", "服务", "module", "component", "service"],
    "paradigm_level": ["范式", "原则", "准则", "协议", "paradigm", "principle", "protocol", "rule"],
    "process_level": ["流程", "步骤", "检查点", "process", "workflow", "checkpoint"],
}


def _categorize_text(text: str, categories: dict[str, list[str]]) -> dict[str, int]:
    """Count how many times each category's keywords appear in text."""
    text_lower = text.lower()
    counts: dict[str, int] = {}
    for cat, keywords in categories.items():
        count = sum(1 for kw in keywords if kw.lower() in text_lower)
        counts[cat] = count
    return counts


def discover_blind_spots(project_dir: str | Path) -> dict:
    """Analyze all deep-layer reflections to find meta-cognitive blind spots.

    Returns {total_sections, risk_profile, plan_profile, blind_spots: [...], quality_stats}.
    """
    project_dir = Path(project_dir)
    m = Memory(project_dir)
    deep_path = m.p["deep_file"]
    if not deep_path.exists():
        return {"total_sections": 0, "blind_spots": []}

    text = deep_path.read_text(encoding="utf-8")
    parts = re.split(r"## (\d{4}-\d{2}-\d{2})", text)

    sections: list[dict] = []
    for i in range(1, len(parts), 2):
        date = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""

        # Extract subsections
        risk_match = re.search(r"### (?:隐患|Risks)(.*?)(?=###|\Z)", body, re.DOTALL)
        risk_text = risk_match.group(1) if risk_match else ""
        plan_match = re.search(r"### (?:优化方案|Better path)(.*?)(?=###|\Z)", body, re.DOTALL)
        plan_text = plan_match.group(1) if plan_match else ""
        pred_match = re.search(r"### (?:预期|Forecast)(.*?)(?=###|\Z)", body, re.DOTALL)
        pred_text = pred_match.group(1) if pred_match else ""
        review_match = re.search(r"### (?:现状审视|Status review)(.*?)(?=###|\Z)", body, re.DOTALL)
        review_text = review_match.group(1) if review_match else ""

        sections.append({
            "date": date,
            "risk_text": risk_text,
            "plan_text": plan_text,
            "pred_text": pred_text,
            "review_text": review_text,
            "body": body,
        })

    if not sections:
        return {"total_sections": 0, "blind_spots": []}

    # --- 1. Profile risk categories across all sections ---
    all_risk_counts: dict[str, int] = defaultdict(int)
    for s in sections:
        cat_counts = _categorize_text(s["risk_text"], _RISK_CATEGORIES)
        for cat, cnt in cat_counts.items():
            all_risk_counts[cat] += cnt

    # --- 2. Profile plan levels ---
    all_plan_counts: dict[str, int] = defaultdict(int)
    for s in sections:
        cat_counts = _categorize_text(s["plan_text"], _PLAN_LEVELS)
        for cat, cnt in cat_counts.items():
            all_plan_counts[cat] += cnt

    # --- 3. Discover blind spots ---
    blind_spots: list[dict] = []

    # Blind spot: risk categories never mentioned
    for cat, cnt in sorted(all_risk_counts.items(), key=lambda x: x[1]):
        if cnt == 0:
            blind_spots.append({
                "type": "unreflected_risk_category",
                "category": cat,
                "description": f"在 {len(sections)} 次反思中，从未在'隐患'节提及'{cat}'类风险",
                "severity": "medium" if cat in ("cognitive", "ethical", "social") else "low",
            })

    # Blind spot: plan levels never used
    for level, cnt in sorted(all_plan_counts.items(), key=lambda x: x[1]):
        if cnt == 0:
            blind_spots.append({
                "type": "unreflected_plan_level",
                "category": level,
                "description": f"在 {len(sections)} 次反思中，'优化方案'从未在'{level}'层面思考",
                "severity": "high" if level == "paradigm_level" else "medium",
            })

    # Blind spot: dominant risk category (over-reliance)
    total_risk = sum(all_risk_counts.values())
    if total_risk > 0:
        for cat, cnt in all_risk_counts.items():
            ratio = cnt / total_risk
            if ratio > 0.6 and cnt > 5:
                blind_spots.append({
                    "type": "over_reliant_risk_category",
                    "category": cat,
                    "description": f"{ratio:.0%} 的隐患集中在'{cat}'类——可能忽略了其他类风险",
                    "severity": "medium",
                    "ratio": round(ratio, 2),
                })

    # Blind spot: dominant plan level (over-reliance)
    total_plan = sum(all_plan_counts.values())
    if total_plan > 0:
        for level, cnt in all_plan_counts.items():
            ratio = cnt / total_plan
            if ratio > 0.7 and cnt > 5:
                blind_spots.append({
                    "type": "over_reliant_plan_level",
                    "category": level,
                    "description": f"{ratio:.0%} 的优化方案在'{level}'层面——可能缺乏更高层面的思考",
                    "severity": "medium",
                    "ratio": round(ratio, 2),
                })

    # --- 4. Quality stats from reflection_quality ---
    quality = assess_reflections(project_dir)
    avg_scores = {"completeness": 0, "substance": 0, "falsifiability": 0, "depth": 0}
    if quality["sections"]:
        for dim in avg_scores:
            avg_scores[dim] = round(
                sum(s["scores"][dim] for s in quality["sections"]) / len(quality["sections"]), 1
            )

    # Blind spot: consistently low quality dimension
    for dim, avg in avg_scores.items():
        if avg < 3.0:
            blind_spots.append({
                "type": "consistently_low_dimension",
                "category": dim,
                "description": f"'{dim}'维度平均分仅 {avg}/10——反思在这个维度系统性退化",
                "severity": "high",
            })

    return {
        "total_sections": len(sections),
        "risk_profile": dict(all_risk_counts),
        "plan_profile": dict(all_plan_counts),
        "quality_stats": avg_scores,
        "blind_spots": blind_spots,
        "total_blind_spots": len(blind_spots),
    }


def blind_spot_report(result: dict) -> str:
    """Render blind spot analysis as a human/agent-readable report."""
    if not result.get("total_sections"):
        return "[meta-meta] no deep-layer reflections found"

    lines = [
        f"# Meta-Meta-Cognition — Blind Spot Analysis",
        f"Sections analyzed: {result['total_sections']}",
        f"Blind spots discovered: {result['total_blind_spots']}",
        "",
        "## Risk profile (what kinds of risks do you identify?)",
    ]
    for cat, cnt in sorted(result.get("risk_profile", {}).items(), key=lambda x: -x[1]):
        lines.append(f"  {cat}: {cnt}")

    lines.append("\n## Plan profile (what level do you think at?)")
    for level, cnt in sorted(result.get("plan_profile", {}).items(), key=lambda x: -x[1]):
        lines.append(f"  {level}: {cnt}")

    lines.append("\n## Quality stats (average scores across all sections)")
    for dim, avg in result.get("quality_stats", {}).items():
        lines.append(f"  {dim}: {avg}/10")

    if result["blind_spots"]:
        lines.append(f"\n## ⚠ Blind spots ({result['total_blind_spots']})")
        for bs in result["blind_spots"]:
            lines.append(f"  [{bs['severity'].upper()}] {bs['type']}: {bs['description']}")

    lines.append("\n→ These are OBSERVATIONS about your reflection habits, not commands.")
    lines.append("→ Review with human — some blind spots may be intentional (not relevant to this project).")
    return "\n".join(lines)