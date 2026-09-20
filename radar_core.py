from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date


ROLE_ORDER = [
    "AI产品与Agent产品",
    "大模型评测、训练与数据质量",
    "AI运营、知识库与增长运营",
    "数据分析与商业/经营分析",
    "金融、投研与风险管理",
    "财务、审计与税务",
    "咨询、行业研究与战略分析",
    "市场、品牌与商业运营",
    "人力资源与组织发展",
    "销售、商务与客户成功",
    "供应链、采购与物流",
    "产品与项目管理",
    "职能支持/其他岗位",
]

ROLE_DESCRIPTIONS = {
    "AI产品与Agent产品": "需求、策略、原型、Agent 交付与版本迭代",
    "大模型评测、训练与数据质量": "评测、Benchmark、标注、Prompt、RAG 与 Agent 质量",
    "AI运营、知识库与增长运营": "知识库、用户反馈、Prompt 优化与 AI 自动化增长",
    "数据分析与商业/经营分析": "SQL、看板、指标、经营诊断与用户研究",
    "金融、投研与风险管理": "行研、投研、估值、银行、证券、量化与风控",
    "财务、审计与税务": "会计、财务分析、审计、税务与 FP&A",
    "咨询、行业研究与战略分析": "管理咨询、产业研究、政策研究与战略规划",
    "市场、品牌与商业运营": "市场调研、品牌、内容、用户、活动与电商运营",
    "人力资源与组织发展": "招聘、HRBP、薪酬、培训与组织发展",
    "销售、商务与客户成功": "销售、BD、渠道、商务合作与客户成功",
    "供应链、采购与物流": "供应链计划、采购、履约、仓储与物流",
    "产品与项目管理": "非 AI 产品、项目协同、PMO 与交付管理",
    "职能支持/其他岗位": "法务、行政等其他职能，或暂无法稳定归类的岗位",
}

SKILL_TERMS = [
    "Python", "SQL", "Excel", "R", "Stata", "FineBI", "Tableau", "Power BI", "Axure", "Figma",
    "Prompt", "RAG", "知识库", "工作流", "Agent", "智能体", "数据标注", "模型评测", "Bad Case",
    "Benchmark", "A/B测试", "用户研究", "需求分析", "PRD", "产品原型", "项目管理", "数据清洗",
    "数据可视化", "指标体系", "经营分析", "商业分析", "Pandas", "NumPy", "LangChain", "Dify", "Coze",
    "Wind", "Choice", "Bloomberg", "估值建模", "财务建模", "财务分析", "行业研究", "风险管理",
    "会计", "审计", "税务", "市场调研", "品牌策划", "用户运营", "内容运营", "广告投放",
    "人力资源", "招聘", "供应链", "采购", "物流", "客户成功", "CRM",
]


@dataclass
class CandidateProfile:
    school: str = "首都经济贸易大学"
    school_tier: str = "非985/211"
    major: str = "经济统计学"
    degree: str = "本科"
    graduation_year: int = 2028
    available_days: int = 4
    min_months: int = 2
    max_months: int = 4
    arrival: str = "立即到岗"
    skills: str = "Python、R、Stata、Excel、FineBI、数据清洗、数据可视化、Prompt、RAG、知识库、工作流、Agent、Bad Case、PRD、项目管理"

    def to_dict(self) -> dict:
        return asdict(self)


def compact(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text.replace("\u200b", "")).strip()


def evidence_fragment(text: str, pattern: str, radius: int = 34) -> str:
    match = re.search(pattern, text, re.I)
    if not match:
        return ""
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return compact(text[start:end].replace("\n", " "))


def extract_identity(jd_text: str) -> dict:
    lines = [compact(line) for line in jd_text.splitlines() if compact(line)]
    first = lines[0] if lines else ""
    first = re.sub(r"^\d+\s*[.．、]\s*", "", first)
    role_markers = (
        r"(?:实习生|实习|管培生|产品经理|产品助理|项目管理|数据分析师|算法|运营|"
        r"研究员|研究助理|分析师|咨询|投研|行研|金融|证券|银行|风控|财务|会计|审计|税务|"
        r"市场|品牌|人力资源|招聘|供应链|采购|物流|销售|商务|客户成功|训练师|工程师)"
    )
    title = ""
    company = ""
    for line in lines[:15]:
        if re.search(role_markers, line, re.I) and len(line) <= 90:
            candidate = re.sub(r"\s+\d{3,4}-\d{2}-\d{2}.*$", "", line).strip()
            candidate = re.sub(r"\s+\d+(?:-\d+)?元?/天.*$", "", candidate).strip()
            title = candidate
            break
    if not title:
        title = first[:80] or "未识别岗位名称"
    if first and title in first and first != title:
        company = first.split(title, 1)[0].strip(" -｜|")
    elif title == first:
        match = re.match(r"^([\u4e00-\u9fffA-Za-z0-9·]+)\s+(.+)$", title)
        if match and re.search(role_markers, match.group(2), re.I):
            company, title = match.group(1), match.group(2)
    return {"company": company or "未识别公司", "role_title": title}


def _day_mentions(text: str) -> list[dict]:
    results = []
    patterns = [
        r"周实习天数[：:]?\s*([1-7])\s*天",
        r"([1-7])\s*天\s*[/／]\s*周",
        r"(?:每周|一周|每星期)[^。；\n]{0,25}?([1-7])\s*[-~～至]\s*([1-7])\s*(?:天|日)",
        r"(?:每周|一周|每星期)[^。；\n]{0,25}?(?:至少|不少于|不低于|保证|可实习)?\s*([1-7])\s*(?:天|日)(?:以上)?",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            fragment = evidence_fragment(text, re.escape(match.group(0)), 20)
            low = int(match.group(1))
            high = int(match.group(2)) if match.lastindex and match.lastindex >= 2 and match.group(2) else low
            preferred = bool(re.search(r"优先|加分", fragment))
            minimum = bool(re.search(r"至少|不少于|不低于|以上", match.group(0)))
            results.append({"min": low, "max": high, "minimum": minimum, "preferred": preferred, "evidence": fragment})
    return results


def _month_mentions(text: str) -> list[dict]:
    results = []
    patterns = [
        r"总实习月数[：:]?\s*([2-9])\s*个?月",
        r"最少\s*([2-9])\s*个?月",
        r"(?:实习|持续|连续|保证|项目实践|实习期)[^。；\n]{0,30}?([2-9])\s*[-~～至]\s*([2-9])\s*个?月",
        r"(?:实习|持续|连续|保证|项目实践|实习期)[^。；\n]{0,30}?(?:至少|不少于|不低于)?\s*([2-9])\s*个?月(?:以上)?",
        r"(?:实习|持续|连续|保证|项目实践|实习期)[^。；\n]{0,30}?半年",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            fragment = evidence_fragment(text, re.escape(match.group(0)), 20)
            if "半年" in match.group(0):
                low = high = 6
            else:
                low = int(match.group(1))
                high = int(match.group(2)) if match.lastindex and match.lastindex >= 2 and match.group(2) else low
            results.append({
                "min": low, "max": high,
                "minimum": bool(re.search(r"至少|不少于|不低于|以上|最少", match.group(0))),
                "preferred": bool(re.search(r"优先|加分", fragment)),
                "evidence": fragment,
            })
    return results


def extract_schedule(jd_text: str, profile: CandidateProfile) -> dict:
    days = _dedupe(_day_mentions(jd_text))
    months = _dedupe(_month_mentions(jd_text))
    hard_days = [item for item in days if not item["preferred"]]
    hard_months = [item for item in months if not item["preferred"]]
    summary_days = next((item for item in hard_days if "天/周" in item["evidence"] or "周实习天数" in item["evidence"]), None)
    summary_months = next((item for item in hard_months if "总实习月数" in item["evidence"] or "最少" in item["evidence"]), None)
    required_days = summary_days["min"] if summary_days else (hard_days[0]["min"] if hard_days else None)
    required_months = summary_months["min"] if summary_months else (hard_months[0]["min"] if hard_months else None)
    day_conflict = len({(x["min"], x["max"]) for x in hard_days}) > 1
    month_conflict = len({(x["min"], x["max"]) for x in hard_months}) > 1

    day_status = "未提及"
    if required_days is not None:
        alternatives = [x for x in hard_days if x["min"] <= profile.available_days <= x["max"] or (x["minimum"] and x["min"] <= profile.available_days)]
        if required_days <= profile.available_days and not day_conflict:
            day_status = "符合"
        elif alternatives:
            day_status = "需核实"
        else:
            day_status = "不符合"

    month_status = "未提及"
    if required_months is not None:
        alternatives = [x for x in hard_months if x["min"] <= profile.max_months and x["max"] >= profile.min_months]
        if profile.min_months <= required_months <= profile.max_months and not month_conflict:
            month_status = "符合"
        elif alternatives:
            month_status = "需核实"
        else:
            month_status = "不符合"

    evidence = "；".join(dict.fromkeys([item["evidence"] for item in [*days, *months] if item["evidence"]]))[:420]
    return {
        "weekly_days": required_days,
        "minimum_months": required_months,
        "day_status": day_status,
        "month_status": month_status,
        "conflict": day_conflict or month_conflict,
        "evidence": evidence,
    }


def _dedupe(items: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for item in items:
        key = (item["min"], item["max"], item["preferred"], item["evidence"])
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def analyze_school(jd_text: str, profile: CandidateProfile) -> dict:
    fragments = re.findall(r"[^。；\n]{0,35}(?:985|211|双一流|重点院校|名校)[^。；\n]{0,35}", jd_text, re.I)
    if not fragments:
        return _constraint("学校层次", "未限制", "未发现明确学校层次要求", "")
    evidence = compact("；".join(fragments))[:320]
    preferred = bool(re.search(r"优先|加分|prefer", evidence, re.I))
    candidate_tiers = set() if profile.school_tier.startswith("非") else {profile.school_tier}
    if profile.school_tier == "985":
        candidate_tiers.update({"211", "双一流"})
    elif profile.school_tier == "211":
        candidate_tiers.add("双一流")
    tier_match = any(tier in evidence for tier in candidate_tiers)
    if preferred:
        return _constraint("学校层次", "加分项不满足" if not tier_match else "符合", "不会直接阻断投递", evidence)
    if re.search(r"985|211|双一流", evidence) and not tier_match:
        return _constraint("学校层次", "不符合", f"{profile.school}不属于岗位限定层次", evidence)
    return _constraint("学校层次", "需核实", "学校层次措辞不够明确", evidence)


def analyze_major(jd_text: str, profile: CandidateProfile) -> dict:
    if re.search(r"专业不限|专业不限制|不限专业", jd_text):
        return _constraint("专业", "符合", "岗位明确写明专业不限", evidence_fragment(jd_text, r"专业不限|不限专业"))
    fragments = re.findall(r"[^。；\n]{0,55}(?:专业优先|相关专业|专业背景|专业要求)[^。；\n]{0,35}", jd_text, re.I)
    if not fragments:
        return _constraint("专业", "未限制", "未发现明确专业限制", "")
    evidence = compact("；".join(fragments))[:420]
    preferred = bool(re.search(r"优先|加分", evidence))
    match_terms = ["统计", "经济", "数学", "金融", "经管", "数据科学"]
    matched = any(term in profile.major and term in evidence for term in match_terms) or "统计" in evidence
    computer_only = bool(re.search(r"(?:仅限|必须|要求)[^。；\n]{0,20}(?:计算机|软件工程|人工智能)", evidence))
    if matched:
        return _constraint("专业", "符合", f"{profile.major}在岗位接受范围内", evidence)
    if preferred:
        return _constraint("专业", "加分项不满足", "专业只是优先项，不直接阻断投递", evidence)
    if computer_only or (re.search(r"计算机|软件工程|人工智能", evidence) and not re.search(r"统计|数学|经济|金融|专业不限", evidence)):
        return _constraint("专业", "不符合", f"岗位仅接受计算机相关专业，{profile.major}不在列", evidence)
    return _constraint("专业", "需核实", f"未能确认{profile.major}是否属于相关专业", evidence)


_GRADE_VALUES = {"一": 1, "二": 2, "三": 3, "四": 4, "1": 1, "2": 2, "3": 3, "4": 4}
_GRADE_LABELS = {1: "一", 2: "二", 3: "三", 4: "四"}


def _academic_year_start(reference_date: date) -> int:
    return reference_date.year if reference_date.month >= 9 else reference_date.year - 1


def _undergraduate_grade(graduation_year: int, academic_year_start: int) -> int | None:
    grade = 5 - (graduation_year - academic_year_start)
    return grade if 1 <= grade <= 4 else None


def _grade_requirement(jd_text: str) -> dict | None:
    patterns = [
        r"本科\s*(?:大|第)([一二三四1-4])(?:年级)?(?:学生|在读|本科生)?",
        r"本科\s*([一二三四1-4])年级(?:学生|在读|本科生)?",
        r"大([一二三四])(?:年级)?(?:本科生|学生|在读)?",
        r"(应届本科|本科应届)(?:生|毕业生)?",
    ]
    matches = [match for pattern in patterns for match in re.finditer(pattern, jd_text)]
    if not matches:
        return None
    match = min(matches, key=lambda item: item.start())
    start_candidates = [jd_text.rfind(separator, 0, match.start()) for separator in "。；\n"]
    start = max(start_candidates) + 1
    end_candidates = [position for separator in "。；\n" if (position := jd_text.find(separator, match.end())) >= 0]
    end = min(end_candidates) if end_candidates else len(jd_text)
    evidence = compact(jd_text[start:end])[:240]

    if re.search(r"应届本科|本科应届", match.group(0)):
        required_grade = 4
    else:
        grade_token = next((group for group in match.groups() if group in _GRADE_VALUES), None)
        if grade_token is None:
            return None
        required_grade = _GRADE_VALUES[grade_token]

    before = jd_text[max(0, match.start() - 10):match.start()]
    after = jd_text[match.end():match.end() + 10]
    preferred = bool(
        re.search(r"(?:优先|加分)(?:考虑|招募)?\s*$", before)
        or re.match(r"\s*(?:者)?(?:优先|加分)", after)
    )
    minimum = bool(re.search(rf"(?:大|第)?[一二三四1-4](?:年级)?\s*(?:及以上|以上)", evidence))
    maximum = bool(re.search(rf"(?:大|第)?[一二三四1-4](?:年级)?\s*(?:及以下|以下)", evidence))
    return {
        "grade": required_grade,
        "preferred": preferred,
        "minimum": minimum,
        "maximum": maximum,
        "evidence": evidence,
    }


def analyze_graduation(jd_text: str, profile: CandidateProfile, reference_date: date | None = None) -> dict:
    years = [int(value) for value in re.findall(r"(20\d{2})\s*届", jd_text)]
    range_match = re.search(r"毕业时间[：:]?\s*(20\d{2})年?[^\d]{0,8}(20\d{2})", jd_text)
    evidence = evidence_fragment(jd_text, r"20\d{2}\s*届|毕业时间", 45)
    if range_match:
        low, high = map(int, range_match.groups())
        status = "符合" if low <= profile.graduation_year <= high else "不符合"
        return _constraint("毕业年份", status, f"个人为{profile.graduation_year}届，岗位范围为{low}-{high}", evidence)
    if not years:
        grade_requirement = _grade_requirement(jd_text)
        if not grade_requirement:
            return _constraint("毕业年份", "未限制", "未发现明确毕业年份或在读年级限制", "")
        current_date = reference_date or date.today()
        academic_start = _academic_year_start(current_date)
        candidate_grade = _undergraduate_grade(profile.graduation_year, academic_start)
        required_grade = grade_requirement["grade"]
        if profile.degree != "本科" or candidate_grade is None:
            return _constraint(
                "毕业年份", "需核实", f"岗位限制本科在读年级，但无法由{profile.degree}、{profile.graduation_year}届可靠换算",
                grade_requirement["evidence"],
            )
        matches_grade = (
            candidate_grade >= required_grade if grade_requirement["minimum"]
            else candidate_grade <= required_grade if grade_requirement["maximum"]
            else candidate_grade == required_grade
        )
        if matches_grade:
            status = "符合"
        elif grade_requirement["preferred"]:
            status = "加分项不满足"
        else:
            status = "不符合"
        school_year = f"{academic_start}-{academic_start + 1}学年"
        description = (
            f"个人为{profile.graduation_year}届，按{school_year}推算为本科大{_GRADE_LABELS[candidate_grade]}；"
            f"岗位要求本科大{_GRADE_LABELS[required_grade]}{'及以上' if grade_requirement['minimum'] else '及以下' if grade_requirement['maximum'] else ''}"
        )
        return _constraint("毕业年份", status, description, grade_requirement["evidence"])
    preferred = "优先" in evidence
    if profile.graduation_year in years or (re.search(r"及以后|以后毕业", evidence) and profile.graduation_year >= min(years)):
        status = "符合"
    elif preferred:
        status = "加分项不满足"
    else:
        status = "不符合"
    return _constraint("毕业年份", status, f"个人为{profile.graduation_year}届", evidence)


def _constraint(name: str, status: str, conclusion: str, evidence: str) -> dict:
    return {"约束": name, "结论": status, "说明": conclusion, "证据": evidence or "未发现明确证据"}


def classify_role(title: str, body: str) -> tuple[str, str, bool]:
    text = f"{title}\n{body}"
    boundary = False
    ai_context = bool(re.search(r"AI|人工智能|大模型|LLM|Agent|智能体|RAG|Prompt|知识库", text, re.I))
    if re.search(r"评测|数据标注|AI训练师|效果评价|Bad\s*Case|测试集|模型效果", text, re.I):
        family, direction = "大模型评测、训练与数据质量", "模型评测与数据质量"
        boundary = bool(re.search(r"产品助理|产品经理|运营", title))
    elif re.search(r"AI工具|知识库|Prompt模板|工作流自动化", text, re.I) or (ai_context and re.search(r"增长运营", text)):
        family, direction = "AI运营、知识库与增长运营", "AI工具与知识库运营"
    elif ai_context and re.search(r"产品经理|产品助理|Agent产品|AI产品", title, re.I):
        family, direction = "AI产品与Agent产品", "AI产品与Agent交付"
    elif re.search(r"数据分析|数据科学|商业分析|经营分析|数据运营|数据开发|大数据", title):
        family, direction = "数据分析与商业/经营分析", "数据分析与数据治理"
    elif re.search(r"投行|投研|券商|证券|基金|资产管理|银行|风控|风险管理|信用分析|量化|金融", title):
        family = "金融、投研与风险管理"
        direction = "投研与资产管理" if re.search(r"投研|行研|证券|基金|资产管理", text) else "金融业务与风险管理"
    elif re.search(r"财务|会计|审计|税务|税务|财务分析|FP&A", title, re.I):
        family, direction = "财务、审计与税务", "财务与审税"
    elif re.search(r"咨询|行研|行业研究|研究报告|产业研究|战略分析|战略规划|政策研究|商业研究", text):
        family, direction = "咨询、行业研究与战略分析", "咨询与行业战略研究"
    elif re.search(r"市场|品牌|新媒体|内容运营|用户运营|活动运营|商业化运营|电商运营|社群运营", title):
        family, direction = "市场、品牌与商业运营", "市场与用户运营"
    elif re.search(r"人力资源|人事|HRBP|招聘|人才|组织发展|薪酬|培训运营", title, re.I):
        family, direction = "人力资源与组织发展", "招聘与人力资源运营"
    elif re.search(r"供应链|采购|物流|仓储|履约|计划专员", title):
        family, direction = "供应链、采购与物流", "供应链与采购管理"
    elif re.search(r"销售|商务|BD|Business\s*Development|客户成功|客户经理|渠道", title, re.I):
        family, direction = "销售、商务与客户成功", "商务拓展与客户运营"
    elif re.search(r"产品经理|产品助理|项目管理|项目助理|PMO", title, re.I):
        family, direction = "产品与项目管理", "通用产品与项目交付"
    elif re.search(r"运营", title):
        family, direction = "市场、品牌与商业运营", "综合运营"
    else:
        family, direction, boundary = "职能支持/其他岗位", "其他或待人工确认", True
    return family, direction, boundary


def extract_skills(text: str) -> list[str]:
    normalized = text.lower().replace(" ", "")
    return [term for term in SKILL_TERMS if term.lower().replace(" ", "") in normalized]


def extract_deliverables(jd_text: str) -> list[str]:
    sentences = [compact(item) for item in re.split(r"[。；\n]|(?=\d+[.、])", jd_text) if len(compact(item)) >= 12]
    action_terms = ["负责", "参与", "搭建", "建设", "分析", "设计", "输出", "推动", "优化", "制定", "维护", "跟踪", "沉淀", "构建"]
    output_terms = ["报告", "方案", "产品", "原型", "指标", "看板", "测试集", "知识库", "工作流", "策略", "数据", "模型", "文档", "结论", "建议"]
    scored = []
    for index, sentence in enumerate(sentences):
        score = sum(term in sentence for term in action_terms) * 2 + sum(term in sentence for term in output_terms)
        if score:
            scored.append((score, -index, sentence[:150]))
    scored.sort(reverse=True)
    result = []
    for _, _, sentence in scored:
        if sentence not in result:
            result.append(sentence)
        if len(result) == 4:
            break
    return result


def find_similar_cases(jd_text: str, cases: list[dict], limit: int = 3) -> list[dict]:
    signal_terms = SKILL_TERMS + ["评测", "产品", "运营", "数据", "研究", "招聘", "知识库", "工作流", "客服", "语音", "对话", "增长", "经营", "用户", "算法", "开发"]
    query_terms = {term for term in signal_terms if term.lower() in jd_text.lower()}
    ranked = []
    for case in cases:
        case_text = f"{case.get('role_title', '')}\n{case.get('jd_raw', '')}"
        case_terms = {term for term in signal_terms if term.lower() in case_text.lower()}
        union = query_terms | case_terms
        overlap = len(query_terms & case_terms) / len(union) if union else 0
        title_bonus = 0.12 if any(term in case.get("role_title", "") for term in query_terms) else 0
        score = min(1.0, overlap + title_bonus)
        gold = case.get("gold", {})
        ranked.append({
            "相似度": round(score * 100),
            "公司": case.get("company", ""),
            "岗位": case.get("role_title", ""),
            "人工分类": gold.get("role_family", ""),
            "时间结论": gold.get("constraint_result", ""),
            "判断依据": gold.get("role_basis", ""),
        })
    return sorted(ranked, key=lambda item: item["相似度"], reverse=True)[:limit]


def analyze_jd(jd_text: str, profile: CandidateProfile, resume_text: str = "") -> dict:
    identity = extract_identity(jd_text)
    family, direction, boundary = classify_role(identity["role_title"], jd_text)
    schedule = extract_schedule(jd_text, profile)
    constraints = [
        _constraint("每周出勤", schedule["day_status"], f"个人最多{profile.available_days}天/周；岗位识别值为{schedule['weekly_days'] or '未提及'}", schedule["evidence"]),
        _constraint("实习周期", schedule["month_status"], f"个人可实习{profile.min_months}-{profile.max_months}个月；岗位识别值为{schedule['minimum_months'] or '未提及'}", schedule["evidence"]),
        analyze_school(jd_text, profile),
        analyze_major(jd_text, profile),
        analyze_graduation(jd_text, profile),
    ]
    blockers = [row for row in constraints if row["结论"] == "不符合"]
    verifications = [row for row in constraints if row["结论"] == "需核实"]
    decision = "不建议投递" if blockers else "投递前需确认" if verifications else "可以投递"

    jd_skills = extract_skills(jd_text)
    profile_text = f"{profile.skills}\n{resume_text}"
    owned_skills = extract_skills(profile_text)
    matched = [skill for skill in jd_skills if skill in owned_skills]
    missing = [skill for skill in jd_skills if skill not in owned_skills]
    skill_score = round(100 * len(matched) / len(jd_skills)) if jd_skills else None
    base_score = 70 if not resume_text else 60 + round((skill_score or 0) * 0.4)
    if blockers:
        fit_score = min(base_score, 45)
    elif verifications:
        fit_score = min(base_score, 68)
    else:
        fit_score = min(base_score + 12, 95)
    risks = [row["说明"] for row in blockers + verifications]
    if missing:
        risks.append(f"简历中暂未识别：{'、'.join(missing[:6])}")
    strengths = matched[:8]
    if not strengths:
        strengths = ["尚未上传简历，当前只完成硬约束判断"]
    next_actions = []
    if blockers:
        next_actions.append("先确认硬约束是否存在例外，再决定是否投入定制简历时间。")
    elif verifications:
        next_actions.append("向招聘方核实含糊条件，尤其是每周天数、周期或专业范围。")
    else:
        next_actions.append("可以进入定制简历阶段，优先强化与岗位交付物直接相关的经历。")
    if missing:
        next_actions.append("只补充真实具备但未写出的技能；不为迎合 JD 虚构经历。")
    next_actions.append("用下方提示词生成一版定制简历，再逐条核验事实和量化结果。")

    return {
        **identity,
        "role_family": family,
        "sub_direction": direction,
        "boundary": boundary,
        "decision": decision,
        "fit_score": fit_score,
        "constraints": constraints,
        "schedule": schedule,
        "jd_skills": jd_skills,
        "deliverables": extract_deliverables(jd_text),
        "matched_skills": matched,
        "missing_skills": missing,
        "skill_score": skill_score,
        "strengths": strengths,
        "risks": risks,
        "next_actions": next_actions,
    }


def build_resume_prompt(jd_text: str, profile: CandidateProfile, resume_text: str, analysis: dict) -> str:
    resume_section = resume_text.strip() or "（尚未上传简历。请先提示我补充简历，不要凭空生成经历。）"
    constraints = "\n".join(f"- {row['约束']}：{row['结论']}；{row['说明']}；证据：{row['证据']}" for row in analysis["constraints"])
    return f"""你是一名严谨的中文求职简历顾问。请针对下面这份 JD 修改我的简历。

重要规则：
1. 绝不虚构项目、实习、技能、指标、奖项或学校背景。
2. 只能重组、压缩、改写我已经提供的事实；信息不足时明确写“需要本人补充”。
3. 先判断硬约束。若学校、专业、毕业年份、出勤或周期明确不符合，先指出，不要用措辞掩盖。
4. 经历描述采用“动作 + 对象/方法 + 结果/交付物”，但没有真实数字时不得编造数字。
5. 优先保留与岗位核心交付物直接相关的内容，删除泛泛自评。

我的基本信息：
- 学校：{profile.school}（{profile.school_tier}）
- 专业：{profile.major}，{profile.degree}，{profile.graduation_year}届
- 时间：{profile.arrival}，每周最多{profile.available_days}天，可连续{profile.min_months}-{profile.max_months}个月
- 已知技能：{profile.skills}

系统初步诊断：
- 投递结论：{analysis['decision']}
- 岗位大类：{analysis['role_family']} / {analysis['sub_direction']}
- 已匹配技能：{'、'.join(analysis['matched_skills']) or '待从简历确认'}
- 暂未识别技能：{'、'.join(analysis['missing_skills']) or '无明确缺口'}
{constraints}

请按以下结构输出：
A. 是否值得定制投递（3-5句，明确硬约束）
B. JD核心交付物与关键词（按重要性排序）
C. 简历应保留、前移、弱化或删除的内容
D. 对现有简历逐段改写，使用可直接替换的中文表述
E. 缺失但不能虚构的信息清单，以及我应该如何补充证据
F. 100字以内的投递邮件/打招呼文案

【目标 JD】
{jd_text.strip()}

【我的原始简历】
{resume_section}
"""
