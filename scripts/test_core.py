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
    analyze_major,
    classify_role,
    detect_summary_body_conflict,
    extract_deliverables,
    extract_identity,
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

# ---------------------------------------------------------------------------
# 以下为第二轮测试报告（N1–N9）的回归用例
# ---------------------------------------------------------------------------

# N1 [P0] 毕业年份的「带月份区间」写法必须被识别。
# 旧正则 `毕业时间[：:]?\s*(20\d{2})年?[^\d]{0,8}(20\d{2})` 的中间段不允许出现数字，
# 「2024年7月-2025年6月」整条漏掉 → 判「未限制」→ 给出错误的「可以投递」。
month_range = analyze_graduation("岗位要求：毕业时间：2024年7月-2025年6月，本科及以上学历。", profile)
assert month_range["结论"] == "不符合", month_range
assert "2024-2025" in month_range["说明"], month_range
assert analyze_graduation("毕业时间：2024-2025", profile)["结论"] == "不符合"
assert analyze_graduation("岗位要求：毕业时间：2026年9月-2028年8月，本科及以上学历。", profile)["结论"] == "符合"
# 开区间写法「2027年以后」也应满足
assert analyze_graduation("任职要求：本硕在校生（毕业时间2027年以后）。", profile)["结论"] == "符合"
# 开区间不一定带「毕业时间」四个字，只有「2027年以后毕业」也要认出来
assert analyze_graduation("任职要求：2027年以后毕业，本科或研究生在读，专业不限。", profile)["结论"] == "符合"
assert analyze_graduation("任职要求：7. 2027年及以后毕业优先；现场实习者优先。", profile)["结论"] == "符合"
assert analyze_graduation("任职要求：2029年以后毕业。", profile)["结论"] == "不符合"
# 只写单一年份时按具体届次处理，不能再判「未限制」
assert analyze_graduation("任职要求：毕业时间：2029年6月。", profile)["结论"] == "不符合"
# 提了毕业时间却解析不出年份 → 需核实，而不是替招聘方宣布「什么届都行」
assert analyze_graduation("任职要求：毕业时间：近期到岗，具体面议。", profile)["结论"] == "需核实"
# 画像没填毕业年份时不能瞎猜
assert analyze_graduation("毕业时间：2024年7月-2025年6月", CandidateProfile(graduation_year=None))["结论"] == "需核实"

# N1 的实际后果：漏识别会给出错误的「可以投递」
p0_verdict = analyze_jd(
    "AI产品实习生\n岗位职责：负责需求梳理与原型设计。\n"
    "任职要求：毕业时间：2024年7月-2025年6月，每周4天，实习3个月。",
    profile,
)
assert p0_verdict["decision"] == "不建议投递", p0_verdict["decision"]

# N3 专业匹配必须双向成立：JD 提到「统计」不再无条件判「符合」。
# 旧实现末尾挂着 `or "统计" in evidence`，任何专业只要 JD 提到统计都会通过。
assert analyze_major("任职要求：统计学、数学相关专业优先。", CandidateProfile(major="经济统计学"))["结论"] == "符合"
assert analyze_major("任职要求：统计学、数学相关专业优先。", CandidateProfile(major="英语"))["结论"] == "加分项不满足"
assert analyze_major("任职要求：统计学、数学相关专业优先。", CandidateProfile(major="会计学"))["结论"] == "加分项不满足"
assert analyze_major("任职要求：计算机、软件工程相关专业。", CandidateProfile(major="计算机科学与技术"))["结论"] == "符合"

# N4 平台水印不得被当成岗位名（「智联招聘」命中 role_markers 的「招聘」）
platform_watermark = (
    "14.智联招聘 2026-09-17 更新\n"
    "AI产品经理实习生 200-300元/天\n"
    "北京·朝阳区·望京本科实习招1人\n"
    "岗位职责\n负责AI产品的需求梳理与原型设计。\n"
    "任职要求\n本科及以上学历，每周4天，实习3个月。"
)
identity = extract_identity(platform_watermark)
assert identity["role_title"] == "AI产品经理实习生", identity
watermark_analysis = analyze_jd(platform_watermark, profile)
assert watermark_analysis["role_family"] == "AI产品与Agent产品", watermark_analysis["role_family"]
# 带真实岗位名的平台行不能被误杀
assert extract_identity("24.脉脉 AI产品助理实习生（AI通话方向）\n岗位职责：参与评测。")["role_title"] == "AI产品助理实习生（AI通话方向）"

# N5 交付物回退不得把「任职要求」里的句子当成交付物。
# 同时覆盖标题误判：正文里的「为符合岗位要求的同学」不是要求段标题。
guarded = extract_deliverables(
    "AI产品实习生\n职位描述 日常实习：面向全体在校生，为符合岗位要求的同学提供项目实践机会。\n"
    "1、参与模型评测业务，输出评测报告； 2、探索模型评测的各种先进方法。\n"
    "职位要求 1、本科及以上学历在读； 2、熟悉提示词工程。"
)
assert guarded, "职责段应能提取到交付物"
assert any("评测报告" in item for item in guarded), guarded
assert all("本科及以上学历" not in item for item in guarded), guarded
assert all("提示词工程" not in item for item in guarded), guarded

requirement_only = extract_deliverables(
    "某公司 数据分析实习生\n任职要求：1. 具备扎实的统计学基础。2. 熟练使用SQL。3. 输出周度经营分析报告。"
)
assert all("统计学基础" not in item for item in requirement_only), requirement_only

# N9 天数自相矛盾时应判「需核实」，不能拿第一个值直接硬否决
conflicting_days = analyze_jd(
    "数据分析实习生\n职位描述\n岗位职责：参与数据看板搭建。\n任职要求：实习期每周3天，转正后每周5天。",
    CandidateProfile(available_days=4, max_months=4),
)
assert conflicting_days["schedule"]["day_status"] == "需核实", conflicting_days["schedule"]
assert conflicting_days["decision"] == "投递前需确认", conflicting_days["decision"]

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
    "n1_month_range": month_range["结论"],
    "n1_p0_decision": p0_verdict["decision"],
    "n3_major_two_way": "ok",
    "n4_platform_watermark": identity["role_title"],
    "n5_heading_guard": len(guarded),
    "n9_conflict_days": conflicting_days["schedule"]["day_status"],
})
