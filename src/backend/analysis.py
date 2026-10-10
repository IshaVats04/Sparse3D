"""Aggregate finished experiments into the view-count / view-arrangement analysis tables.

Every number is an average of measured values from stored experiments. A metric that was never measured
(for example Chamfer distance without ground truth) stays None. Insights are derived mechanically from the
aggregated data; nothing is hard-coded.
"""

from collections import defaultdict
from statistics import mean
from typing import Any, Dict, List, Optional

from .db import METRIC_KEYS

METHODS = ("classical", "neural")


def _avg(rows: List[Dict[str, Any]], key: str) -> Optional[float]:
    vals = [r[key] for r in rows if r.get(key) is not None]
    return round(mean(vals), 4) if vals else None


def _aggregate(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not rows:
        return None
    out = {k: _avg(rows, k) for k in METRIC_KEYS}
    out["runs"] = len(rows)
    return out


def _method_rows(experiments: List[Dict[str, Any]], method: str, group_key: str) -> Dict[Any, List[Dict[str, Any]]]:
    grouped: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for e in experiments:
        m = e["methods"].get(method)
        if m and m["status"] == "completed":
            grouped[e[group_key]].append(m)
    return grouped


def build_analysis(experiments: List[Dict[str, Any]]) -> Dict[str, Any]:
    usable = [e for e in experiments if any(m["status"] == "completed" for m in e["methods"].values())]
    result: Dict[str, Any] = {"has_data": bool(usable), "view_count": [], "arrangement": [],
                              "failures": [], "insights": []}

    for group_key, out_key, label in (("num_views", "view_count", "views"),
                                      ("view_arrangement", "arrangement", "arrangement")):
        per_method = {m: _method_rows(usable, m, group_key) for m in METHODS}
        keys = sorted({k for pm in per_method.values() for k in pm if k is not None},
                      key=(lambda x: x) if group_key == "num_views" else str)
        for k in keys:
            result[out_key].append({label: k, "classical": _aggregate(per_method["classical"].get(k, [])),
                                    "neural": _aggregate(per_method["neural"].get(k, []))})

    for e in experiments:
        for name, m in e["methods"].items():
            if m["status"] == "failed":
                reason = m["message"] or "Reconstruction failed"
            elif (m["status"] == "completed" and m.get("registered") is not None
                  and m["registered"] < (m.get("total_input") or 0)):
                reason = f"Only {m['registered']} of {m['total_input']} views registered"
            else:
                continue
            result["failures"].append({"job_id": e["job_id"], "num_views": e["num_views"],
                                       "view_arrangement": e["view_arrangement"], "method": name, "reason": reason})
        if e["status"] == "failed" and not any(m["status"] == "completed" for m in e["methods"].values()):
            result["failures"].append({"job_id": e["job_id"], "num_views": e["num_views"],
                                       "view_arrangement": e["view_arrangement"], "method": "pipeline",
                                       "reason": e.get("summary") or "Experiment failed (see its logs)"})

    result["insights"] = _insights(result)
    return result


def _fmt(v: float, nd: int = 3) -> str:
    return f"{v:.{nd}f}".rstrip("0").rstrip(".")


def _insights(analysis: Dict[str, Any]) -> List[str]:
    notes: List[str] = []
    vc = analysis["view_count"]
    for method in METHODS:
        pts = [(r["views"], r[method]) for r in vc if r[method]]
        if len(pts) < 2:
            continue
        lo, hi = pts[0], pts[-1]
        name = method.capitalize()
        for key, label, unit, higher_better in (
                ("registration_ratio_pct", "registration ratio", "%", True),
                ("f_score", "F-score", "", True),
                ("chamfer_distance", "Chamfer distance", "", False),
                ("point_count", "point count", "", True)):
            a, b = lo[1].get(key), hi[1].get(key)
            if a is None or b is None or a == b:
                continue
            direction = "rises" if b > a else "falls"
            notes.append(f"{name} {label} {direction} from {_fmt(a)}{unit} at {lo[0]} views to {_fmt(b)}{unit} "
                         f"at {hi[0]} views.")
        a, b = lo[1].get("runtime_sec"), hi[1].get("runtime_sec")
        if a and b:
            notes.append(f"{name} runtime goes from {_fmt(a, 1)}s at {lo[0]} views to {_fmt(b, 1)}s at {hi[0]} views.")
    for r in vc:
        c, n = r["classical"], r["neural"]
        if not c or not n:
            continue
        for key, label, lower_better in (("f_score", "F-score", False), ("chamfer_distance", "Chamfer distance", True),
                                         ("point_count", "point count", False)):
            if c.get(key) is not None and n.get(key) is not None and c[key] != n[key]:
                better_is_neural = (n[key] < c[key]) if lower_better else (n[key] > c[key])
                winner = "neural" if better_is_neural else "classical"
                notes.append(f"At {r['views']} views the {winner} method has the "
                             f"better {label} ({_fmt(n[key])} neural vs {_fmt(c[key])} classical).")
    arr = [r for r in analysis["arrangement"]
           if r["classical"] and r["classical"].get("registration_ratio_pct") is not None]
    if len(arr) >= 2:
        best = max(arr, key=lambda r: r["classical"]["registration_ratio_pct"])
        worst = min(arr, key=lambda r: r["classical"]["registration_ratio_pct"])
        if best is not worst:
            notes.append(f"View arrangement matters: '{best['arrangement']}' registered "
                         f"{_fmt(best['classical']['registration_ratio_pct'])}% of views versus "
                         f"{_fmt(worst['classical']['registration_ratio_pct'])}% for '{worst['arrangement']}'.")
    if not notes and analysis["has_data"]:
        notes.append("Only one setting has been measured so far; run a view-count sweep to see trends.")
    return notes
