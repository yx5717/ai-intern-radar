"""Evaluate the shipped Python rule engine against the frozen external gold labels.

IMPORTANT — this is an INTERNAL REGRESSION run, not a blind test.

`radar_core.py` was written after the external gold labels already existed, so the
engine author had seen the answers. Its numbers therefore cannot be presented as
cross-platform generalisation. The only blind result in this project remains
`rule-baseline-v1`, whose predictions were frozen before labelling
(see data/external_predictions_frozen_v1.meta.json).

Run:  ./.venv/Scripts/python.exe scripts/evaluate_python_engine.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from radar_core import ROLE_ALIASES, CandidateProfile, analyze_jd, normalize_role_family

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ENGINE_VERSION = "radar-core-py-v3"
DECISION_TO_GOLD = {"可以投递": "通过", "投递前需确认": "需要核实", "不建议投递": "不通过"}
COMPARED_METRICS = ("role_family", "weekly_days", "minimum_months", "constraint_result", "bad_case_binary", "bad_case_type")

# 与冻结基线保持完全相同的画像，否则两套数字无法并列比较。
FROZEN_PROFILE = CandidateProfile(
    school="首都经济贸易大学", school_tier="非985/211", major="经济统计学", degree="本科",
    graduation_year=2028, available_days=4, min_months=2, max_months=4, skills="",
)


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def rate(correct: int, total: int) -> float:
    return correct / total if total else 0.0


def main() -> None:
    rows = load_jsonl(DATA / "external_gold_v1.jsonl")
    total = len(rows)
    counters = {key: 0 for key in COMPARED_METRICS}
    predictions = []
    alias_hits = 0

    for row in rows:
        gold = row["gold"]
        analysis = analyze_jd(row["jd_raw"], FROZEN_PROFILE, "")
        gold_family = normalize_role_family(gold["role_family"])
        if gold_family != gold["role_family"]:
            alias_hits += 1
        predicted_family = normalize_role_family(analysis["role_family"])
        predicted_decision = DECISION_TO_GOLD.get(analysis["decision"])
        gold_bad_case_type = gold.get("bad_case_type", "无")

        if predicted_family == gold_family:
            counters["role_family"] += 1
        if analysis["schedule"]["weekly_days"] == gold["weekly_days"]:
            counters["weekly_days"] += 1
        if analysis["schedule"]["minimum_months"] == gold["minimum_months"]:
            counters["minimum_months"] += 1
        if predicted_decision == gold["constraint_result"]:
            counters["constraint_result"] += 1
        if analysis["bad_case_binary"] == (gold_bad_case_type != "无"):
            counters["bad_case_binary"] += 1
        if analysis["bad_case_type"] == gold_bad_case_type:
            counters["bad_case_type"] += 1

        predictions.append({
            "job_id": row["job_id"],
            "role_family": predicted_family,
            "weekly_days": analysis["schedule"]["weekly_days"],
            "minimum_months": analysis["schedule"]["minimum_months"],
            "constraint_result": predicted_decision,
            "bad_case_type": analysis["bad_case_type"],
            "bad_case_binary": analysis["bad_case_binary"],
            "decision": analysis["decision"],
            "fit_score": analysis["fit_score"],
            "engine_version": ENGINE_VERSION,
        })

    metrics = {
        key: {"correct": value, "total": total, "accuracy": rate(value, total)}
        for key, value in counters.items()
    }

    baseline = json.loads((DATA / "external_eval_v1.json").read_text(encoding="utf-8"))
    comparison = {
        key: {
            "baseline": baseline["metrics"][key]["accuracy"],
            "python_engine": metrics[key]["accuracy"],
        }
        for key in COMPARED_METRICS
    }

    report = {
        "evaluation_scope": "internal_regression_not_blind",
        "caveat": (
            "Python 引擎（radar_core.py）在金标准建立之后编写，作者已见过答案，"
            "因此本结果只用于回归与迭代，不具备盲测意义，不得作为跨平台泛化成绩对外呈现。"
            "项目唯一的盲测结果仍是 rule-baseline-v1。"
        ),
        "engine_version": ENGINE_VERSION,
        "gold_version": "external-gold-v1",
        "baseline_version": baseline["prediction_version"],
        "sample_count": total,
        "platforms": baseline["platforms"],
        "profile": {
            "available_days": FROZEN_PROFILE.available_days,
            "min_months": FROZEN_PROFILE.min_months,
            "max_months": FROZEN_PROFILE.max_months,
        },
        "taxonomy_aliases": ROLE_ALIASES,
        "taxonomy_alias_hits": alias_hits,
        "metrics": metrics,
        "comparison_with_blind_baseline": comparison,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    (DATA / "python_engine_eval_v1.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (DATA / "python_engine_predictions_v1.jsonl").open("w", encoding="utf-8") as handle:
        for item in predictions:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Python engine internal regression ({total} samples, NOT blind)")
    print(f"{'指标':<14}{'盲测基线':>12}{'Python 引擎':>14}")
    for key, label in [("role_family", "岗位大类"), ("weekly_days", "每周天数"),
                       ("minimum_months", "最低月数"), ("constraint_result", "硬约束结论"),
                       ("bad_case_binary", "Bad Case识别"), ("bad_case_type", "Bad Case类型")]:
        print(f"{label:<12}{comparison[key]['baseline']:>8.1%}{comparison[key]['python_engine']:>14.1%}")
    print(f"词表别名折叠命中：{alias_hits} 条")


if __name__ == "__main__":
    main()
