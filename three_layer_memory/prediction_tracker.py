"""
Prediction tracker — verify deep-layer predictions against subsequent events.

Phase 3-3 of the cognitive upgrade: every deep-layer "预期/Forecast" prediction
is a falsifiable claim. This module tracks whether subsequent middle-layer
records confirm or falsify each prediction.

This closes the "prediction -> verification" loop:
  1. Deep layer says "if X is not done, Y will break" (prediction)
  2. Later middle-layer record says "Y broke because X was not done" (confirmation)
  3. System reports: "prediction from 2026-07-01 was CONFIRMED on 2026-07-14"

Or:
  1. Deep layer says "if X is not done, Y will break"
  2. Later middle-layer record says "Y works fine, X was not needed"
  3. System reports: "prediction from 2026-07-01 was FALSIFIED on 2026-07-14"

Falsified predictions trigger meta-reflection: "why was the prediction wrong?"

Usage:
    from three_layer_memory.prediction_tracker import track_predictions, prediction_report

    result = track_predictions(project_dir)
    print(prediction_report(result))
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .core import Memory


# --- prediction extraction ----------------------------------------------------

# Markers for falsifiable predictions (things that can be confirmed/falsified)
_PREDICTION_MARKERS = [
    "若", "如果", "当...时", "如果不", "若不", "如果不做",
    "预测", "观察哨", "预期", "验证条件", "反证条件",
    "if X", "falsifiable", "verifiable", "observable",
    "将", "会", "将导致", "会导致",
]

# Markers for confirmed outcomes
_CONFIRM_MARKERS = ["确认", "证实", "验证通过", "确实", "果然", "如预期",
                    "confirmed", "verified", "as expected"]

# Markers for falsified outcomes
_FALSIFY_MARKERS = ["证伪", "推翻", "不符", "未发生", "没有", "并未",
                    "实际", "反而", "falsified", "contradicted", "actually"]


def _extract_predictions(deep_text: str) -> list[dict]:
    """Extract falsifiable predictions from deep-layer sections.

    Returns list of {date, text, keywords, prediction_type}.
    prediction_type: "risk_warning" (if X then bad) or "expectation" (X will happen).
    """
    predictions: list[dict] = []
    parts = re.split(r"## (\d{4}-\d{2}-\d{2})", deep_text)

    for i in range(1, len(parts), 2):
        date = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""

        # Find 预期/Forecast subsection
        pred_match = re.search(r"### (?:预期|Forecast)(.*?)(?=###|\Z)", body, re.DOTALL)
        if not pred_match:
            continue

        pred_text = pred_match.group(1).strip()
        # Extract individual prediction bullets
        for bullet in re.findall(r"[-*]\s+(.+?)(?=\n[-*]|\n###|\Z)", pred_text, re.DOTALL):
            bullet = bullet.strip()
            if len(bullet) < 15:
                continue

            # Determine prediction type
            ptype = "expectation"
            if any(kw in bullet for kw in ["若不", "如果不", "若", "如果X", "将导致", "会导致"]):
                ptype = "risk_warning"

            # Extract keywords for matching
            keywords = re.findall(r"[\u4e00-\u9fff]{2,6}|[a-zA-Z_]{3,}", bullet)
            # Filter out common stopwords
            keywords = [kw for kw in keywords if kw not in
                        ("短期", "中期", "长期", "如果", "建议", "需要", "应该", "可以")]

            if len(keywords) >= 2:
                predictions.append({
                    "date": date,
                    "text": bullet[:300],
                    "keywords": keywords[:10],
                    "type": ptype,
                })

    return predictions


def _check_prediction_vs_record(prediction: dict, record_text: str, record_date: str) -> dict:
    """Check if a middle-layer record confirms or falsifies a prediction.

    Returns {status: "confirmed"|"falsified"|"touched"|"none", evidence: str}.
    """
    pred_keywords = set(kw.lower() for kw in prediction["keywords"])
    record_lower = record_text.lower()

    # Count keyword matches
    matched = [kw for kw in pred_keywords if kw in record_lower]

    if len(matched) < 2:
        return {"status": "none", "evidence": ""}

    # Check for confirmation markers
    has_confirm = any(m in record_lower for m in _CONFIRM_MARKERS)
    has_falsify = any(m in record_lower for m in _FALSIFY_MARKERS)

    if has_confirm and not has_falsify:
        return {
            "status": "confirmed",
            "evidence": f"keywords matched: {', '.join(matched[:5])}; confirmation markers found",
        }
    elif has_falsify and not has_confirm:
        return {
            "status": "falsified",
            "evidence": f"keywords matched: {', '.join(matched[:5])}; falsification markers found",
        }
    elif has_confirm and has_falsify:
        return {
            "status": "mixed",
            "evidence": f"keywords matched: {', '.join(matched[:5])}; both confirm and falsify markers found",
        }
    else:
        return {
            "status": "touched",
            "evidence": f"keywords matched: {', '.join(matched[:5])}; no confirm/falsify markers",
        }


def track_predictions(project_dir: str | Path) -> dict:
    """Track all deep-layer predictions against subsequent middle-layer records.

    Returns {total_predictions, confirmed, falsified, touched, unverified,
             predictions: [...], falsified_predictions: [...]}.
    """
    project_dir = Path(project_dir)
    m = Memory(project_dir)
    deep_path = m.p["deep_file"]
    if not deep_path.exists():
        return {"total_predictions": 0, "predictions": []}

    deep_text = deep_path.read_text(encoding="utf-8")
    predictions = _extract_predictions(deep_text)

    # Load all middle-layer records (sorted by date)
    mid_dir = m.p["middle_dir"]
    records: list[dict] = []
    for f in sorted(mid_dir.iterdir()):
        if f.suffix == ".md" and not f.name.startswith("_") and not f.name.startswith("INDEX"):
            date_match = re.match(r"(\d{4}-\d{2}-\d{2})", f.name)
            date_str = date_match.group(1) if date_match else ""
            try:
                text = f.read_text(encoding="utf-8")
                records.append({"date": date_str, "file": f.name, "text": text})
            except Exception:
                continue
    # Also check archive
    arch_dir = mid_dir / "archive"
    if arch_dir.is_dir():
        for f in sorted(arch_dir.iterdir()):
            if f.suffix == ".md" and not f.name.startswith("_"):
                date_match = re.match(r"(\d{4}-\d{2}-\d{2})", f.name)
                date_str = date_match.group(1) if date_match else ""
                try:
                    text = f.read_text(encoding="utf-8")
                    records.append({"date": date_str, "file": f.name, "text": text})
                except Exception:
                    continue

    # Sort records by date
    records.sort(key=lambda r: r["date"])

    # For each prediction, find records after its date
    results: list[dict] = []
    confirmed_count = 0
    falsified_count = 0
    touched_count = 0

    for pred in predictions:
        pred_result: dict = {
            **pred,
            "status": "unverified",
            "verification_records": [],
        }

        for rec in records:
            # Only check records after the prediction date
            if rec["date"] < pred["date"]:
                continue
            check = _check_prediction_vs_record(pred, rec["text"], rec["date"])
            if check["status"] != "none":
                pred_result["verification_records"].append({
                    "file": rec["file"],
                    "date": rec["date"],
                    "status": check["status"],
                    "evidence": check["evidence"],
                })
                # Update overall status (latest verification wins)
                if check["status"] in ("confirmed", "falsified", "mixed"):
                    pred_result["status"] = check["status"]
                elif pred_result["status"] == "unverified":
                    pred_result["status"] = "touched"

        if pred_result["status"] == "confirmed":
            confirmed_count += 1
        elif pred_result["status"] == "falsified":
            falsified_count += 1
        elif pred_result["status"] in ("touched", "mixed"):
            touched_count += 1

        results.append(pred_result)

    return {
        "total_predictions": len(predictions),
        "confirmed": confirmed_count,
        "falsified": falsified_count,
        "touched": touched_count,
        "unverified": len(predictions) - confirmed_count - falsified_count - touched_count,
        "predictions": results,
        "falsified_predictions": [p for p in results if p["status"] == "falsified"],
    }


def prediction_report(result: dict) -> str:
    """Render prediction tracking results as a human/agent-readable report."""
    if not result.get("total_predictions"):
        return "[predictions] no deep-layer predictions found"

    lines = [
        f"# Prediction Tracker — Verification Report",
        f"Total predictions: {result['total_predictions']}",
        f"  confirmed: {result['confirmed']}",
        f"  falsified: {result['falsified']}",
        f"  touched (no verdict): {result['touched']}",
        f"  unverified: {result['unverified']}",
        "",
    ]

    # Show confirmed
    confirmed = [p for p in result["predictions"] if p["status"] == "confirmed"]
    if confirmed:
        lines.append(f"## ✓ Confirmed ({len(confirmed)})")
        for p in confirmed[:5]:
            lines.append(f"  [{p['date']}] {p['text'][:100]}")
            for vr in p["verification_records"][-1:]:
                lines.append(f"    -> {vr['file']} ({vr['date']}): {vr['evidence'][:80]}")
        lines.append("")

    # Show falsified
    falsified = result.get("falsified_predictions", [])
    if falsified:
        lines.append(f"## ✗ Falsified ({len(falsified)}) — needs meta-reflection")
        for p in falsified[:5]:
            lines.append(f"  [{p['date']}] {p['text'][:100]}")
            for vr in p["verification_records"][-1:]:
                lines.append(f"    -> {vr['file']} ({vr['date']}): {vr['evidence'][:80]}")
        lines.append("  → Why was this prediction wrong? What assumption was incorrect?")
        lines.append("")

    # Show touched
    touched = [p for p in result["predictions"] if p["status"] in ("touched", "mixed")]
    if touched:
        lines.append(f"## ? Touched — no clear verdict ({len(touched)})")
        for p in touched[:5]:
            lines.append(f"  [{p['date']}] {p['text'][:80]}")
        lines.append("")

    if result["unverified"] > 0:
        lines.append(f"## ⏳ Unverified: {result['unverified']} predictions have no matching records yet")

    return "\n".join(lines)