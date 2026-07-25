"""
Auto-consolidation layer — automatically discover recurring patterns (N>=2)
across middle-layer task records and propose experience laws for human review.

Phase 2-3 of the cognitive upgrade: the system itself scans all task records,
finds where the same difficulty/solution/effect recurs, and generates candidate
laws. This replaces the manual "consolidate step 3" where a human or agent had
to read recent records and notice patterns — the system now does the noticing.

The output is *candidate* laws, not final laws. A human reviews and decides
which to promote to surface "application rules" or global-deep laws. This
follows the paradigm's principle: "reflection is an obligation, adoption is
a right" — the system proposes, the human disposes.

Usage:
    from three_layer_memory.auto_consolidate import discover_patterns, pattern_report

    patterns = discover_patterns(project_dir)
    print(pattern_report(patterns))
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from .core import Memory


# --- difficulty/solution extraction -------------------------------------------

# Common patterns in Chinese task records
_DIFFICULTY_HEADERS = ["遇到的困难", "困难", "踩坑", "坑", "真因", "Difficulties", "Pit"]
_SOLUTION_KEYWORDS = ["修复", "解决", "绕过", "改为", "改用", "替换", "补", "fix", "workaround", "resolve"]
_EFFECT_KEYWORDS = ["导致", "使得", "引发", "caused", "resulted"]


def _extract_difficulty_blocks(text: str) -> list[str]:
    """Extract difficulty/root-cause blocks from a task record."""
    blocks: list[str] = []
    # Find sections under "遇到的困难" headers
    for header in _DIFFICULTY_HEADERS:
        pattern = rf"## {re.escape(header)}.*?(?=\n##|\Z)"
        for m in re.finditer(pattern, text, re.DOTALL):
            content = m.group(0)
            # Extract bullet points
            for bullet in re.findall(r"[-*]\s+(.+?)(?=\n[-*]|\n##|\Z)", content, re.DOTALL):
                bullet = bullet.strip()
                if len(bullet) > 10:
                    blocks.append(bullet[:200])
    # Also find lines containing "真因" (root cause)
    for m in re.finditer(r"真因[：:]\s*(.+?)(?=\n|$)", text):
        cause = m.group(1).strip()
        if len(cause) > 5:
            blocks.append(cause[:200])
    return blocks


def _extract_solution_blocks(text: str) -> list[str]:
    """Extract solution/fix blocks from a task record."""
    blocks: list[str] = []
    # Lines in "完成情况" or "关键产出" that contain solution keywords
    for section in ["完成情况", "关键产出", "Done", "Key output"]:
        pattern = rf"## {re.escape(section)}.*?(?=\n##|\Z)"
        for m in re.finditer(pattern, text, re.DOTALL):
            content = m.group(0)
            for bullet in re.findall(r"[-*]\s+(.+?)(?=\n[-*]|\n##|\Z)", content, re.DOTALL):
                bullet = bullet.strip()
                if any(kw in bullet.lower() for kw in [k.lower() for k in _SOLUTION_KEYWORDS]):
                    if len(bullet) > 10:
                        blocks.append(bullet[:200])
    return blocks


def _extract_keywords(text: str, min_len: int = 2) -> list[str]:
    """Extract significant keywords from a text block for similarity matching."""
    # Chinese words (2+ chars)
    cn_words = re.findall(r"[\u4e00-\u9fff]{2,6}", text)
    # English/code words (3+ chars)
    en_words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", text)
    return cn_words + en_words


def _similarity(a: list[str], b: list[str]) -> float:
    """Jaccard similarity between two keyword lists."""
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union > 0 else 0.0


# --- pattern discovery --------------------------------------------------------

def discover_patterns(
    project_dir: str | Path,
    *,
    min_n: int = 2,
    similarity_threshold: float = 0.35,
    max_patterns: int = 20,
) -> dict:
    """Scan all middle-layer task records and discover recurring patterns.

    Finds difficulties/solutions that appear in N>=min_n records with similar
    keywords, and generates candidate experience laws.

    Returns {patterns: [...], total_records: N, total_patterns: M}.
    Each pattern: {type, count, records, keywords, candidate_law, evidence}.
    """
    project_dir = Path(project_dir)
    m = Memory(project_dir)

    mid_dir = m.p["middle_dir"]
    task_files = []
    for f in sorted(mid_dir.iterdir()):
        if f.suffix == ".md" and not f.name.startswith("_") and not f.name.startswith("INDEX") and "归档说明" not in f.name:
            task_files.append(f)
    arch_dir = mid_dir / "archive"
    if arch_dir.is_dir():
        for f in sorted(arch_dir.iterdir()):
            if f.suffix == ".md" and not f.name.startswith("_"):
                task_files.append(f)

    # Collect difficulties and solutions from all records
    all_difficulties: list[dict] = []  # {text, keywords, file, date}
    all_solutions: list[dict] = []

    for tf in task_files:
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", tf.name)
        date_str = date_match.group(1) if date_match else ""
        try:
            text = tf.read_text(encoding="utf-8")
        except Exception:
            continue

        for block in _extract_difficulty_blocks(text):
            kws = _extract_keywords(block)
            if kws:
                all_difficulties.append({
                    "text": block, "keywords": kws,
                    "file": tf.name, "date": date_str,
                })

        for block in _extract_solution_blocks(text):
            kws = _extract_keywords(block)
            if kws:
                all_solutions.append({
                    "text": block, "keywords": kws,
                    "file": tf.name, "date": date_str,
                })

    # Cluster difficulties by similarity
    patterns: list[dict] = []
    used_diff: set[int] = set()
    for i, d in enumerate(all_difficulties):
        if i in used_diff:
            continue
        cluster = [d]
        used_diff.add(i)
        for j in range(i + 1, len(all_difficulties)):
            if j in used_diff:
                continue
            if _similarity(d["keywords"], all_difficulties[j]["keywords"]) >= similarity_threshold:
                cluster.append(all_difficulties[j])
                used_diff.add(j)
        if len(cluster) >= min_n:
            # Find common keywords across the cluster
            kw_counter = Counter()
            for item in cluster:
                for kw in item["keywords"]:
                    kw_counter[kw] += 1
            common_kws = [kw for kw, cnt in kw_counter.most_common(10) if cnt >= min_n]
            patterns.append({
                "type": "recurring_difficulty",
                "count": len(cluster),
                "records": [{"file": item["file"], "date": item["date"], "text": item["text"][:100]} for item in cluster],
                "keywords": common_kws,
                "candidate_law": _generate_law_candidate("difficulty", common_kws, cluster),
                "evidence": "; ".join(f"{item['file']}({item['date']})" for item in cluster[:5]),
            })

    # Cluster solutions by similarity
    used_sol: set[int] = set()
    for i, s in enumerate(all_solutions):
        if i in used_sol:
            continue
        cluster = [s]
        used_sol.add(i)
        for j in range(i + 1, len(all_solutions)):
            if j in used_sol:
                continue
            if _similarity(s["keywords"], all_solutions[j]["keywords"]) >= similarity_threshold:
                cluster.append(all_solutions[j])
                used_sol.add(j)
        if len(cluster) >= min_n:
            kw_counter = Counter()
            for item in cluster:
                for kw in item["keywords"]:
                    kw_counter[kw] += 1
            common_kws = [kw for kw, cnt in kw_counter.most_common(10) if cnt >= min_n]
            patterns.append({
                "type": "recurring_solution",
                "count": len(cluster),
                "records": [{"file": item["file"], "date": item["date"], "text": item["text"][:100]} for item in cluster],
                "keywords": common_kws,
                "candidate_law": _generate_law_candidate("solution", common_kws, cluster),
                "evidence": "; ".join(f"{item['file']}({item['date']})" for item in cluster[:5]),
            })

    # Sort by count descending
    patterns.sort(key=lambda x: x["count"], reverse=True)

    return {
        "patterns": patterns[:max_patterns],
        "total_records": len(task_files),
        "total_difficulties": len(all_difficulties),
        "total_solutions": len(all_solutions),
        "total_patterns": len(patterns),
    }


def _generate_law_candidate(pattern_type: str, keywords: list[str], cluster: list[dict]) -> str:
    """Generate a candidate law string from a recurring pattern."""
    if pattern_type == "difficulty":
        kw_str = "、".join(keywords[:5])
        return f"当涉及{kw_str}时，注意该类问题已出现 {len(cluster)} 次，需优先检查已知解法"
    else:
        kw_str = "、".join(keywords[:5])
        return f"涉及{kw_str}时，已有 {len(cluster)} 次成功解法可复用"


def pattern_report(result: dict) -> str:
    """Render discovered patterns as a human/agent-readable report."""
    lines = [
        f"# Auto-Consolidation — Pattern Discovery",
        f"Scanned {result['total_records']} records: {result['total_difficulties']} difficulties, {result['total_solutions']} solutions",
        f"Discovered {result['total_patterns']} recurring patterns (N>={2})",
        "",
    ]
    for i, p in enumerate(result.get("patterns", []), 1):
        lines.append(f"## Pattern {i}: {p['type']} (x{p['count']})")
        lines.append(f"  keywords: {', '.join(p['keywords'][:8])}")
        lines.append(f"  candidate law: {p['candidate_law']}")
        lines.append(f"  evidence: {p['evidence']}")
        for rec in p["records"][:3]:
            lines.append(f"    - {rec['file']} ({rec['date']}): {rec['text'][:80]}")
        lines.append("")
    lines.append("→ These are CANDIDATE laws for human review. Promote to surface rules or global-deep if accepted.")
    return "\n".join(lines)