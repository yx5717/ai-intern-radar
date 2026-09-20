import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from radar_core import CandidateProfile, analyze_graduation, analyze_jd


profile = CandidateProfile()
hard_school = analyze_jd(
    "AI产品实习生\n每周4天，连续3个月。任职要求：仅限985、211高校本科生，专业不限，2028届。负责AI产品需求分析和迭代。",
    profile,
)
assert next(row for row in hard_school["constraints"] if row["约束"] == "学校层次")["结论"] == "不符合"
assert hard_school["decision"] == "不建议投递"

preferred_major = analyze_jd(
    "AI运营实习生\n每周3天，连续3个月。计算机、软件工程相关专业优先。负责知识库、Prompt和工作流运营。",
    profile,
)
assert next(row for row in preferred_major["constraints"] if row["约束"] == "专业")["结论"] == "加分项不满足"

statistics_match = analyze_jd(
    "大模型评测实习生\n4天/周，最少3个月。本科及以上，计算机、数据科学、统计相关专业优先。负责测试集和Bad Case分析。",
    profile,
)
assert next(row for row in statistics_match["constraints"] if row["约束"] == "专业")["结论"] == "符合"
assert statistics_match["schedule"]["weekly_days"] == 4
assert statistics_match["schedule"]["minimum_months"] == 3
assert statistics_match["role_family"] == "大模型评测、训练与数据质量"

senior_only = analyze_graduation(
    "任职要求：本科大四学生，细心负责，有较强的数据分析能力。",
    profile,
    reference_date=date(2026, 9, 20),
)
assert senior_only["结论"] == "不符合"
assert "推算为本科大三" in senior_only["说明"]
assert "岗位要求本科大四" in senior_only["说明"]

senior_preferred = analyze_graduation(
    "任职要求：本科大四学生优先，专业不限。",
    profile,
    reference_date=date(2026, 9, 20),
)
assert senior_preferred["结论"] == "加分项不满足"

senior_only_analysis = analyze_jd(
    "AI应用实习生\n每周4天，连续3个月。任职要求：本科大四学生，专业不限。负责Prompt和知识库运营。",
    profile,
)
assert next(row for row in senior_only_analysis["constraints"] if row["约束"] == "毕业年份")["结论"] == "不符合"
assert senior_only_analysis["decision"] == "不建议投递"

print({
    "hard_school": hard_school["decision"],
    "preferred_major": next(row for row in preferred_major["constraints"] if row["约束"] == "专业")["结论"],
    "statistics_match": statistics_match["decision"],
    "senior_only": senior_only["结论"],
    "senior_preferred": senior_preferred["结论"],
})
