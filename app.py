import json
import os
from datetime import datetime
from hashlib import sha256
from pathlib import Path

import pandas as pd
import streamlit as st

from llm_client import PROVIDERS, chat_completion, normalize_provider_config, test_connection
from radar_core import CandidateProfile, ROLE_DESCRIPTIONS, ROLE_ORDER, analyze_jd, build_resume_prompt
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


def metric_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


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
    "profile_max_months": "未填写", "profile_skills": "",
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
    "profile_graduation_year", "profile_available_days", "profile_max_months", "profile_skills",
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
    max_months = st.session_state.profile_max_months
    return CandidateProfile(
        school=st.session_state.profile_school, school_tier=st.session_state.profile_school_tier,
        major=st.session_state.profile_major, degree=st.session_state.profile_degree,
        graduation_year=int(graduation_year) if graduation_year != "未填写" else None,
        available_days=int(available_days) if available_days != "未填写" else None,
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
    st.markdown(f'<div class="decision"><div class="label">投递建议</div><div class="value {status_class(analysis["decision"])}">{analysis["decision"]}</div><div>{analysis["company"]} · {analysis["role_title"]} · {analysis["role_family"]}</div></div>', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("综合适配度", f"{analysis['fit_score']} / 100")
    m2.metric("每周要求", analysis["schedule"]["weekly_days"] or "未提及")
    m3.metric("最低周期", analysis["schedule"]["minimum_months"] or "未提及")
    m4.metric("识别技能", len(analysis["jd_skills"]))
    st.caption(record_note)
    hard, fit = st.columns([1, 1])
    with hard:
        st.subheader("硬约束")
        for constraint in analysis["constraints"]:
            render_constraint(constraint)
    with fit:
        st.subheader("能力与经历")
        st.write("**已匹配**")
        st.write("、".join(analysis["matched_skills"]) or "上传简历后才能进行可靠匹配")
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


st.set_page_config(page_title="AI 实习雷达", page_icon="◎", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
:root { --ink:#17212b; --muted:#65717e; --line:#d9e1e7; --surface:#f7f9fb; --panel:#ffffff; --blue:#176b94; --navy:#102f42; --green:#16734a; --amber:#986000; --red:#a33636; }
.stApp { background:var(--surface); color:var(--ink); }
[data-testid="stSidebar"] { background:var(--navy); }
[data-testid="stSidebar"] * { color:#edf5f8; }
[data-testid="stSidebar"] .stRadio label { padding:7px 4px; }
[data-testid="stSidebar"] input { color:#17212b; }
.st-key-logout_button button { background:#b42318 !important; border-color:#b42318 !important; color:#fff !important; }
.st-key-logout_button button * { color:#fff !important; }
.st-key-logout_button button:hover { background:#912018 !important; border-color:#912018 !important; }
.block-container { padding-top:1.4rem; padding-bottom:2rem; max-width:1480px; }
h1,h2,h3 { letter-spacing:0 !important; color:var(--ink); }
h1 { font-size:1.9rem !important; margin-bottom:.15rem !important; }
h2 { font-size:1.22rem !important; margin-top:1rem !important; }
h3 { font-size:1.02rem !important; }
.caption { color:var(--muted); font-size:.92rem; margin-bottom:1.1rem; }
[data-testid="stMetric"] { background:var(--panel); border:1px solid var(--line); border-radius:6px; padding:13px 15px; min-height:102px; }
[data-testid="stMetricLabel"] { color:var(--muted); }
[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:4px; }
.decision { background:var(--panel); border:1px solid var(--line); border-left:5px solid var(--blue); padding:15px 17px; margin:4px 0 16px; }
.decision .label { color:var(--muted); font-size:.82rem; }
.decision .value { font-size:1.3rem; font-weight:700; margin:3px 0; }
.constraint { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; background:var(--panel); border-top:1px solid var(--line); padding:11px 4px 7px; }
.constraint span { display:block; color:var(--muted); font-size:.86rem; margin-top:2px; }
.constraint b { white-space:nowrap; }
.pass { color:var(--green); } .verify { color:var(--amber); } .fail { color:var(--red); }
.tagline { border-left:4px solid var(--blue); background:var(--panel); padding:11px 15px; margin:8px 0 16px; }
.tagline strong { display:block; margin-bottom:3px; }
div[data-testid="stButton"] button { border-radius:5px; }
@media (prefers-color-scheme: dark) {
  :root { --ink:#edf3f6; --muted:#b8c6ce; --line:#40515d; --surface:#0e171e; --panel:#17242d; --blue:#61b5df; --navy:#09131a; --green:#69d6a0; --amber:#f1c15c; --red:#ff8b8b; }
  [data-testid="stSidebar"] { border-right:1px solid var(--line); }
  [data-testid="stMetric"] [data-testid="stMetricValue"], .decision, .constraint, .tagline { color:var(--ink); }
  [data-testid="stDataFrame"], [data-testid="stTable"] { color:var(--ink); }
  code { color:#e6edf1 !important; }
}
@media (max-width:700px) { .block-container { padding-left:1rem; padding-right:1rem; } h1 { font-size:1.55rem !important; } }
</style>
""", unsafe_allow_html=True)

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

with st.sidebar:
    st.markdown("### AI 实习雷达")
    st.caption("先判断能不能投，再决定怎么投")
    account_label = f"账户：{st.session_state.auth_username}" if st.session_state.auth_mode == "account" else "游客模式 · 数据不会保存"
    st.caption(account_label)
    if st.button("退出登录", key="logout_button", width="stretch"):
        sign_out()
    nav_options = ["求职首页", "我的资料", "智能诊断", "岗位库", "更多"]
    page = st.radio("导航", nav_options, label_visibility="collapsed", key="nav_page")
    st.divider()
    st.caption("我的求职画像")
    st.write(st.session_state.profile_school or "学校未填写")
    graduation_display = f"{st.session_state.profile_graduation_year}届" if st.session_state.profile_graduation_year != "未填写" else "毕业年份未填写"
    st.write(f"{st.session_state.profile_major or '专业未填写'} · {graduation_display}")
    days_display = f"每周最多 {st.session_state.profile_available_days} 天" if st.session_state.profile_available_days != "未填写" else "出勤未填写"
    months_display = f"最长 {st.session_state.profile_max_months} 个月" if st.session_state.profile_max_months != "未填写" else "周期未填写"
    st.write(f"{days_display} · {months_display}")
    st.caption("简历：" + (st.session_state.resume_name or "尚未上传"))
    sidebar_api_status = st.empty()

profile = current_profile()
profile_ready = profile_is_complete()
catalog_df, catalog_details = build_catalog(profile, st.session_state.resume_text, st.session_state.user_jobs) if profile_ready else (pd.DataFrame(columns=CATALOG_COLUMNS), {})

if page == "求职首页":
    st.title("今天先投什么")
    if profile_ready:
        st.markdown(f'<div class="caption">{profile.school} · {profile.major} · {profile.graduation_year}届 · 每周最多{profile.available_days}天 · 最长{profile.max_months}个月</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="caption">完成求职画像后，这里会按你的真实条件生成投递优先级。</div>', unsafe_allow_html=True)
    suitable = catalog_df[catalog_df["综合结论"] == "可以投递"]
    verify = catalog_df[catalog_df["综合结论"] == "投递前需确认"]
    blocked = catalog_df[catalog_df["综合结论"] == "不建议投递"]
    cols = st.columns(4)
    cols[0].metric("可直接投递", len(suitable), "先做定制简历")
    cols[1].metric("联系后再投", len(verify), "核实所有模糊约束")
    cols[2].metric("暂不建议", len(blocked), "存在明确硬门槛")
    diagnosis_note = "已保存到当前账户" if st.session_state.auth_mode == "account" else "仅保留在本次访问"
    cols[3].metric("我的诊断", len(st.session_state.user_jobs), diagnosis_note)
    if not profile_ready:
        next_step = "先到“我的资料”填写学校、专业、学历、毕业年份和实习时间，再上传简历。大模型 API 可以稍后按需配置。"
    elif st.session_state.resume_text:
        next_step = "个人资料已就绪。打开“智能诊断”粘贴 JD；如需网页直接生成深度分析，可再配置大模型 API。"
    else:
        next_step = "先到“我的资料”完善求职画像并上传简历。大模型 API 是可选项，不配置也可以完成岗位诊断。"
    st.markdown(f'<div class="tagline"><strong>你的下一步</strong>{next_step}</div>', unsafe_allow_html=True)
    left, right = st.columns([1.45, 1])
    with left:
        st.subheader("优先处理")
        st.dataframe(suitable[["公司", "岗位名称", "岗位大类", "适配度", "专业", "学校"]].sort_values("适配度", ascending=False).head(12), width="stretch", hide_index=True, height=415)
    with right:
        st.subheader("你的匹配方向")
        role_counts = suitable["岗位大类"].value_counts().reindex(ROLE_ORDER, fill_value=0)
        role_counts.index = [ROLE_CHART_LABELS[role] for role in role_counts.index]
        st.bar_chart(role_counts, horizontal=True, color="#2878B5", height=430)
        st.caption("以上结论已同时检查出勤、周期、学校层次、专业和毕业年份。")
    st.subheader("投递漏斗")
    f1, f2, f3 = st.columns(3)
    f1.info("**1. 能不能投**\n\n时间、学校、专业、毕业年份")
    f2.info("**2. 值不值得投**\n\n职责、技能、经历证据与风险")
    f3.info("**3. 怎么投**\n\n定制简历、提示词和招呼文案")

elif page == "我的资料":
    st.title("我的资料")
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
        c3, c4 = st.columns(2)
        c3.selectbox("每周最多出勤", ["未填写", *range(1, 8)], key="profile_available_days_input", on_change=sync_profile_field, args=("profile_available_days",))
        c4.selectbox("最长实习月数", ["未填写", *range(1, 13)], key="profile_max_months_input", on_change=sync_profile_field, args=("profile_max_months",))
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
        no_api, with_api = st.columns(2)
        no_api.info("**不配置 API**\n\n仍可使用硬约束判断、适配度分析、岗位库和简历修改提示词。")
        with_api.success("**配置 API**\n\n可在诊断结果中直接生成深度分析和简历改写，会消耗你自己的模型额度。")
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
    st.title("智能诊断")
    st.markdown('<div class="caption">直接粘贴完整 JD，岗位名称、时间和资格限制由系统自动提取</div>', unsafe_allow_html=True)
    left, right = st.columns([1.35, 1])
    with left:
        jd_text = st.text_area("完整 JD", height=340, placeholder="把招聘网站上的岗位信息完整粘贴到这里，包括岗位名称、职责和任职要求……", key="jd_input")
    with right:
        st.subheader("本次使用的资料")
        if profile_ready:
            st.write(f"**画像**：{profile.school} · {profile.major} · {profile.graduation_year}届")
            st.write(f"**时间**：每周最多{profile.available_days}天 · 最长{profile.max_months}个月")
        else:
            st.warning("求职画像尚未填写完整，请先到“我的资料”补齐必填信息。")
        if st.session_state.resume_text:
            st.success(f"简历已就绪：{st.session_state.resume_name}")
        else:
            st.warning("尚未上传简历。可以继续做硬约束判断，但能力匹配只基于画像中的技能。")
        st.caption("需要修改画像、简历或 API 时，请前往“我的资料”。")
        analyze_button = st.button("分析这个岗位", type="primary", width="stretch", disabled=not profile_ready)
    if analyze_button:
        if len(jd_text.strip()) < 30:
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

elif page == "岗位库":
    st.title("岗位库")
    library_scope = "当前账户" if st.session_state.auth_mode == "account" else "本次访问"
    st.markdown(f'<div class="caption">{len(st.session_state.user_jobs)} 条已分析岗位 · 当前支持 {len(ROLE_ORDER)} 类岗位 · 仅显示{library_scope}的数据，并按最新规则与求职画像重新判断</div>', unsafe_allow_html=True)
    with st.expander(f"查看完整岗位分类（{len(ROLE_ORDER)} 类）"):
        taxonomy_df = pd.DataFrame([{"#": index, "岗位大类": family, "覆盖方向": ROLE_DESCRIPTIONS[family]} for index, family in enumerate(ROLE_ORDER, 1)])
        st.dataframe(taxonomy_df, width="stretch", hide_index=True)
    if not profile_ready:
        st.warning("请先到“我的资料”补齐求职画像，岗位库才能按你的条件重新计算并展示诊断结果。")
    f1, f2, f3 = st.columns([1.35, 1.1, 1.35])
    families = f1.multiselect(f"岗位大类（{len(ROLE_ORDER)} 类）", ROLE_ORDER, default=ROLE_ORDER)
    decisions = f2.multiselect("综合结论", ["可以投递", "投递前需确认", "不建议投递"], default=["可以投递", "投递前需确认", "不建议投递"])
    query = f3.text_input("搜索", placeholder="公司、岗位或记录ID")
    with st.expander("更多约束筛选"):
        c1, c2, c3, c4, c5 = st.columns(5)
        status_options = ["符合", "未限制", "未提及", "加分项不满足", "需核实", "不符合"]
        day_filter = c1.multiselect("出勤", status_options, default=status_options)
        month_filter = c2.multiselect("周期", status_options, default=status_options)
        school_filter = c3.multiselect("学校", status_options, default=status_options)
        major_filter = c4.multiselect("专业", status_options, default=status_options)
        grad_filter = c5.multiselect("毕业年份", status_options, default=status_options)
    filtered = catalog_df[
        catalog_df["岗位大类"].isin(families) & catalog_df["综合结论"].isin(decisions)
        & catalog_df["出勤"].isin(day_filter) & catalog_df["周期"].isin(month_filter) & catalog_df["学校"].isin(school_filter)
        & catalog_df["专业"].isin(major_filter) & catalog_df["毕业年份"].isin(grad_filter)
    ]
    if query.strip():
        filtered = filtered[filtered["公司"].str.contains(query, case=False, na=False) | filtered["岗位名称"].str.contains(query, case=False, na=False) | filtered["记录ID"].str.contains(query, case=False, na=False)]
    st.caption(f"{len(filtered)} 条结果")
    st.dataframe(filtered[["记录ID", "公司", "岗位名称", "岗位大类", "综合结论", "适配度", "出勤", "周期", "学校", "专业", "毕业年份", "保存时间"]], width="stretch", hide_index=True, height=430)
    if not filtered.empty:
        selected_id = st.selectbox("查看岗位", filtered["记录ID"], format_func=lambda value: f"{value} · {filtered.loc[filtered['记录ID'] == value, '公司'].iloc[0]} · {filtered.loc[filtered['记录ID'] == value, '岗位名称'].iloc[0]}")
        selected = filtered[filtered["记录ID"] == selected_id].iloc[0]
        detail = catalog_details[selected_id]
        selected_analysis = detail["analysis"]
        st.subheader(f"{selected['公司']} · {selected['岗位名称']}")
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("综合结论", selected["综合结论"]); d2.metric("适配度", f"{selected['适配度']} / 100"); d3.metric("岗位大类", selected["岗位大类"]); d4.metric("保存时间", selected["保存时间"] or "未记录")
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
    st.title("更多")
    evaluation_tab, about_tab = st.tabs(["评测实验", "关于项目"])
    with evaluation_tab:
        st.markdown('<div class="caption">26 条跨平台样本先冻结预测，之后才建立人工金标准</div>', unsafe_allow_html=True)
        st.caption("以下岗位大类指标对应原 AI 岗位六类体系；新扩展的 13 类商科体系已完成规则测试，尚未建立独立人工标注评测集。")
        metric_names = {"role_family": "岗位大类", "weekly_days": "每周天数", "minimum_months": "最低月数", "constraint_result": "硬约束", "bad_case_binary": "Bad Case识别", "bad_case_type": "Bad Case类型"}
        metric_df = pd.DataFrame([{"指标": metric_names[key], "正确数": value["correct"], "样本数": value["total"], "准确率": value["accuracy"]} for key, value in report["metrics"].items()])
        cols = st.columns(3)
        for index, row in metric_df.iterrows():
            cols[index % 3].metric(row["指标"], metric_pct(row["准确率"]), f"{row['正确数']}/{row['样本数']}")
    with about_tab:
        st.markdown('<div class="caption">项目背景、分析边界与版本说明</div>', unsafe_allow_html=True)
        st.subheader("为什么做")
        st.write("作为在校生，面对不同平台、不同公司写法各异的实习 JD，很难快速判断岗位是否真正适合自己。AI 实习雷达把求职过程拆成三个问题：能不能投、值不值得投、应该怎么投。它先识别时间、学校、专业和毕业年份等硬约束，再分析岗位核心交付物与个人能力，最后生成可审计的简历修改提示词或调用大模型完成深度改写。当前分类同时覆盖 AI 应用岗与商科院校常见的金融、财会、咨询、市场、人力、商务和供应链方向。")
        st.subheader("规则与大模型的分工")
        st.write("**本地规则层**：信息提取、明确硬约束、证据定位、冻结评测，可离线运行。")
        st.write("**大模型层**：理解复杂职责、比较简历证据、生成针对性改写。需要用户自行配置 API，且不会参与已冻结的 v1 盲测成绩。")
        st.warning("任何模型生成的简历都必须人工核验。系统明确禁止虚构经历、指标、奖项和技能。")
        st.subheader("项目版本")
        version_df = pd.DataFrame([["内部数据集", "30 条 BOSS JD", "人工复核完成"], ["外部盲测", "26 条 · 3 平台", "冻结后标注"], ["规则基线", "rule-baseline-v1", "保留原始结果"], ["求职助手", "web-v6", "13 类岗位 + 简历自动回填 + 6 类模型接口"]], columns=["模块", "版本/规模", "状态"])
        st.dataframe(version_df, width="stretch", hide_index=True)

sidebar_api_status.caption("模型：" + api_status_label())
persist_account_state()
