import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from radar_core import (
    CandidateProfile,
    ROLE_ORDER,
    analyze_graduation,
    analyze_jd,
    classify_role,
    detect_summary_body_conflict,
    extract_deliverables,
    extract_skills,
    normalize_role_family,
)


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

role_cases = {
    "量化投研实习生": "金融、投研与风险管理",
    "审计实习生": "财务、审计与税务",
    "战略咨询实习生": "咨询、行业研究与战略分析",
    "品牌市场实习生": "市场、品牌与商业运营",
    "人力资源实习生": "人力资源与组织发展",
    "商务拓展实习生": "销售、商务与客户成功",
    "供应链采购实习生": "供应链、采购与物流",
    "产品助理实习生": "产品与项目管理",
}
for role_title, expected_family in role_cases.items():
    actual_family, _, _ = classify_role(role_title, f"{role_title}\n负责日常项目支持和分析报告。")
    assert actual_family == expected_family, (role_title, actual_family)
    assert actual_family in ROLE_ORDER

# 回归：历史词表别名需折叠到当前分类词表，否则同一概念两种写法会被判错
assert normalize_role_family("职能支持/边界岗位") == "职能支持/其他岗位"
assert normalize_role_family("数据分析与商业/经营分析") == "数据分析与商业/经营分析"
assert normalize_role_family("职能支持/其他岗位") in ROLE_ORDER

# 回归：相邻行的「优先」不得把硬约束降级为加分项（P0）
neighbour_preferred = analyze_jd(
    "AI产品经理实习生\n任职要求：\n1. 本科及以上学历\n2. 每周出勤5天，实习期至少6个月\n3. 熟悉大模型优先",
    CandidateProfile(available_days=5, max_months=5),
)
assert neighbour_preferred["schedule"]["weekly_days"] == 5, neighbour_preferred["schedule"]
assert neighbour_preferred["schedule"]["minimum_months"] == 6, neighbour_preferred["schedule"]
assert next(row for row in neighbour_preferred["constraints"] if row["约束"] == "实习周期")["结论"] == "不符合"
assert neighbour_preferred["decision"] == "不建议投递"
assert neighbour_preferred["fit_score"] is None

# 同一句里真正写着「优先」时，仍应被识别为加分项
same_sentence_preferred = analyze_jd(
    "AI运营实习生\n每周4天优先，连续3个月。负责知识库运营。",
    CandidateProfile(available_days=2, max_months=4),
)
assert same_sentence_preferred["schedule"]["weekly_days"] is None

# 回归：单字母技能不得命中其它单词内部（R）
assert extract_skills("Product") == []
assert extract_skills("PRD document") == ["PRD"]
assert extract_skills("RAG pipeline") == ["RAG"]
assert "R" in extract_skills("熟悉 R 语言与 Python")
assert "R" in extract_skills("Python、R、Stata")
assert extract_skills("用 r 做统计") == []

# 回归：核心交付物只取职责段落，且不保留原文编号
duty_only = extract_deliverables(
    "工作职责：\n1. 负责用户调研与竞品分析，输出产品改进方案\n任职要求：\n1. 本科及以上学历，统计学相关专业优先"
)
assert duty_only, "职责段落应能提取到交付物"
assert all("本科及以上学历" not in item for item in duty_only)
assert all(not re.match(r"^\d", item) for item in duty_only)

# 回归：只填最长月数时不得编造下限
no_lower_bound = analyze_jd(
    "AI运营实习生\n每周3天，连续3个月。负责知识库运营。",
    CandidateProfile(min_months=None, max_months=6, available_days=4),
)
period_note = next(row for row in no_lower_bound["constraints"] if row["约束"] == "实习周期")["说明"]
assert "最长6个月" in period_note, period_note
assert "2-6" not in period_note

# 回归：无简历时不给综合适配度
assert analyze_jd("数据分析实习生\n4天/周，最少3个月。负责看板搭建。", CandidateProfile())["fit_score"] is None

# 回归：加分项只在所属分句内生效，不得吞掉同一行的硬要求
clause_scoped = analyze_jd(
    "数据分析实习生\n职位描述\n岗位要求：1.本科及以上学历，可长期实习者优先，每周工作4天及以上",
    CandidateProfile(available_days=4, max_months=4),
)
assert clause_scoped["schedule"]["weekly_days"] == 4, clause_scoped["schedule"]

# 回归：区间写法需被识别，取下限参与比较
range_parsed = analyze_jd(
    "数据运营实习生\n职位描述\n岗位职责：负责看板搭建。\n岗位要求：可出勤4-5天/周，3-6个月实习时长",
    CandidateProfile(available_days=4, max_months=4),
)
assert range_parsed["schedule"]["weekly_days"] == 4, range_parsed["schedule"]
assert range_parsed["schedule"]["minimum_months"] == 3, range_parsed["schedule"]

# 回归：平台摘要与正文时间要求不一致需标为 Bad Case
conflict = detect_summary_body_conflict(
    "数据分析师\n200-400/天\n北京\n本科\n3天/周\n最少3个月\n岗位职责\n协助数据提取与清洗。\n岗位要求：每周至少5天"
)
assert conflict["conflict"] is True, conflict
assert "每周出勤" in conflict["dimensions"], conflict

consistent = detect_summary_body_conflict(
    "数据分析师\n200-400/天\n北京\n本科\n4天/周\n最少3个月\n岗位职责\n协助数据提取与清洗。\n岗位要求：可出勤4-5天/周，3-6个月实习时长"
)
assert consistent["conflict"] is False, consistent

# 回归：无正文区时不应误报冲突
assert detect_summary_body_conflict("数据分析实习生\n4天/周，最少3个月")["conflict"] is False

print({
    "hard_school": hard_school["decision"],
    "preferred_major": next(row for row in preferred_major["constraints"] if row["约束"] == "专业")["结论"],
    "statistics_match": statistics_match["decision"],
    "senior_only": senior_only["结论"],
    "senior_preferred": senior_preferred["结论"],
    "business_role_categories": len(role_cases),
    "neighbour_preferred": neighbour_preferred["decision"],
    "duty_only_deliverables": len(duty_only),
    "summary_body_conflict": conflict["conflict"],
})
