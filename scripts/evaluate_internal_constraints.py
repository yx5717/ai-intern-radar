"""内部 30 条样本的「学校层次 / 专业 / 毕业年份」三维度回归。

为什么单独做这一份评测：
    外部 26 条金标准只人工标注了岗位大类、出勤天数、实习月数和投递结论。
    学校层次、专业、毕业年份这三个维度在外部集里没有任何标注，所以网页上那个
    「硬约束结论 84.6%」并不覆盖它们——三个维度判错，那个数字也不会动。
    这份脚本把这三维度单独量出来，避免「硬约束」这个标签被误读。

诚实声明：
    data/internal_constraint_gold_v1.jsonl 的标注由助手本人完成
    （review_status = pending_human_review），不是独立人工金标准。
    它只能作为回归基线，不能当作准确率对外呈现。

Run:  ./.venv/Scripts/python.exe scripts/evaluate_internal_constraints.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from radar_core import CandidateProfile, analyze_graduation, analyze_major, analyze_school

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DIMENSIONS = ("school_tier", "major", "graduation_year")
DIMENSION_LABELS = {"school_tier": "学校层次", "major": "专业", "graduation_year": "毕业年份"}

# 与网页默认画像一致：本人的真实条件。
PROFILE = CandidateProfile(
    school="首都经济贸易大学", school_tier="非985/211", major="经济统计学", degree="本科",
    graduation_year=2028, available_days=4, min_months=2, max_months=4, skills="",
)


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    samples = load_jsonl(DATA / "gold_labels_v1.jsonl")
    gold = {row["job_id"]: row for row in load_jsonl(DATA / "internal_constraint_gold_v1.jsonl")}
    missing = [row["job_id"] for row in samples if row["job_id"] not in gold]
    if missing:
        raise SystemExit(f"以下内部样本缺少三维度标注：{missing}")

    counters = {key: 0 for key in DIMENSIONS}
    disagreements = []
    for row in samples:
        job_id = row["job_id"]
        jd = row["jd_raw"]
        predicted = {
            "school_tier": analyze_school(jd, PROFILE)["结论"],
            "major": analyze_major(jd, PROFILE)["结论"],
            "graduation_year": analyze_graduation(jd, PROFILE)["结论"],
        }
        for key in DIMENSIONS:
            if predicted[key] == gold[job_id][key]:
                counters[key] += 1
            else:
                disagreements.append({
                    "job_id": job_id,
                    "dimension": DIMENSION_LABELS[key],
                    "gold": gold[job_id][key],
                    "engine": predicted[key],
                    "note": gold[job_id].get("note", ""),
                })

    total = len(samples)
    metrics = {
        key: {"correct": counters[key], "total": total, "accuracy": counters[key] / total}
        for key in DIMENSIONS
    }
    # 学校层次这一维在内部 30 条里没有任何正例，标出来避免把 100% 当成能力。
    distinct_gold = {key: sorted({row[key] for row in gold.values()}) for key in DIMENSIONS}

    report = {
        "evaluation_scope": "internal_regression_not_blind",
        "annotation_source": "assistant_self_review_pending_human_review",
        "caveat": (
            "三维度标注由助手完成、尚未经本人复核，只能用于回归，不得作为准确率对外呈现。"
            "外部 26 条金标准不含这三个维度，因此这里的数字与网页上的「硬约束结论」不可互相替代。"
        ),
        "sample_count": total,
        "gold_distinct_values": distinct_gold,
        "metrics": metrics,
        "disagreements": disagreements,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (DATA / "internal_constraint_eval_v1.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"内部 {total} 条 · 学校层次 / 专业 / 毕业年份（自标注，待人工复核）")
    for key in DIMENSIONS:
        item = metrics[key]
        print(f"  {DIMENSION_LABELS[key]:<6}{item['correct']:>3}/{item['total']:<3}{item['accuracy']:>8.1%}"
              f"   标注取值分布：{distinct_gold[key]}")
    print()
    if disagreements:
        print(f"不一致 {len(disagreements)} 处：")
        for item in disagreements:
            print(f"  [{item['job_id']}] {item['dimension']}：标注={item['gold']} 引擎={item['engine']}")
            if item["note"]:
                print(f"        {item['note']}")
    else:
        print("无不一致。")


if __name__ == "__main__":
    main()
