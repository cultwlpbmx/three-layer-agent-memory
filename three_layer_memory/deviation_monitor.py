"""
Deviation monitor — real-time guardrails against drifting from project tenets.

Phase 2-2 of the cognitive upgrade: the system continuously monitors the
agent's current work context against the project's stable constraints
(surface tenets/principles/application rules) and forward-looking warnings
(deep-layer risks/predictions), and raises alerts when the agent is about
to violate its own past judgments.

This is the "guardian angel" layer: the agent declared "we do not add new
features" in the surface, but is now about to add one → alert. The agent
predicted "if X is not done, Y will break" in the deep layer, and is now
working near Y without having done X → alert.

Usage:
    from three_layer_memory.deviation_monitor import check_deviation, deviation_report

    # Before/during work
    alerts = check_deviation(project_dir, context="我要给聊天页加一个新的视频通话功能")
    print(deviation_report(alerts))

    # Or with files
    alerts = check_deviation(project_dir, files=["voice_service.dart"], context="新增语音通话")
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .core import Memory


# --- surface constraint extraction --------------------------------------------

def _extract_surface_constraints(overview_path: Path) -> dict:
    """Extract tenets, principles, and application rules from the surface overview.

    Returns {tenets: [...], principles: [...], rules: [...], preferences: [...]}.
    Each item is a string (one constraint).
    """
    if not overview_path.exists():
        return {"tenets": [], "principles": [], "rules": [], "preferences": []}

    text = overview_path.read_text(encoding="utf-8")
    sections: dict[str, list[str]] = {"tenets": [], "principles": [], "rules": [], "preferences": []}

    # 核心宗旨（逐字保留） — extract blockquote content
    tenet_match = re.search(
        r"## 核心宗旨.*?\n>(.*?)(?=\n##|\Z)", text, re.DOTALL
    )
    if tenet_match:
        for line in tenet_match.group(1).strip().split("\n"):
            line = line.strip().lstrip(">").strip()
            if line and len(line) > 5:
                sections["tenets"].append(line)

    # 哲学思想 — extract blockquote
    phil_match = re.search(
        r"## 哲学思想.*?\n>(.*?)(?=\n##|\Z)", text, re.DOTALL
    )
    if phil_match:
        for line in phil_match.group(1).strip().split("\n"):
            line = line.strip().lstrip(">").strip()
            if line and len(line) > 5:
                sections["principles"].append(line)

    # 应用准则 — extract bullet points
    rules_match = re.search(
        r"## 应用准则.*?(?=\n##|\Z)", text, re.DOTALL
    )
    if rules_match:
        for line in rules_match.group(0).split("\n"):
            line = line.strip()
            if line.startswith("- ") and len(line) > 5:
                sections["rules"].append(line.lstrip("- "))

    # 固定偏好 — extract bullet points
    pref_match = re.search(
        r"## 固定偏好.*?(?=\n##|\Z)", text, re.DOTALL
    )
    if pref_match:
        for line in pref_match.group(0).split("\n"):
            line = line.strip()
            if line.startswith("- ") and len(line) > 5:
                sections["preferences"].append(line.lstrip("- "))

    return sections


# --- deep layer risk extraction ------------------------------------------------

def _extract_deep_risks(deep_path: Path, sections_count: int = 3) -> list[dict]:
    """Extract recent deep-layer risks (隐患) and predictions (预期).

    Returns list of {type: "risk"|"prediction", text: "...", date: "..."}.
    Only the most recent N sections to avoid stale alerts.
    """
    if not deep_path.exists():
        return []

    text = deep_path.read_text(encoding="utf-8")

    # Split by ## YYYY-MM-DD sections
    parts = re.split(r"## (\d{4}-\d{2}-\d{2})", text)
    if len(parts) < 3:
        return []

    # Build (date, body) pairs, take last N
    section_pairs = []
    for i in range(1, len(parts), 2):
        date = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        section_pairs.append((date, body))

    results: list[dict] = []
    for date, body in section_pairs[-sections_count:]:
        # Extract 隐患 / Risks subsection
        risk_match = re.search(
            r"### (?:隐患|Risks)(.*?)(?=###|\Z)", body, re.DOTALL
        )
        if risk_match:
            for bullet in re.findall(r"[-*]\s+(.+?)(?=\n[-*]|\n###|\Z)", risk_match.group(1), re.DOTALL):
                bullet = bullet.strip()
                if len(bullet) > 10:
                    results.append({"type": "risk", "text": bullet[:300], "date": date})

        # Extract 预期 / Forecast subsection
        pred_match = re.search(
            r"### (?:预期|Forecast)(.*?)(?=###|\Z)", body, re.DOTALL
        )
        if pred_match:
            for bullet in re.findall(r"[-*]\s+(.+?)(?=\n[-*]|\n###|\Z)", pred_match.group(1), re.DOTALL):
                bullet = bullet.strip()
                if len(bullet) > 10:
                    results.append({"type": "prediction", "text": bullet[:300], "date": date})

    return results


# --- deviation detection ------------------------------------------------------

# Keywords that signal "adding new feature" vs "fixing/improving existing"
_NEW_FEATURE_KEYWORDS = ["新功能", "新增", "添加功能", "加功能", "new feature", "add feature", "新模块", "新建"]
_NO_NEW_FEATURE_KEYWORDS = ["不再增加新功能", "不再加", "只做修缮", "不铺新摊子", "一个模块一个模块修缮", "不增加新功能"]

# Fuzzy new-feature detection: "新" near "功能/模块/页面/通话" within a window
# This catches "加一个新的视频通话功能" which has 新+功能 separated
_NEW_FEATURE_FUZZY = re.compile(
    r"新.{0,15}?(?:功能|模块|页面|通话|服务|feature|module|page)",
    re.IGNORECASE,
)
# Also: "加一个" + "功能/模块" pattern
_ADD_FEATURE_RE = re.compile(
    r"(?:加|添加|增加|新建|实现).{0,15}?(?:功能|模块|页面|通话|服务)",
    re.IGNORECASE,
)

# Keywords for common constraint violations
_CONSTRAINT_PATTERNS = [
    {
        "keywords": _NEW_FEATURE_KEYWORDS,
        "constraint": "产品功能已定位定型，不再增加新功能",
        "severity": "high",
        "check": lambda ctx: (
            any(kw in ctx.lower() for kw in _NEW_FEATURE_KEYWORDS)
            or bool(_NEW_FEATURE_FUZZY.search(ctx))
            or bool(_ADD_FEATURE_RE.search(ctx))
        ),
    },
    {
        "keywords": ["教知识", "教授学科", "学科知识", "teach knowledge"],
        "constraint": "不是教授学科知识的，专注家庭关系成长",
        "severity": "high",
        "check": lambda ctx: any(kw in ctx.lower() for kw in ["教知识", "教授学科", "学科知识", "teach knowledge"]),
    },
    {
        "keywords": ["贴性格标签", "贴标签", "personality label"],
        "constraint": "不贴性格标签",
        "severity": "medium",
        "check": lambda ctx: any(kw in ctx.lower() for kw in ["贴性格标签", "贴标签", "personality label"]),
    },
    {
        "keywords": ["评判对错", "judge right wrong"],
        "constraint": "不评判对错",
        "severity": "medium",
        "check": lambda ctx: any(kw in ctx.lower() for kw in ["评判对错", "judge right wrong"]),
    },
]


def check_deviation(
    project_dir: str | Path,
    *,
    context: str = "",
    files: list[str] | None = None,
    deep_sections: int = 5,
) -> dict:
    """Check if the agent's current work context deviates from project constraints.

    Returns a dict with:
      - surface_alerts: violations of surface tenets/rules/preferences
      - deep_alerts: work that touches recent deep-layer risks/predictions
      - total_alerts: count
      - all_clear: True if no alerts
    """
    project_dir = Path(project_dir)
    m = Memory(project_dir)

    result: dict = {
        "context": context,
        "files": files or [],
        "surface_alerts": [],
        "deep_alerts": [],
        "all_clear": True,
    }

    # --- 1. Surface constraint checks ---
    constraints = _extract_surface_constraints(m.p["overview"])

    # Check against predefined constraint patterns FIRST (independent of rules)
    # These are hardcoded patterns that signal known constraint violations.
    # If the pattern matches the context, alert regardless of rule text.
    triggered_patterns: set[str] = set()
    for pattern in _CONSTRAINT_PATTERNS:
        if pattern["check"](context):
            # Find the most relevant rule text from surface constraints
            best_rule = ""
            for rule in constraints["rules"] + constraints["preferences"]:
                if any(kw.lower() in rule.lower() for kw in pattern["keywords"]):
                    best_rule = rule[:200]
                    break
            if not best_rule:
                # No matching rule found in surface, but pattern still triggered
                best_rule = pattern["constraint"]
            result["surface_alerts"].append({
                "type": "surface_rule",
                "severity": pattern["severity"],
                "constraint": pattern["constraint"],
                "rule_text": best_rule,
                "evidence": f"context mentions: {context[:100]}",
            })
            triggered_patterns.add(pattern["constraint"])
            result["all_clear"] = False

    # Also check explicit "不增加新功能" preference (uses fuzzy matching too)
    for pref in constraints["preferences"]:
        if any(kw in pref for kw in _NO_NEW_FEATURE_KEYWORDS):
            # Use both direct keywords and fuzzy patterns
            is_new_feature = (
                any(kw in context.lower() for kw in _NEW_FEATURE_KEYWORDS)
                or bool(_NEW_FEATURE_FUZZY.search(context))
                or bool(_ADD_FEATURE_RE.search(context))
            )
            if is_new_feature and "产品功能已定位定型，不再增加新功能" not in [a["constraint"] for a in result["surface_alerts"]]:
                result["surface_alerts"].append({
                    "type": "surface_preference",
                    "severity": "high",
                    "constraint": "产品功能已定位定型，不再增加新功能",
                    "rule_text": pref[:200],
                    "evidence": f"context mentions new feature: {context[:100]}",
                })
                result["all_clear"] = False
            break

    # --- 2. Deep layer risk/prediction checks ---
    deep_risks = _extract_deep_risks(m.p["deep_file"], sections_count=deep_sections)

    # Extract keywords from context and files for matching
    file_terms = [f.lower() for f in (files or []) if len(f) >= 3]
    context_terms = []
    if context:
        words = re.findall(r"[a-zA-Z_]{4,}|[\u4e00-\u9fff]{2,}", context)
        context_terms = [w.lower() for w in words[:15]]

    for risk in deep_risks:
        risk_text = risk["text"].lower()
        file_hits = 0
        context_hits = 0
        matched_terms = []

        # File matches are strong signals — 1 file match is enough
        for term in file_terms:
            if term in risk_text:
                file_hits += 1
                matched_terms.append(term)

        # Context word matches — need >=2 for relevance
        for term in context_terms:
            if len(term) >= 2 and term in risk_text:
                context_hits += 1
                matched_terms.append(term)

        total_hits = file_hits + context_hits
        # File match (1+) OR context match (2+) triggers alert
        if file_hits >= 1 or context_hits >= 2:
            result["deep_alerts"].append({
                "type": risk["type"],
                "severity": "medium" if risk["type"] == "risk" else "low",
                "date": risk["date"],
                "text": risk["text"][:200],
                "matched_terms": matched_terms,
                "evidence": f"your work context touches a deep-layer {risk['type']} from {risk['date']}",
            })
            result["all_clear"] = False

    result["total_alerts"] = len(result["surface_alerts"]) + len(result["deep_alerts"])
    return result


def deviation_report(result: dict) -> str:
    """Render deviation check result as a human/agent-readable report."""
    if result["all_clear"]:
        return "[deviation] ✅ All clear — current work context does not violate any known constraints or touch recent deep-layer warnings."

    lines = [
        f"# Deviation Monitor — {len(result['surface_alerts'])} surface + {len(result['deep_alerts'])} deep alerts",
        f"Context: {result.get('context', '')}",
        "",
    ]

    if result["surface_alerts"]:
        lines.append("## ⚠ Surface constraint violations")
        for a in result["surface_alerts"]:
            lines.append(f"  [{a['severity'].upper()}] {a['constraint']}")
            lines.append(f"    rule: {a['rule_text'][:120]}")
            lines.append(f"    evidence: {a['evidence'][:120]}")
            lines.append("")

    if result["deep_alerts"]:
        lines.append("## ⚠ Deep-layer risk/prediction touched")
        for a in result["deep_alerts"]:
            lines.append(f"  [{a['severity'].upper()}] {a['type']} from {a['date']}")
            lines.append(f"    {a['text'][:150]}")
            lines.append(f"    matched: {', '.join(a['matched_terms'][:5])}")
            lines.append("")

    lines.append("→ Review these alerts before proceeding. If the deviation is intentional, acknowledge it explicitly.")
    return "\n".join(lines)