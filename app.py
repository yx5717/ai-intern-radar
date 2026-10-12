import html
import json
import os
import re
from datetime import datetime
from hashlib import sha256
from pathlib import Path

import pandas as pd
import streamlit as st

from llm_client import PROVIDERS, chat_completion, normalize_provider_config, test_connection
from radar_core import (
    CandidateProfile,
    ROLE_DESCRIPTIONS,
    ROLE_ORDER,
    analyze_jd,
    build_catalog_csv,
    build_report_markdown,
    build_resume_prompt,
    months_span,
)
from resume_parser import parse_resume
from storage import UserStore

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
ROLE_CHART_LABELS = {
    "AI产品与Agent产品": "AI产品/Agent",
    "大模型评测、训练与数据质量": "大模型评测/训练",
    "AI运营、知识库与增长运营": "AI运营/知识库",
    "数据分析与商业/经营分析": "数据/商业分析",
    "金融、投研与风险管理": "金融/投研/风控",
    "财务、审计与税务": "财务/审计/税务",
    "咨询、行业研究与战略分析": "咨询/行研/战略",
    "市场、品牌与商业运营": "市场/品牌/运营",
    "人力资源与组织发展": "人力资源/组织",
    "销售、商务与客户成功": "销售/商务/客成",
    "供应链、采购与物流": "供应链/采购/物流",
    "产品与项目管理": "产品/项目管理",
    "职能支持/其他岗位": "职能支持/其他",
}
STORE = UserStore(
    Path(os.getenv("AI_RADAR_DB_PATH", DATA / "ai_radar.db")),
    Path(os.getenv("AI_RADAR_KEY_PATH", DATA / ".storage_key")),
)


@st.cache_data
def load_jsonl(name: str) -> list[dict]:
    with (DATA / name).open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


@st.cache_data
def load_json(name: str) -> dict:
    with (DATA / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _h(value) -> str:
    """把用户填写的文本安全地放进自绘 HTML 片段。"""
    return html.escape(str(value if value is not None else ""))


def metric_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def page_header(title: str) -> None:
    """页面头。

    曾经在每个标题上方压一行英文上标签（DASHBOARD / PROFILE / PROJECT……），
    但侧栏已经标明了当前位置，那行字不承担任何信息，只是把页面做出「设计感」。
    这种「主标题 + 大写拉丁眉标」正是最典型的模板味，所以整个删掉。
    """
    st.title(title)


def render_barlist(pairs: list[tuple[str, int]], alt: bool = False) -> None:
    """自绘条形图：无坐标轴、无网格线，标签右对齐、数值等宽。"""
    if not pairs:
        return
    peak = max(value for _, value in pairs) or 1
    rows = "".join(
        f'<div class="row"><div class="k">{_h(label)}</div>'
        f'<div class="track"><div class="fill" style="width:{value / peak * 100:.1f}%"></div></div>'
        f'<div class="v">{value}</div></div>'
        for label, value in pairs
    )
    st.markdown(f'<div class="barlist{" alt" if alt else ""}">{rows}</div>', unsafe_allow_html=True)


_BATCH_SEPARATOR = re.compile(r"^[ \t]*(?:-{3,}|={3,}|\*{3,}|#{3,})[ \t]*$", re.MULTILINE)
MIN_JD_LENGTH = 30


def _split_batch_raw(text: str) -> list[str]:
    """只做切分与长度过滤，不去重。"""
    if _BATCH_SEPARATOR.search(text):
        parts = _BATCH_SEPARATOR.split(text)
    else:
        parts = re.split(r"\n[ \t]*\n[ \t]*\n+", text)
    return [part.strip() for part in parts if len(part.strip()) >= MIN_JD_LENGTH]


def split_batch_jds(text: str) -> list[str]:
    """把批量粘贴的文本切成多条 JD。

    优先按独占一行的分隔符（--- / === / *** / ###）切分；没有分隔符时退回到
    「连续 3 个以上空行」。两种都做长度过滤，避免把碎片当成岗位。

    最后按内容哈希去重：入库本身是按 JD 内容哈希去重的（见 save_user_job），
    如果这里不去重，按钮上写「3 条」而实际只落库 2 条，用户会以为出错。
    """
    seen, unique = set(), []
    for item in _split_batch_raw(text):
        digest = sha256(item.encode("utf-8")).hexdigest()
        if digest not in seen:
            seen.add(digest)
            unique.append(item)
    return unique


def dropped_duplicate_count(text: str) -> int:
    """本次粘贴里被合并掉的重复条数，用于如实告知用户。"""
    return len(_split_batch_raw(text)) - len(split_batch_jds(text))


def safe_filename(value: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", value).strip("_")[:80] or "report"


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, float) and pd.isna(value))


def fit_metric(value) -> str:
    return "—" if _is_blank(value) else f"{int(round(float(value)))} / 100"


def fit_cell(value):
    # 适配度列混入 "—" 后会被 pandas 提升为 float，直接展示会变成 72.0。
    return "—" if _is_blank(value) else int(round(float(value)))


def status_class(value: str) -> str:
    return "pass" if value in {"符合", "可以投递", "未限制"} else "fail" if value in {"不符合", "不建议投递"} else "verify"


def render_constraint(row: dict) -> None:
    st.markdown(
        f'<div class="constraint"><div><strong>{row["约束"]}</strong><span>{row["说明"]}</span></div>'
        f'<b class="{status_class(row["结论"])}">{row["结论"]}</b></div>', unsafe_allow_html=True,
    )
    if row["证据"] != "未发现明确证据":
        st.caption(f"证据：{row['证据']}")


PROFILE_DEFAULTS = {
    "profile_school": "", "profile_school_tier": "未填写", "profile_major": "",
    "profile_degree": "未填写", "profile_graduation_year": "未填写", "profile_available_days": "未填写",
    "profile_min_months": "未填写", "profile_max_months": "未填写", "profile_skills": "",
    "resume_text": "", "resume_name": "", "user_jobs": [],
    "api_provider": "DeepSeek", "api_base_url": PROVIDERS["DeepSeek"]["base_url"], "api_model": PROVIDERS["DeepSeek"]["model"], "api_key": os.getenv("AI_RADAR_API_KEY", ""),
    "api_config_status": "saved" if os.getenv("AI_RADAR_API_KEY", "") else "unconfigured",
    "api_status_message": "环境变量中的 API Key 已载入，尚未测试连接。" if os.getenv("AI_RADAR_API_KEY", "") else "",
    "api_tested_at": "",
}


for state_key, default_value in PROFILE_DEFAULTS.items():
    if state_key not in st.session_state:
        st.session_state[state_key] = default_value

(
    st.session_state.api_provider,
    st.session_state.api_base_url,
    st.session_state.api_model,
) = normalize_provider_config(
    st.session_state.api_provider,
    st.session_state.api_base_url,
    st.session_state.api_model,
)

for draft_key, saved_key in {
    "api_provider_draft": "api_provider", "api_base_url_draft": "api_base_url",
    "api_model_draft": "api_model", "api_key_draft": "api_key",
}.items():
    if draft_key not in st.session_state:
        st.session_state[draft_key] = st.session_state[saved_key]

(
    st.session_state.api_provider_draft,
    st.session_state.api_base_url_draft,
    st.session_state.api_model_draft,
) = normalize_provider_config(
    st.session_state.api_provider_draft,
    st.session_state.api_base_url_draft,
    st.session_state.api_model_draft,
)


ACCOUNT_STATE_KEYS = [
    "profile_school", "profile_school_tier", "profile_major", "profile_degree",
    "profile_graduation_year", "profile_available_days", "profile_min_months", "profile_max_months", "profile_skills",
    "resume_text", "resume_name", "api_provider", "api_base_url", "api_model", "api_key",
    "api_config_status", "api_status_message", "api_tested_at",
]
PROFILE_WIDGET_KEYS = {
    "profile_school": "profile_school_input",
    "profile_school_tier": "profile_school_tier_input",
    "profile_major": "profile_major_input",
    "profile_degree": "profile_degree_input",
    "profile_graduation_year": "profile_graduation_year_input",
    "profile_available_days": "profile_available_days_input",
    "profile_min_months": "profile_min_months_input",
    "profile_max_months": "profile_max_months_input",
    "profile_skills": "profile_skills_input",
}


def account_state_payload() -> dict:
    return {key: st.session_state.get(key, PROFILE_DEFAULTS.get(key, "")) for key in ACCOUNT_STATE_KEYS}


def account_state_signature(payload: dict) -> str:
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def load_account_state(user_id: int) -> None:
    saved_state = STORE.load_state(user_id)
    for key, default_value in PROFILE_DEFAULTS.items():
        if key != "user_jobs":
            st.session_state[key] = saved_state.get(key, default_value)
    (
        st.session_state.api_provider,
        st.session_state.api_base_url,
        st.session_state.api_model,
    ) = normalize_provider_config(
        st.session_state.api_provider,
        st.session_state.api_base_url,
        st.session_state.api_model,
    )
    st.session_state.user_jobs = STORE.list_jobs(user_id)
    for widget_key in PROFILE_WIDGET_KEYS.values():
        st.session_state.pop(widget_key, None)
    for draft_key, saved_key in {
        "api_provider_draft": "api_provider", "api_base_url_draft": "api_base_url",
        "api_model_draft": "api_model", "api_key_draft": "api_key",
    }.items():
        st.session_state[draft_key] = st.session_state[saved_key]
    st.session_state._account_loaded_for = user_id
    st.session_state._persisted_state_signature = account_state_signature(account_state_payload())


def prepare_profile_widgets() -> None:
    if st.session_state.pop("_reset_profile_widgets", False):
        for widget_key in PROFILE_WIDGET_KEYS.values():
            st.session_state.pop(widget_key, None)
    for state_key, widget_key in PROFILE_WIDGET_KEYS.items():
        if widget_key not in st.session_state:
            st.session_state[widget_key] = st.session_state[state_key]


def sync_profile_field(state_key: str) -> None:
    st.session_state[state_key] = st.session_state[PROFILE_WIDGET_KEYS[state_key]]


def apply_resume_snapshot(snapshot) -> list[str]:
    updated = []
    field_values = {
        "profile_school": snapshot.school,
        "profile_major": snapshot.major,
        "profile_degree": snapshot.degree,
        "profile_graduation_year": snapshot.graduation_year,
        "profile_skills": "、".join(snapshot.skills or []),
    }
    labels = {
        "profile_school": "学校", "profile_major": "专业", "profile_degree": "学历",
        "profile_graduation_year": "毕业年份", "profile_skills": "技能",
    }
    for state_key, value in field_values.items():
        if value not in {None, ""}:
            st.session_state[state_key] = value
            updated.append(labels[state_key])
    st.session_state._reset_profile_widgets = True
    return updated


def persist_account_state(force: bool = False) -> None:
    user_id = st.session_state.get("auth_user_id")
    if not user_id:
        return
    payload = account_state_payload()
    signature = account_state_signature(payload)
    if force or signature != st.session_state.get("_persisted_state_signature"):
        STORE.save_state(int(user_id), payload)
        st.session_state._persisted_state_signature = signature


def sign_out() -> None:
    persist_account_state(force=True)
    for key in list(st.session_state):
        del st.session_state[key]
    st.rerun()


def start_guest_session() -> None:
    for key in list(st.session_state):
        del st.session_state[key]
    for state_key, default_value in PROFILE_DEFAULTS.items():
        st.session_state[state_key] = list(default_value) if isinstance(default_value, list) else default_value
    for draft_key, saved_key in {
        "api_provider_draft": "api_provider", "api_base_url_draft": "api_base_url",
        "api_model_draft": "api_model", "api_key_draft": "api_key",
    }.items():
        st.session_state[draft_key] = st.session_state[saved_key]
    st.session_state.auth_mode = "guest"
    st.session_state.auth_user_id = None
    st.session_state.auth_username = "游客"
    st.session_state._account_loaded_for = "guest"
    st.rerun()


def apply_provider_defaults() -> None:
    provider = st.session_state.api_provider_draft
    st.session_state.api_base_url_draft = PROVIDERS[provider]["base_url"]
    st.session_state.api_model_draft = PROVIDERS[provider]["model"]


def clear_api_config() -> None:
    provider = st.session_state.api_provider_draft
    st.session_state.api_provider = provider
    st.session_state.api_base_url = PROVIDERS[provider]["base_url"]
    st.session_state.api_model = PROVIDERS[provider]["model"]
    st.session_state.api_key = ""
    st.session_state.api_base_url_draft = PROVIDERS[provider]["base_url"]
    st.session_state.api_model_draft = PROVIDERS[provider]["model"]
    st.session_state.api_key_draft = ""
    st.session_state.api_config_status = "unconfigured"
    st.session_state.api_status_message = "配置已清除。"
    st.session_state.api_tested_at = ""


def api_status_label() -> str:
    labels = {
        "connected": f"连接成功：{st.session_state.api_model}",
        "saved": "API 已保存，等待测试",
        "failed": "API 连接失败",
        "unconfigured": "尚未配置 API",
    }
    return labels.get(st.session_state.api_config_status, "尚未配置 API")


def key_fingerprint(api_key: str) -> str:
    clean_key = api_key.strip()
    if not clean_key:
        return ""
    return f"{clean_key[:3]}****{clean_key[-4:]}" if len(clean_key) >= 8 else "****"


def current_profile() -> CandidateProfile:
    graduation_year = st.session_state.profile_graduation_year
    available_days = st.session_state.profile_available_days
    min_months = st.session_state.profile_min_months
    max_months = st.session_state.profile_max_months
    return CandidateProfile(
        school=st.session_state.profile_school, school_tier=st.session_state.profile_school_tier,
        major=st.session_state.profile_major, degree=st.session_state.profile_degree,
        graduation_year=int(graduation_year) if graduation_year != "未填写" else None,
        available_days=int(available_days) if available_days != "未填写" else None,
        min_months=int(min_months) if min_months != "未填写" else None,
        max_months=int(max_months) if max_months != "未填写" else None,
        skills=st.session_state.profile_skills,
    )


def profile_is_complete() -> bool:
    required_values = [
        st.session_state.profile_school, st.session_state.profile_school_tier,
        st.session_state.profile_major, st.session_state.profile_degree,
        st.session_state.profile_graduation_year, st.session_state.profile_available_days,
        st.session_state.profile_max_months,
    ]
    return all(value not in {None, "", "未填写"} for value in required_values)


def constraint_value(analysis: dict, name: str) -> str:
    return next(row["结论"] for row in analysis["constraints"] if row["约束"] == name)


CATALOG_COLUMNS = [
    "记录ID", "公司", "岗位名称", "岗位大类", "综合结论", "适配度",
    "出勤", "周期", "学校", "专业", "毕业年份", "保存时间",
]


def build_catalog(profile: CandidateProfile, resume_text: str, user_jobs: list[dict]) -> tuple[pd.DataFrame, dict]:
    rows = []
    details = {}
    for record in user_jobs:
        analysis = analyze_jd(record["jd_raw"], profile, resume_text)
        details[record["record_id"]] = {**record, "analysis": analysis}
        rows.append({
            "记录ID": record["record_id"],
            "公司": analysis["company"], "岗位名称": analysis["role_title"], "岗位大类": analysis["role_family"],
            "综合结论": analysis["decision"], "适配度": analysis["fit_score"],
            "出勤": constraint_value(analysis, "每周出勤"), "周期": constraint_value(analysis, "实习周期"),
            "学校": constraint_value(analysis, "学校层次"), "专业": constraint_value(analysis, "专业"),
            "毕业年份": constraint_value(analysis, "毕业年份"), "保存时间": record.get("saved_at", ""),
        })
    return pd.DataFrame(rows, columns=CATALOG_COLUMNS), details


def save_user_job(jd_text: str, analysis: dict) -> str:
    record_id = f"USR-{sha256(jd_text.encode('utf-8')).hexdigest()[:8].upper()}"
    record = {
        "record_id": record_id, "platform": "用户粘贴", "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "jd_raw": jd_text, "snapshot": {"company": analysis["company"], "role_title": analysis["role_title"], "decision": analysis["decision"]},
    }
    existing = [item for item in st.session_state.user_jobs if item["record_id"] != record_id]
    st.session_state.user_jobs = [record, *existing]
    if st.session_state.get("auth_mode") == "account":
        STORE.upsert_job(int(st.session_state.auth_user_id), record)
    return record_id


def render_analysis_report(
    jd_text: str,
    analysis_profile: CandidateProfile,
    analysis: dict,
    analysis_resume: str,
    record_note: str,
    allow_api: bool = True,
) -> None:
    decision_class = status_class(analysis["decision"])
    st.markdown(
        f'<div class="decision {decision_class}"><div class="label">投递建议</div>'
        f'<div class="value {decision_class}">{_h(analysis["decision"])}</div>'
        f'<div class="meta">{_h(analysis["company"])} · {_h(analysis["role_title"])} · {_h(analysis["role_family"])}</div></div>',
        unsafe_allow_html=True,
    )
    m1, m2, m3, m4 = st.columns(4)
    schedule = analysis["schedule"]
    day_metric = schedule["weekly_days"] if schedule["weekly_days"] is not None else ("待核实" if schedule["day_status"] == "需核实" else "未提及")
    month_metric = schedule["minimum_months"] if schedule["minimum_months"] is not None else ("待核实" if schedule["month_status"] == "需核实" else "未提及")
    m1.metric("综合适配度", fit_metric(analysis["fit_score"]))
    m2.metric("每周要求", day_metric)
    m3.metric("最低周期", month_metric)
    m4.metric("识别技能", len(analysis["jd_skills"]))
    if analysis.get("fit_breakdown"):
        st.caption("适配度构成：" + " · ".join(f"{name} {item['得分']} 分（权重 {item['权重']}%）" for name, item in analysis["fit_breakdown"].items()))
    elif analysis.get("fit_note"):
        st.caption(analysis["fit_note"])
    if analysis.get("bad_case_type") and analysis["bad_case_type"] != "无":
        bad_case_detail = analysis.get("bad_case_evidence") or "岗位归类处于边界，建议人工复核后再决定投递方向。"
        st.warning(f"需要留意：{analysis['bad_case_type']}。{bad_case_detail}")
    st.caption(record_note)
    hard, fit = st.columns([1, 1])
    with hard:
        st.subheader("硬约束")
        for constraint in analysis["constraints"]:
            render_constraint(constraint)
    with fit:
        st.subheader("能力与经历")
        st.write("**已匹配**")
        # 简历已上传却一条都没匹配上时，再提示「上传简历后才能匹配」就是误导。
        if analysis["matched_skills"]:
            st.write("、".join(analysis["matched_skills"]))
        elif analysis_resume.strip():
            st.write("这份简历里没有识别到与 JD 明确对应的技能，建议人工比对职责段落")
        else:
            st.write("上传简历后才能进行可靠匹配")
        st.write("**JD要求但简历中暂未识别**")
        st.write("、".join(analysis["missing_skills"]) or "没有识别到明确技能缺口")
        st.write("**主要风险**")
        for risk in analysis["risks"] or ["暂未识别明显风险"]:
            st.write(f"- {risk}")
    st.subheader("核心交付物")
    for item in analysis["deliverables"] or ["未能从 JD 中提取明确交付物，建议人工复核职责段落。"]:
        st.write(f"- {item}")
    st.subheader("建议动作")
    for index, action in enumerate(analysis["next_actions"], 1):
        st.write(f"{index}. {action}")
    prompt = build_resume_prompt(jd_text, analysis_profile, analysis_resume, analysis)
    st.subheader("简历修改提示词")
    st.caption("可直接复制；已包含硬约束、JD、个人画像和防止虚构的要求。")
    st.code(prompt, language="text", line_numbers=False)
    export_col, _ = st.columns([1, 2])
    export_col.download_button(
        "导出这份诊断报告",
        data=build_report_markdown(analysis, jd_text, analysis_profile),
        file_name=f"诊断报告_{safe_filename(analysis['company'])}_{safe_filename(analysis['role_title'])}.md",
        mime="text/markdown",
        width="stretch",
        help="导出为 Markdown，包含硬约束、能力匹配、交付物、建议动作与 JD 原文。",
    )
    if not allow_api:
        return
    with st.expander("使用我的 API 生成深度建议"):
        api_ready = st.session_state.api_config_status == "connected"
        if api_ready:
            st.success(f"模型可以调用：{st.session_state.api_provider} / {st.session_state.api_model}")
        elif st.session_state.api_config_status == "saved":
            st.warning("API 已保存但尚未测试，请先到“我的资料”点击“保存并测试连接”。")
        elif st.session_state.api_config_status == "failed":
            st.error(f"API 连接失败：{st.session_state.api_status_message}")
        else:
            st.warning("尚未配置 API，请先到“我的资料”粘贴 Key 并测试连接。")
        st.caption("请求会把当前 JD 和简历文本发送给你选择的模型服务商。")
        if st.button("生成深度分析与改写", width="content", disabled=not api_ready):
            try:
                with st.spinner("正在分析岗位与简历……"):
                    st.session_state["llm_result"] = chat_completion(st.session_state.api_key, st.session_state.api_base_url, st.session_state.api_model, prompt)
            except Exception as error:
                st.error(str(error))
        if st.session_state.get("llm_result"):
            st.markdown(st.session_state["llm_result"])


st.set_page_config(page_title="AI 实习雷达", page_icon="◎", layout="wide", initial_sidebar_state="auto")
THEME_CSS = (ROOT / "theme.css").read_text(encoding="utf-8")
st.markdown(f"<style>{THEME_CSS}</style>", unsafe_allow_html=True)

if st.session_state.get("auth_user_id") and not st.session_state.get("auth_mode"):
    st.session_state.auth_mode = "account"

if os.getenv("AI_RADAR_TEST_BYPASS_AUTH") == "1" and not st.session_state.get("auth_mode"):
    test_user = STORE.ensure_test_user()
    st.session_state.auth_mode = "account"
    st.session_state.auth_user_id = test_user["id"]
    st.session_state.auth_username = test_user["username"]

if not st.session_state.get("auth_mode"):
    st.title("AI 实习雷达")
    st.markdown('<div class="caption">登录后，你的求职画像、简历、API 配置和岗位记录会自动恢复。</div>', unsafe_allow_html=True)
    if st.button("游客体验", width="stretch"):
        start_guest_session()
    st.caption("从空白资料开始，退出后清除本次数据。")
    login_tab, register_tab = st.tabs(["登录", "注册"])
    with login_tab:
        with st.form("login_form"):
            login_username = st.text_input("用户名", key="login_username")
            login_password = st.text_input("密码", type="password", key="login_password")
            login_submitted = st.form_submit_button("登录", type="primary", width="stretch")
        if login_submitted:
            user = STORE.authenticate(login_username, login_password)
            if user is None:
                st.error("用户名或密码不正确。")
            else:
                st.session_state.auth_mode = "account"
                st.session_state.auth_user_id = user["id"]
                st.session_state.auth_username = user["username"]
                load_account_state(user["id"])
                st.rerun()
    with register_tab:
        with st.form("register_form"):
            register_username = st.text_input("设置用户名", key="register_username")
            register_password = st.text_input("设置密码", type="password", key="register_password")
            register_confirmation = st.text_input("确认密码", type="password", key="register_confirmation")
            register_submitted = st.form_submit_button("创建账户", type="primary", width="stretch")
        if register_submitted:
            if register_password != register_confirmation:
                st.error("两次输入的密码不一致。")
            else:
                try:
                    user = STORE.register_user(register_username, register_password)
                    st.session_state.auth_mode = "account"
                    st.session_state.auth_user_id = user["id"]
                    st.session_state.auth_username = user["username"]
                    load_account_state(user["id"])
                    persist_account_state(force=True)
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
    st.stop()

if st.session_state.auth_mode == "account" and st.session_state.get("_account_loaded_for") != st.session_state.auth_user_id:
    load_account_state(int(st.session_state.auth_user_id))

report = load_json("external_eval_v1.json")
engine_report = load_json("python_engine_eval_v1.json") if (DATA / "python_engine_eval_v1.json").exists() else None

with st.sidebar:
    st.markdown('<div class="brand"><span class="dot"></span>AI 实习雷达</div>', unsafe_allow_html=True)
    st.caption("先判断能不能投，再决定怎么投")
    nav_options = ["求职首页", "我的资料", "智能诊断", "岗位库", "更多"]
    page = st.radio("导航", nav_options, label_visibility="collapsed", key="nav_page")
    st.divider()
    st.caption("我的求职画像")
    graduation_display = f"{st.session_state.profile_graduation_year} 届" if st.session_state.profile_graduation_year != "未填写" else "未填写"
    max_months_value = st.session_state.profile_max_months
    min_months_value = st.session_state.profile_min_months
    if max_months_value == "未填写":
        months_display = "未填写"
    elif min_months_value == "未填写":
        months_display = f"最长 {max_months_value} 个月"
    else:
        months_display = f"{min_months_value}-{max_months_value} 个月"
    days_display = f"{st.session_state.profile_available_days} 天/周" if st.session_state.profile_available_days != "未填写" else "未填写"
    st.markdown(
        f'<div class="kv"><span class="k">学校</span><span class="v">{_h(st.session_state.profile_school or "未填写")}</span></div>'
        f'<div class="kv"><span class="k">专业</span><span class="v">{_h(st.session_state.profile_major or "未填写")}</span></div>'
        f'<div class="kv"><span class="k">毕业</span><span class="v">{_h(graduation_display)}</span></div>'
        f'<div class="kv"><span class="k">出勤</span><span class="v">{_h(days_display)}</span></div>'
        f'<div class="kv"><span class="k">周期</span><span class="v">{_h(months_display)}</span></div>'
        f'<div class="kv"><span class="k">简历</span><span class="v">{_h(st.session_state.resume_name or "未上传")}</span></div>',
        unsafe_allow_html=True,
    )
    st.divider()
    account_label = f"账户：{st.session_state.auth_username}" if st.session_state.auth_mode == "account" else "游客模式 · 数据不会保存"
    st.caption(account_label)
    if st.button("退出登录", key="logout_button"):
        sign_out()
    sidebar_api_status = st.empty()

profile = current_profile()
profile_ready = profile_is_complete()
catalog_df, catalog_details = build_catalog(profile, st.session_state.resume_text, st.session_state.user_jobs) if profile_ready else (pd.DataFrame(columns=CATALOG_COLUMNS), {})

if page == "求职首页":
    page_header("今天先投什么")
    if profile_ready:
        st.markdown(
            f'<div class="caption">{profile.school} · {profile.major} · {profile.graduation_year} 届 · '
            f'每周最多 {profile.available_days} 天 · 可实习 {months_span(profile)}<br>'
            f'下面每条结论都同时检查出勤、周期、学校层次、专业和毕业年份。</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div class="caption">完成求职画像后，这里会按你的真实条件生成投递优先级。</div>', unsafe_allow_html=True)
    suitable = catalog_df[catalog_df["综合结论"] == "可以投递"]
    verify = catalog_df[catalog_df["综合结论"] == "投递前需确认"]
    blocked = catalog_df[catalog_df["综合结论"] == "不建议投递"]
    cols = st.columns(4)
    cols[0].metric("可直接投递", len(suitable), "先做定制简历")
    cols[1].metric("联系后再投", len(verify), "核实模糊约束")
    cols[2].metric("暂不建议", len(blocked), "存在硬门槛")
    diagnosis_note = "已保存到账户" if st.session_state.auth_mode == "account" else "仅本次访问"
    cols[3].metric("已存岗位", len(st.session_state.user_jobs), diagnosis_note)
    if not profile_ready:
        next_step = "先到“我的资料”填写学校、专业、学历、毕业年份和实习时间，再上传简历。大模型 API 可以稍后按需配置。"
    elif st.session_state.resume_text:
        next_step = "个人资料已就绪。打开“智能诊断”粘贴 JD；如需网页直接生成深度分析，可再配置大模型 API。"
    else:
        next_step = "先到“我的资料”完善求职画像并上传简历。大模型 API 是可选项，不配置也可以完成岗位诊断。"
    st.markdown(f'<div class="tagline"><strong>下一步</strong><span>{next_step}</span></div>', unsafe_allow_html=True)
    st.subheader("优先处理")
    if suitable.empty:
        st.markdown(
            '<div class="empty"><div class="t">还没有可直接投递的岗位</div>'
            '<div class="d">到「智能诊断」粘贴一条 JD，或用「批量导入」一次投喂多条，结果会自动进入这里。</div></div>',
            unsafe_allow_html=True,
        )
    else:
        priority = suitable.sort_values("适配度", ascending=False).head(12).copy()
        priority["适配度"] = priority["适配度"].map(fit_cell)
        # 首页是短名单，只保留决策必需的 4 列；完整约束在“岗位库”里看。
        st.dataframe(
            priority[["公司", "岗位名称", "岗位大类", "适配度"]], width="stretch", hide_index=True,
            height=min(415, 58 + 35 * len(priority)),
            column_config={
                # 宽度之和要贴近容器实际宽度（约 962px）：总和远小于容器时，
                # Streamlit 会把多出来的空间摊给最后一列，适配度列会空出一大片。
                "公司": st.column_config.TextColumn(width=132),
                "岗位名称": st.column_config.TextColumn(width=470),
                "岗位大类": st.column_config.TextColumn(width=250),
                "适配度": st.column_config.TextColumn(width=110),
            },
        )
    # 方向分布统计的是整个岗位库，不是只看「可以投递」那几条：
    # 只统计 2 条时两根等长的条会退化成一条分隔线，反而看不出信息。
    st.subheader("方向分布")
    active_roles = []
    if not catalog_df.empty:
        role_counts = catalog_df["岗位大类"].value_counts().reindex(ROLE_ORDER, fill_value=0)
        active_roles = [
            (ROLE_CHART_LABELS[role], int(count))
            for role, count in role_counts.items() if count > 0
        ]
    if active_roles:
        render_barlist(active_roles)
        st.caption(f"岗位库共 {len(catalog_df)} 条，按岗位大类分布")
    else:
        st.markdown(
            '<div class="empty"><div class="t">暂无可统计的岗位</div>'
            '<div class="d">完成一次诊断后，这里会显示你的方向分布。</div></div>',
            unsafe_allow_html=True,
        )
    st.subheader("判断顺序")
    st.markdown(
        '<div class="flow">'
        '<div class="step"><div class="n">1</div><div class="t">能不能投</div>'
        '<div class="d">时间、学校、专业、毕业年份等硬门槛</div></div>'
        '<div class="step"><div class="n">2</div><div class="t">值不值得投</div>'
        '<div class="d">职责、技能、经历证据与主要风险</div></div>'
        '<div class="step"><div class="n">3</div><div class="t">怎么投</div>'
        '<div class="d">定制简历、修改提示词与招呼文案</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )

elif page == "我的资料":
    page_header("我的资料")
    st.markdown('<div class="caption">求职画像、个人简历和大模型接口统一在这里管理</div>', unsafe_allow_html=True)
    prepare_profile_widgets()
    p1, p2 = st.columns([1, 1])
    with p1:
        st.subheader("求职画像")
        st.text_input("学校", key="profile_school_input", on_change=sync_profile_field, args=("profile_school",))
        st.selectbox("学校层次", ["未填写", "非985/211", "双一流", "211", "985"], key="profile_school_tier_input", on_change=sync_profile_field, args=("profile_school_tier",))
        st.text_input("专业", key="profile_major_input", on_change=sync_profile_field, args=("profile_major",))
        c1, c2 = st.columns(2)
        c1.selectbox("学历", ["未填写", "本科", "硕士", "博士", "大专"], key="profile_degree_input", on_change=sync_profile_field, args=("profile_degree",))
        c2.selectbox("毕业年份", ["未填写", *range(2025, 2036)], key="profile_graduation_year_input", on_change=sync_profile_field, args=("profile_graduation_year",))
        c3, c4, c5 = st.columns(3)
        c3.selectbox("每周最多出勤", ["未填写", *range(1, 8)], key="profile_available_days_input", on_change=sync_profile_field, args=("profile_available_days",))
        c4.selectbox("最短可实习月数", ["未填写", *range(1, 13)], key="profile_min_months_input", on_change=sync_profile_field, args=("profile_min_months",))
        c5.selectbox("最长实习月数", ["未填写", *range(1, 13)], key="profile_max_months_input", on_change=sync_profile_field, args=("profile_max_months",))
        st.text_area("已掌握技能", key="profile_skills_input", height=130, on_change=sync_profile_field, args=("profile_skills",))
    with p2:
        st.subheader("个人简历")
        resume_privacy = (
            "简历仅用于提取求职画像、匹配 JD 和生成改写建议。原文件不会保存；解析后的文本按账户隔离保存，不会进入岗位记录或诊断记录导出文件。"
            if st.session_state.auth_mode == "account"
            else "简历仅用于提取求职画像、匹配 JD 和生成改写建议。游客模式不保存原文件或解析文本，退出后即清除。"
        )
        st.caption(resume_privacy)
        st.info("上传简历后，系统会自动提取并回填学校、专业、学历、毕业年份和技能；不上传也可以在左侧手动填写。学校层次和实习时间需由本人确认。")
        resume_file = st.file_uploader("上传 DOCX、PDF 或 TXT", type=["docx", "pdf", "txt"], help="支持 DOCX、PDF 和纯文本简历；上传后自动生成可编辑的求职画像。")
        if resume_file:
            try:
                upload_id = sha256(resume_file.name.encode("utf-8") + resume_file.getvalue()).hexdigest()
                if st.session_state.get("_processed_resume_upload") != upload_id:
                    snapshot = parse_resume(resume_file)
                    st.session_state.resume_text = snapshot.text
                    st.session_state.resume_name = resume_file.name
                    updated_fields = apply_resume_snapshot(snapshot)
                    st.session_state._processed_resume_upload = upload_id
                    st.session_state.resume_parse_message = (
                        f"已自动回填：{'、'.join(updated_fields)}。" if updated_fields
                        else "已读取简历文本，但未稳定识别到画像字段，请手动补充。"
                    )
                    persist_account_state(force=True)
                    st.rerun()
                st.success(f"当前简历：{st.session_state.resume_name}")
                st.caption(st.session_state.get("resume_parse_message", "简历已解析并更新求职画像。"))
            except Exception as error:
                st.error(str(error))
        elif st.session_state.resume_text:
            st.success(f"当前简历：{st.session_state.resume_name}")
            if st.button("清除当前简历"):
                st.session_state.resume_text = ""; st.session_state.resume_name = ""
                persist_account_state(force=True)
                st.rerun()
        else:
            st.info("上传简历后，智能诊断会区分真实技能匹配与简历表达缺口。")
        st.subheader("大模型 API")
        api_privacy = (
            "API Key 仅用于向所选模型服务商发起请求，并加密保存到当前账户；不会写入岗位记录或导出文件。JD 和简历文本会发送给所选服务商处理。"
            if st.session_state.auth_mode == "account"
            else "API Key 仅用于向所选模型服务商发起请求，游客模式只保留在当前会话；退出后即清除。JD 和简历文本会发送给所选服务商处理。"
        )
        st.caption(api_privacy)
        st.markdown(
            '<div class="pair">'
            '<div class="card mut"><div class="t">不配置 API</div>'
            '<div class="d">硬约束判断、适配度分析、岗位库和简历修改提示词全部可用。</div></div>'
            '<div class="card ok"><div class="t">配置 API</div>'
            '<div class="d">在诊断结果中直接生成深度分析和简历改写，消耗你自己的模型额度。</div></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.caption("选择服务商后会自动填写官方地址和推荐模型；通常只需粘贴 API Key，若控制台指定了模型或接入点 ID，请按控制台信息修改模型。")
        st.selectbox("模型服务", list(PROVIDERS), key="api_provider_draft", on_change=apply_provider_defaults)
        custom_provider = st.session_state.api_provider_draft == "自定义"
        if not custom_provider and (not st.session_state.api_base_url_draft or not st.session_state.api_model_draft):
            apply_provider_defaults()
        with st.form("api_config_form"):
            st.text_input("Base URL", key="api_base_url_draft", disabled=not custom_provider, help="预设服务商会自动填写官方地址；自定义地址需支持 Bearer 密钥和 /chat/completions 对话路径。")
            st.text_input("模型", key="api_model_draft", help="已自动填写推荐模型。豆包等服务若要求推理接入点 ID，请替换为控制台提供的值。")
            st.text_input("API Key", type="password", key="api_key_draft", help="加密保存到当前账户，不写入岗位记录或导出文件。")
            save_col, test_col = st.columns(2)
            save_api = save_col.form_submit_button("保存配置", width="stretch")
            test_api = test_col.form_submit_button("保存并测试连接", type="primary", width="stretch")

        if save_api or test_api:
            draft_key = st.session_state.api_key_draft.strip()
            draft_url = st.session_state.api_base_url_draft.strip()
            draft_model = st.session_state.api_model_draft.strip()
            if not draft_key:
                st.session_state.api_config_status = "unconfigured"
                st.session_state.api_status_message = "请先粘贴 API Key。"
            elif not draft_url or not draft_model:
                st.session_state.api_config_status = "failed"
                st.session_state.api_status_message = "Base URL 和模型名称不能为空。"
            else:
                st.session_state.api_provider = st.session_state.api_provider_draft
                st.session_state.api_base_url = draft_url
                st.session_state.api_model = draft_model
                st.session_state.api_key = draft_key
                st.session_state.api_config_status = "saved"
                st.session_state.api_status_message = "配置已保存，尚未测试连接。"
                st.session_state.api_tested_at = ""
                if test_api:
                    try:
                        with st.spinner("正在测试连接，请稍候……"):
                            test_connection(draft_key, draft_url, draft_model)
                        st.session_state.api_config_status = "connected"
                        st.session_state.api_status_message = "连接成功，可以在智能诊断中调用大模型。"
                        st.session_state.api_tested_at = datetime.now().strftime("%Y-%m-%d %H:%M")
                    except Exception as error:
                        st.session_state.api_config_status = "failed"
                        st.session_state.api_status_message = str(error)

        api_status = st.session_state.api_config_status
        if api_status == "connected":
            st.success(st.session_state.api_status_message)
        elif api_status == "saved":
            st.info(st.session_state.api_status_message)
        elif api_status == "failed":
            st.error(st.session_state.api_status_message)
        elif st.session_state.api_status_message:
            st.warning(st.session_state.api_status_message)
        else:
            st.warning("尚未配置。粘贴 API Key 后，请点击“保存并测试连接”。")
        if st.session_state.api_key:
            detail = f"当前配置：{st.session_state.api_provider} / {st.session_state.api_model} / {key_fingerprint(st.session_state.api_key)}"
            if st.session_state.api_tested_at:
                detail += f" · 测试于 {st.session_state.api_tested_at}"
            st.caption(detail)
        st.button("清除 API 配置", on_click=clear_api_config)
        st.caption("公开部署时必须使用 HTTPS。")
    st.subheader("诊断记录备份")
    history_json = json.dumps(st.session_state.user_jobs, ensure_ascii=False, indent=2)
    h1, h2 = st.columns(2)
    h1.download_button("导出我的诊断记录", data=history_json, file_name="ai_radar_history.json", mime="application/json", width="stretch")
    imported = h2.file_uploader("导入诊断记录", type=["json"], label_visibility="collapsed")
    if imported:
        try:
            payload = json.loads(imported.getvalue().decode("utf-8"))
            if not isinstance(payload, list): raise ValueError("记录文件必须是数组。")
            if any(not isinstance(item, dict) or not item.get("record_id") or not item.get("jd_raw") for item in payload):
                raise ValueError("记录文件中存在缺少 record_id 或 jd_raw 的条目。")
            st.session_state.user_jobs = payload
            if st.session_state.auth_mode == "account":
                STORE.replace_jobs(int(st.session_state.auth_user_id), payload)
            st.success(f"已导入 {len(payload)} 条记录。")
        except Exception as error:
            st.error(f"导入失败：{error}")

elif page == "智能诊断":
    page_header("智能诊断")
    single_tab, batch_tab = st.tabs(["单条诊断", "批量导入"])

    with single_tab:
        st.markdown('<div class="caption">粘贴一条完整 JD，岗位名称、时间和资格限制由系统自动提取。</div>', unsafe_allow_html=True)
        left, right = st.columns([1.35, 1])
        with left:
            jd_text = st.text_area("完整 JD", height=340, placeholder="把招聘网站上的岗位信息完整粘贴到这里，包括岗位名称、职责和任职要求……", key="jd_input")
        with right:
            st.subheader("本次使用的资料")
            if profile_ready:
                st.write(f"**画像**：{profile.school} · {profile.major} · {profile.graduation_year}届")
                st.write(f"**时间**：每周最多{profile.available_days}天 · 可实习{months_span(profile)}")
            else:
                st.warning("求职画像尚未填写完整，请先到“我的资料”补齐必填信息。")
            if st.session_state.resume_text:
                st.success(f"简历已就绪：{st.session_state.resume_name}")
            else:
                st.warning("尚未上传简历。可以继续做硬约束判断，但能力匹配只基于画像中的技能。")
            st.caption("需要修改画像、简历或 API 时，请前往“我的资料”。")
            analyze_button = st.button("分析这个岗位", type="primary", width="stretch", disabled=not profile_ready)
        if analyze_button:
            if len(jd_text.strip()) < MIN_JD_LENGTH:
                st.warning("请粘贴完整 JD，至少包含岗位职责或任职要求。")
            else:
                st.session_state["analysis"] = analyze_jd(jd_text, profile, st.session_state.resume_text)
                st.session_state["analysis_jd"] = jd_text
                st.session_state["analysis_resume"] = st.session_state.resume_text
                st.session_state["analysis_profile"] = profile
                st.session_state.pop("llm_result", None)
                st.session_state["saved_record_id"] = save_user_job(jd_text, st.session_state["analysis"])
        analysis = st.session_state.get("analysis")
        if analysis and st.session_state.get("analysis_jd") == jd_text:
            analysis_profile = st.session_state.get("analysis_profile", profile)
            save_scope = "已保存到你的岗位库" if st.session_state.auth_mode == "account" else "已加入本次访问的临时岗位库"
            render_analysis_report(
                jd_text,
                analysis_profile,
                analysis,
                st.session_state.get("analysis_resume", ""),
                f"{save_scope}：{st.session_state.get('saved_record_id', '')}",
            )

    with batch_tab:
        st.markdown(
            f'<div class="caption">一次粘贴多条 JD：用独占一行的 <code>---</code> 分隔；若没有分隔符，'
            f'则按连续空行切分。每条自动分析并写入岗位库，重复内容会自动去重。</div>',
            unsafe_allow_html=True,
        )
        batch_text = st.text_area(
            "批量 JD", height=250, key="batch_input",
            placeholder="第一条 JD 全文……\n\n---\n\n第二条 JD 全文……\n\n---\n\n第三条 JD 全文……",
        )
        batch_items = split_batch_jds(batch_text) if batch_text.strip() else []
        if batch_items:
            duplicates = dropped_duplicate_count(batch_text)
            dedupe_note = f"，已合并 <b>{duplicates}</b> 条重复内容" if duplicates else ""
            st.markdown(
                f'<div class="caption">识别到 <b>{len(batch_items)}</b> 条 JD（每条至少 {MIN_JD_LENGTH} 字）'
                f'{dedupe_note}。请先核对首行，确认没有被错误切分。</div>',
                unsafe_allow_html=True,
            )
            preview_df = pd.DataFrame([
                {"#": index, "首行": item.splitlines()[0][:72], "字数": len(item)}
                for index, item in enumerate(batch_items, 1)
            ])
            st.dataframe(preview_df, width="stretch", hide_index=True,
                         height=min(300, 58 + 35 * len(preview_df)))
        elif batch_text.strip():
            st.warning(f"没有识别到完整 JD。请确认每条不少于 {MIN_JD_LENGTH} 字，或用独占一行的 --- 分隔。")
        if not profile_ready:
            st.warning("求职画像尚未填写完整，请先到“我的资料”补齐必填信息。")
        run_batch = st.button(
            f"分析并入库（{len(batch_items)} 条）", type="primary", width="stretch",
            disabled=not batch_items or not profile_ready,
        )
        if run_batch:
            batch_rows = []
            progress = st.progress(0.0, text="正在分析……")
            for index, item in enumerate(batch_items, 1):
                item_analysis = analyze_jd(item, profile, st.session_state.resume_text)
                save_user_job(item, item_analysis)
                batch_rows.append({
                    "公司": item_analysis["company"], "岗位名称": item_analysis["role_title"],
                    "岗位大类": item_analysis["role_family"], "综合结论": item_analysis["decision"],
                    "适配度": fit_cell(item_analysis["fit_score"]),
                    "出勤": constraint_value(item_analysis, "每周出勤"),
                    "周期": constraint_value(item_analysis, "实习周期"),
                })
                progress.progress(index / len(batch_items), text=f"正在分析…… {index}/{len(batch_items)}")
            progress.empty()
            st.session_state["batch_result"] = pd.DataFrame(batch_rows)
        if "batch_result" in st.session_state and not st.session_state["batch_result"].empty:
            result_df = st.session_state["batch_result"]
            st.subheader("最近一次导入结果")
            st.markdown(
                " · ".join(f"{name} <b>{count}</b>" for name, count in result_df["综合结论"].value_counts().items()),
                unsafe_allow_html=True,
            )
            st.dataframe(result_df, width="stretch", hide_index=True,
                         height=min(400, 58 + 35 * len(result_df)))
            st.caption("这些岗位已经写入岗位库，可以在“岗位库”页按结论和约束进一步筛选。")

elif page == "岗位库":
    page_header("岗位库")
    library_scope = "当前账户" if st.session_state.auth_mode == "account" else "本次访问"
    st.markdown(f'<div class="caption">{len(st.session_state.user_jobs)} 条已分析岗位 · 当前支持 {len(ROLE_ORDER)} 类岗位 · 仅显示{library_scope}的数据，并按最新规则与求职画像重新判断</div>', unsafe_allow_html=True)
    with st.expander(f"查看完整岗位分类（{len(ROLE_ORDER)} 类）"):
        taxonomy_df = pd.DataFrame([{"#": index, "岗位大类": family, "覆盖方向": ROLE_DESCRIPTIONS[family]} for index, family in enumerate(ROLE_ORDER, 1)])
        st.dataframe(taxonomy_df, width="stretch", hide_index=True)
    with st.expander("数据概览 · 结论 / 出勤 / 周期分布"):
        if catalog_df.empty:
            st.markdown(
                '<div class="empty"><div class="t">还没有已分析的岗位</div>'
                '<div class="d">到「智能诊断」粘贴一条 JD，或用「批量导入」一次投喂多条。</div></div>',
                unsafe_allow_html=True,
            )
        else:
            o1, o2, o3 = st.columns(3)
            with o1:
                st.markdown('<div class="overline">结论</div>', unsafe_allow_html=True)
                render_barlist(
                    [(name, int(count)) for name, count in catalog_df["综合结论"].value_counts().items()],
                    alt=True,
                )
            with o2:
                st.markdown('<div class="overline">出勤要求</div>', unsafe_allow_html=True)
                render_barlist([(name, int(count)) for name, count in catalog_df["出勤"].value_counts().items()])
            with o3:
                st.markdown('<div class="overline">周期要求</div>', unsafe_allow_html=True)
                render_barlist([(name, int(count)) for name, count in catalog_df["周期"].value_counts().items()])
    if not profile_ready:
        st.warning("请先到“我的资料”补齐求职画像，岗位库才能按你的条件重新计算并展示诊断结果。")
    f1, f2, f3 = st.columns([1.35, 1.1, 1.35])
    families = f1.multiselect(f"岗位大类（{len(ROLE_ORDER)} 类）", ROLE_ORDER, default=ROLE_ORDER)
    decisions = f2.multiselect("综合结论", ["可以投递", "投递前需确认", "不建议投递"], default=["可以投递", "投递前需确认", "不建议投递"])
    query = f3.text_input("搜索", placeholder="公司、岗位或记录ID")
    with st.expander("更多约束筛选"):
        c1, c2, c3 = st.columns(3)
        status_options = ["符合", "未限制", "未提及", "加分项不满足", "需核实", "不符合"]
        day_filter = c1.multiselect("出勤", status_options, default=status_options)
        month_filter = c2.multiselect("周期", status_options, default=status_options)
        grad_filter = c3.multiselect("毕业年份", status_options, default=status_options)
    filtered = catalog_df[
        catalog_df["岗位大类"].isin(families) & catalog_df["综合结论"].isin(decisions)
        & catalog_df["出勤"].isin(day_filter) & catalog_df["周期"].isin(month_filter)
        & catalog_df["毕业年份"].isin(grad_filter)
    ]
    if query.strip():
        filtered = filtered[filtered["公司"].str.contains(query, case=False, na=False) | filtered["岗位名称"].str.contains(query, case=False, na=False) | filtered["记录ID"].str.contains(query, case=False, na=False)]
    st.caption(f"{len(filtered)} 条结果")
    if filtered.empty:
        st.markdown(
            '<div class="empty"><div class="t">没有符合条件的岗位</div>'
            '<div class="d">调整上方筛选条件，或到「智能诊断」补充新的 JD。</div></div>',
            unsafe_allow_html=True,
        )
    library_display = filtered.copy()
    library_display["适配度"] = library_display["适配度"].map(fit_cell)
    # 列表页只留日期，带时间的完整值在下方详情里。省下来的宽度留给岗位名称，
    # 否则最长的那几列会把保存时间挤到容器外，直接看不见。
    library_display["保存时间"] = library_display["保存时间"].astype(str).str.slice(0, 10)
    # 学校/专业/毕业年份在详情页的硬约束表里仍可查。10 列挤不进 962px 的容器，
    # 硬塞的结果是岗位名称和岗位大类被从中间切断（canvas 表格不会自动省略号），
    # 所以这里砍掉信息量最低的两列，把宽度让给真正要扫的两列。
    library_columns = ["记录ID", "公司", "岗位名称", "岗位大类", "综合结论", "适配度", "出勤", "周期", "保存时间"]
    library_widths = {
        "记录ID": 96, "公司": 72, "岗位名称": 264, "岗位大类": 190, "综合结论": 96,
        "适配度": 52, "出勤": 56, "周期": 56, "保存时间": 88,
    }
    if not filtered.empty:
        # 导出的就是眼前这张表的当前筛选结果，方便离线整理或直接发给别人核对。
        export_frame = library_display[library_columns].astype(str)
        st.download_button(
            "导出当前结果（CSV）",
            data=build_catalog_csv(list(export_frame.columns), export_frame.values.tolist()).encode("utf-8-sig"),
            file_name="ai_radar_jobs.csv", mime="text/csv",
        )
        st.dataframe(
            library_display[library_columns], width="stretch", hide_index=True,
            height=min(430, 58 + 35 * len(library_display)),
            column_config={name: st.column_config.TextColumn(width=width) for name, width in library_widths.items()},
        )
    if not filtered.empty:
        selected_id = st.selectbox("查看岗位", filtered["记录ID"], format_func=lambda value: f"{value} · {filtered.loc[filtered['记录ID'] == value, '公司'].iloc[0]} · {filtered.loc[filtered['记录ID'] == value, '岗位名称'].iloc[0]}")
        selected = filtered[filtered["记录ID"] == selected_id].iloc[0]
        detail = catalog_details[selected_id]
        selected_analysis = detail["analysis"]
        st.subheader(f"{selected['公司']} · {selected['岗位名称']}")
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("综合结论", selected["综合结论"]); d2.metric("适配度", fit_metric(selected["适配度"])); d3.metric("岗位大类", selected["岗位大类"]); d4.metric("保存时间", selected["保存时间"] or "未记录")
        constraint_df = pd.DataFrame(selected_analysis["constraints"])
        st.dataframe(constraint_df, width="stretch", hide_index=True)
        st.write("**核心交付物**")
        for item in selected_analysis["deliverables"] or ["未提取到明确交付物"]:
            st.write(f"- {item}")
        with st.expander("JD 原文"):
            st.text(detail["jd_raw"])
        if st.button("删除这条诊断记录"):
            if st.session_state.auth_mode == "account":
                STORE.delete_job(int(st.session_state.auth_user_id), selected_id)
            st.session_state.user_jobs = [item for item in st.session_state.user_jobs if item["record_id"] != selected_id]
            st.rerun()

else:
    page_header("更多")
    evaluation_tab, about_tab = st.tabs(["评测实验", "关于项目"])
    with evaluation_tab:
        st.markdown('<div class="caption">26 条跨平台样本先冻结预测，之后才建立人工金标准</div>', unsafe_allow_html=True)
        st.caption("样本来自实习僧、智联招聘和牛客网。以下岗位大类指标对应原 AI 岗位六类体系；新扩展的 13 类商科体系已完成规则测试，尚未建立独立人工标注评测集。")
        metric_names = {"role_family": "岗位大类", "weekly_days": "每周天数", "minimum_months": "最低月数", "constraint_result": "硬约束", "bad_case_binary": "Bad Case识别", "bad_case_type": "Bad Case类型"}
        st.subheader("盲测基线 · 冻结")
        st.caption("rule-baseline-v1 · 预测在人工标注之前冻结，是项目唯一具备盲测意义的成绩")
        metric_df = pd.DataFrame([{"指标": metric_names[key], "正确数": value["correct"], "样本数": value["total"], "准确率": value["accuracy"]} for key, value in report["metrics"].items()])
        cols = st.columns(3)
        for index, row in metric_df.iterrows():
            cols[index % 3].metric(row["指标"], metric_pct(row["准确率"]), f"{row['正确数']}/{row['样本数']}")
        st.subheader("当前网页引擎 · 内部回归")
        if not engine_report:
            st.info("尚未生成 Python 引擎的回归报告。运行 scripts/evaluate_python_engine.py 后刷新本页。")
        else:
            st.warning(engine_report["caveat"])
            engine_rows = [
                {"指标": metric_names[key], "正确数": value["correct"], "样本数": value["total"], "准确率": value["accuracy"]}
                for key, value in engine_report["metrics"].items() if value["accuracy"] is not None
            ]
            engine_df = pd.DataFrame(engine_rows)
            engine_cols = st.columns(3)
            for index, row in engine_df.iterrows():
                engine_cols[index % 3].metric(row["指标"], metric_pct(row["准确率"]), f"{row['正确数']}/{row['样本数']}")
            comparison_df = pd.DataFrame([
                {"指标": metric_names[key], "盲测基线": metric_pct(value["baseline"]), "当前引擎": metric_pct(value["python_engine"])}
                for key, value in engine_report["comparison_with_blind_baseline"].items()
            ])
            st.dataframe(comparison_df, width="stretch", hide_index=True)
            st.caption(
                f"岗位大类比较前已把金标准中的「职能支持/边界岗位」折叠为「职能支持/其他岗位」（{engine_report['taxonomy_alias_hits']} 条），"
                "否则同一概念的两种写法会被直接判错。Bad Case 类型的剩余误差集中在「边界分类」，它取决于岗位分类质量，"
                "「摘要正文冲突」为独立规则、可稳定命中。"
            )
    with about_tab:
        st.markdown('<div class="caption">项目背景、分析边界与版本说明</div>', unsafe_allow_html=True)
        st.subheader("为什么做")
        st.write("作为在校生，面对不同平台、不同公司写法各异的实习 JD，很难快速判断岗位是否真正适合自己。AI 实习雷达把求职过程拆成三个问题：能不能投、值不值得投、应该怎么投。它先识别时间、学校、专业和毕业年份等硬约束，再分析岗位核心交付物与个人能力，最后生成可审计的简历修改提示词或调用大模型完成深度改写。当前分类同时覆盖 AI 应用岗与商科院校常见的金融、财会、咨询、市场、人力、商务和供应链方向。")
        st.subheader("规则与大模型的分工")
        st.write("**本地规则层**：信息提取、明确硬约束、证据定位、冻结评测，可离线运行。")
        st.write("**大模型层**：理解复杂职责、比较简历证据、生成针对性改写。需要用户自行配置 API，且不会参与已冻结的 v1 盲测成绩。")
        st.warning("任何模型生成的简历都必须人工核验。系统明确禁止虚构经历、指标、奖项和技能。")
        st.subheader("项目版本")
        version_df = pd.DataFrame([["内部数据集", "30 条 BOSS JD", "人工复核完成"], ["外部盲测", "26 条 · 3 平台", "冻结后标注"], ["规则基线", "rule-baseline-v1", "保留原始结果"], ["网页引擎回归", "radar-core-py-v3", "26 条 · 内部回归，非盲测"], ["求职助手", "web-v7", "深色数据风界面 + 13 类岗位 + 简历自动回填 + 6 类模型接口"]], columns=["模块", "版本/规模", "状态"])
        st.dataframe(version_df, width="stretch", hide_index=True)

sidebar_api_status.caption("模型：" + api_status_label())
persist_account_state()
