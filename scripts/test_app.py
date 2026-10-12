import os
import sys
import tempfile
from pathlib import Path

from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm_client import PROVIDERS
from radar_core import CandidateProfile, analyze_jd, build_catalog_csv, build_report_markdown
from storage import UserStore


app_path = Path(__file__).resolve().parents[1] / "app.py"
test_data = tempfile.TemporaryDirectory()
os.environ["AI_RADAR_TEST_BYPASS_AUTH"] = "1"
os.environ["AI_RADAR_DB_PATH"] = str(Path(test_data.name) / "app-test.db")
os.environ["AI_RADAR_KEY_PATH"] = str(Path(test_data.name) / ".key")
test_store = UserStore(Path(test_data.name) / "app-test.db", Path(test_data.name) / ".key")
test_user = test_store.ensure_test_user()
test_store.save_state(test_user["id"], {
    "profile_school": "首都经济贸易大学", "profile_school_tier": "非985/211", "profile_major": "经济统计学",
    "profile_degree": "本科", "profile_graduation_year": 2028, "profile_available_days": 4,
    "profile_max_months": 4, "profile_skills": "Python、RAG、Bad Case", "api_key": "",
})
pages = ["求职首页", "我的资料", "智能诊断", "岗位库", "更多"]
results = []

for page_name in pages:
    app = AppTest.from_file(str(app_path), default_timeout=30).run()
    app.radio[0].set_value(page_name).run()
    if app.exception:
        raise AssertionError(f"{page_name}: {app.exception}")
    results.append({"page": page_name, "title_count": len(app.title), "exceptions": len(app.exception)})

if set(app.radio[0].options) != {"求职首页", "我的资料", "智能诊断", "岗位库", "更多"}:
    raise AssertionError(f"侧栏仍存在未合并的低频页面: {app.radio[0].options}")
if any(item.value == "失败模式" for item in app.subheader):
    raise AssertionError("更多页面仍展示失败模式")

app = AppTest.from_file(str(app_path), default_timeout=30).run()
app.radio[0].set_value("我的资料").run()
captions = [item.value for item in app.caption]
if not any("简历仅用于" in value for value in captions) or not any("API Key 仅用于" in value for value in captions):
    raise AssertionError("简历或 API 配置区缺少隐私与用途说明")
button_labels = {item.label for item in app.button}
if not {"保存配置", "保存并测试连接", "清除 API 配置"}.issubset(button_labels):
    raise AssertionError(f"API 配置操作不完整: {button_labels}")
base_url_input = next(item for item in app.text_input if item.label == "Base URL")
model_input = next(item for item in app.text_input if item.label == "模型")
if base_url_input.value != "https://api.deepseek.com/v1" or model_input.value != "deepseek-chat":
    raise AssertionError("DeepSeek 推荐地址和模型未自动填写")

provider_select = next(item for item in app.selectbox if item.label == "模型服务")
if list(provider_select.options) != list(PROVIDERS):
    raise AssertionError(f"模型服务商选项不正确: {provider_select.options}")
for provider, defaults in PROVIDERS.items():
    provider_select.set_value(provider).run()
    if app.exception:
        raise AssertionError(f"切换到 {provider} 后页面报错: {app.exception}")
    current_url = next(item for item in app.text_input if item.label == "Base URL")
    current_model = next(item for item in app.text_input if item.label == "模型")
    if current_url.value != defaults["base_url"] or current_model.value != defaults["model"]:
        raise AssertionError(f"{provider} 未自动填写正确的地址和模型")
    provider_select = next(item for item in app.selectbox if item.label == "模型服务")

next(item for item in app.selectbox if item.label == "模型服务").set_value("自定义").run()
next(item for item in app.text_input if item.label == "Base URL").set_value("https://custom.example.com/v1").run()
next(item for item in app.text_input if item.label == "模型").set_value("custom-model").run()
if app.session_state["api_base_url_draft"] != "https://custom.example.com/v1" or app.session_state["api_model_draft"] != "custom-model":
    raise AssertionError("自定义接口的地址或模型不可编辑")
next(item for item in app.selectbox if item.label == "模型服务").set_value("DeepSeek").run()
next(item for item in app.text_input if item.label == "API Key").set_value("sk-test-session-key")
next(item for item in app.button if item.label == "保存配置").click().run()
if app.exception:
    raise AssertionError(f"保存 API 配置: {app.exception}")
if app.session_state["api_config_status"] != "saved" or app.session_state["api_key"] != "sk-test-session-key":
    raise AssertionError("API 配置未明确保存到当前账户")

app = AppTest.from_file(str(app_path), default_timeout=30).run()
app.radio[0].set_value("智能诊断").run()
jd = """贝壳找房 产品经理（AI效果评测方向）实习生
4天/周，最少3个月
岗位职责：参与Agent Chat和RAG效果评测标准搭建，构建测试集，分析Bad Case并输出优化建议。
岗位要求：本科及以上，计算机、数据科学、统计相关专业优先，2026年9月-2028年8月毕业。"""
next(item for item in app.text_area if item.label == "完整 JD").set_value(jd)
next(item for item in app.button if item.label == "分析这个岗位").click().run()
if app.exception:
    raise AssertionError(f"智能诊断交互: {app.exception}")
metric_values = {item.label: item.value for item in app.metric}
if metric_values.get("每周要求") != "4" or metric_values.get("最低周期") != "3":
    raise AssertionError(f"自动时间提取错误: {metric_values}")
if not any("可以投递" in markdown.value for markdown in app.markdown):
    raise AssertionError("未产生预期的投递结论")
if any(item.value == "相似已复核案例" for item in app.subheader):
    raise AssertionError("智能诊断仍展示相似已复核案例")
if len(app.session_state["user_jobs"]) != 1:
    raise AssertionError("诊断记录未保存到当前账户")
app.radio[0].set_value("岗位库").run()
if app.exception:
    raise AssertionError(f"岗位库诊断记录: {app.exception}")
family_filter = next(item for item in app.multiselect if item.label.startswith("岗位大类"))
if len(family_filter.options) != 13:
    raise AssertionError(f"岗位库未显示 13 类新分类: {family_filter.options}")
library_tables = [item.value for item in app.dataframe if "记录ID" in item.value.columns]
if not library_tables or len(library_tables[0]) != 1 or "数据来源" in library_tables[0].columns:
    raise AssertionError("岗位库没有仅展示当前用户诊断记录")

# --- 批量导入：显式分隔符切分 ---
batch_jds = [
    """字节跳动 AI产品运营实习生
5天/周，实习3个月
岗位职责：负责AI产品的用户增长与内容运营，策划活动并复盘数据。
岗位要求：本科及以上，2027年及以后毕业。""",
    """某咨询公司 行业研究实习生
3天/周，实习2个月
岗位职责：撰写行业研究报告，整理专家访谈纪要，搭建数据底稿。
岗位要求：本科及以上，经济、统计相关专业优先。""",
    """某快消公司 市场部实习生
4天/周，实习6个月
岗位职责：负责品牌社交媒体内容排期与投放数据复盘。
岗位要求：本科在读，市场营销相关专业优先。""",
]

app = AppTest.from_file(str(app_path), default_timeout=60).run()
app.radio[0].set_value("智能诊断").run()
batch_before = len(app.session_state["user_jobs"])
next(item for item in app.text_area if item.label == "批量 JD").set_value("\n\n---\n\n".join(batch_jds)).run()
batch_button = next(item for item in app.button if item.label.startswith("分析并入库"))
if batch_button.label != "分析并入库（3 条）":
    raise AssertionError(f"分隔符切分数量不对：{batch_button.label}")
batch_button.click().run()
if app.exception:
    raise AssertionError(f"批量导入报错：{app.exception}")
batch_after = len(app.session_state["user_jobs"])
if batch_after - batch_before != 3:
    raise AssertionError(f"批量导入未新增 3 条：{batch_before} -> {batch_after}")
if len(app.session_state["batch_result"]) != 3:
    raise AssertionError("批量导入结果表行数不正确")

# --- 批量导入：无分隔符时退回到连续空行切分 ---
app = AppTest.from_file(str(app_path), default_timeout=60).run()
app.radio[0].set_value("智能诊断").run()
next(item for item in app.text_area if item.label == "批量 JD").set_value("\n\n\n\n".join(batch_jds)).run()
blank_split_button = next(item for item in app.button if item.label.startswith("分析并入库"))
if blank_split_button.label != "分析并入库（3 条）":
    raise AssertionError(f"空行切分数量不对：{blank_split_button.label}")

# --- 批量导入：碎片不应被当成 JD ---
app = AppTest.from_file(str(app_path), default_timeout=60).run()
app.radio[0].set_value("智能诊断").run()
next(item for item in app.text_area if item.label == "批量 JD").set_value("太短\n\n---\n\n也短").run()
fragment_button = next(item for item in app.button if item.label.startswith("分析并入库"))
if fragment_button.label != "分析并入库（0 条）":
    raise AssertionError(f"短碎片未被过滤：{fragment_button.label}")
if not fragment_button.disabled:
    raise AssertionError("没有可分析内容时按钮应为禁用状态")

# --- 诊断报告导出 ---
# AppTest 的 download_button 不暴露 .data，所以「按钮在不在」用 AppTest 验，
# 「报告内容对不对」直接单测纯函数 build_report_markdown（它住在 radar_core.py）。
app = AppTest.from_file(str(app_path), default_timeout=60).run()
app.radio[0].set_value("智能诊断").run()
next(item for item in app.text_area if item.label == "完整 JD").set_value(jd).run()
next(item for item in app.button if item.label == "分析这个岗位").click().run()
if app.exception:
    raise AssertionError(f"诊断报告导出交互：{app.exception}")
if not [item for item in app.download_button if item.label == "导出这份诊断报告"]:
    raise AssertionError("诊断报告缺少导出按钮")

export_profile = CandidateProfile(
    school="首都经济贸易大学", major="经济统计学", degree="本科",
    graduation_year=2028, available_days=4, max_months=4,
)
report_text = build_report_markdown(analyze_jd(jd, export_profile), jd, export_profile)
for required in ("## 硬约束", "## 能力与经历", "## 核心交付物", "## 建议动作", "## JD 原文", "贝壳找房", "投递建议"):
    if required not in report_text:
        raise AssertionError(f"导出报告缺少小节：{required}")
if "None" in report_text or "nan" in report_text:
    raise AssertionError("导出报告泄漏了未处理的控制值")
if jd.strip() not in report_text:
    raise AssertionError("导出报告没有完整保留 JD 原文")

# --- 批量导入：批内重复必须合并，否则按钮条数与实际入库条数对不上 ---
app = AppTest.from_file(str(app_path), default_timeout=60).run()
app.radio[0].set_value("智能诊断").run()
next(item for item in app.text_area if item.label == "批量 JD").set_value(
    "\n\n---\n\n".join([batch_jds[0], batch_jds[1], batch_jds[0]])
).run()
dedupe_button = next(item for item in app.button if item.label.startswith("分析并入库"))
if dedupe_button.label != "分析并入库（2 条）":
    raise AssertionError(f"批内重复未被合并：{dedupe_button.label}")
if not any("已合并" in item.value and "1" in item.value for item in app.markdown):
    raise AssertionError("批内去重没有如实告知用户")

# --- 岗位库 CSV 导出 ---
app = AppTest.from_file(str(app_path), default_timeout=60).run()
app.radio[0].set_value("岗位库").run()
if app.exception:
    raise AssertionError(f"岗位库 CSV 导出：{app.exception}")
if not [item for item in app.download_button if item.label == "导出当前结果（CSV）"]:
    raise AssertionError("岗位库缺少 CSV 导出按钮")

# build_catalog_csv 是纯函数，直接单测内容而不是去够 download_button 的 data。
csv_text = build_catalog_csv(["公司", "适配度"], [["滴滴, 出行", "72"], ["快手", "—"]])
if csv_text.splitlines()[0] != "公司,适配度":
    raise AssertionError(f"CSV 表头不正确：{csv_text!r}")
if '"滴滴, 出行",72' not in csv_text:
    raise AssertionError(f"CSV 没有正确转义含逗号的字段：{csv_text!r}")

# --- 方向分布统计的是整个岗位库，不是只看「可以投递」那几条 ---
app = AppTest.from_file(str(app_path), default_timeout=60).run()
if app.radio[0].value != "求职首页":
    raise AssertionError(f"默认页不是求职首页：{app.radio[0].value}")
home_captions = "\n".join(item.value for item in app.caption)
if f"岗位库共 {len(app.session_state['user_jobs'])} 条" not in home_captions:
    raise AssertionError(f"首页方向分布没有覆盖整个岗位库：{home_captions}")

# --- N2 回归：搜索框输入正则元字符不得让整页崩溃 ---
# pandas 的 str.contains 默认 regex=True，输入「(」「[」「*」会抛
# PatternSyntaxException，整页直接报错。这里逐个试一遍。
app = AppTest.from_file(str(app_path), default_timeout=60).run()
app.radio[0].set_value("岗位库").run()
for probe in ["(", "[", "*", "\\", "（贝壳"]:
    next(item for item in app.text_input if item.label == "搜索").set_value(probe).run()
    if app.exception:
        raise AssertionError(f"搜索框输入 {probe!r} 导致页面崩溃：{app.exception}")

# --- N6 回归：硬约束卡片必须转义，不能把尖括号原样写进自绘 HTML ---
# 这一步会改写账户画像，放在 resume_honesty 之前（后者会重写整份状态）。
test_store.save_state(test_user["id"], {
    "profile_school": "首都经济贸易大学", "profile_school_tier": "非985/211",
    "profile_major": "<img src=x onerror=alert(1)>",
    "profile_degree": "本科", "profile_graduation_year": 2028, "profile_available_days": 4,
    "profile_max_months": 4, "profile_skills": "Python", "api_key": "",
})
app = AppTest.from_file(str(app_path), default_timeout=60).run()
app.radio[0].set_value("智能诊断").run()
next(item for item in app.text_area if item.label == "完整 JD").set_value(
    # 不带「优先」二字，走「需核实」分支，说明里会原样嵌入画像里的专业名，
    # 正好用来验证 render_constraint 有没有转义。
    "数据分析实习生\n岗位职责：负责看板搭建。\n任职要求：法学、新闻传播相关专业。"
)
next(item for item in app.button if item.label == "分析这个岗位").click().run()
if app.exception:
    raise AssertionError(f"转义回归用例诊断报错：{app.exception}")
constraint_html = "\n".join(item.value for item in app.markdown if '<div class="constraint">' in item.value)
if not constraint_html:
    raise AssertionError("没有渲染出硬约束卡片，无法验证转义")
if "<img" in constraint_html:
    raise AssertionError("硬约束卡片未转义，尖括号被原样写进了 DOM")
if "&lt;img" not in constraint_html:
    raise AssertionError(f"硬约束卡片没有按预期转义：{constraint_html[:200]}")

# --- 简历已上传却一条技能都没匹配上时，不能再说「上传简历后才能匹配」 ---
# 放在最后跑：这一步会改写账户状态，不能影响上面的断言。
test_store.save_state(test_user["id"], {
    "profile_school": "首都经济贸易大学", "profile_school_tier": "非985/211", "profile_major": "经济统计学",
    "profile_degree": "本科", "profile_graduation_year": 2028, "profile_available_days": 4,
    "profile_max_months": 4, "profile_skills": "Python、RAG、Bad Case", "api_key": "",
    "resume_text": "首都经济贸易大学 经济统计学 本科 2028 届\n技能：Python、RAG、Bad Case 分析",
    "resume_name": "个人简历.docx",
})
app = AppTest.from_file(str(app_path), default_timeout=60).run()
app.radio[0].set_value("智能诊断").run()
unrelated_jd = """某会计师事务所 审计实习生
3天/周，实习2个月
岗位职责：协助完成企业年报审计底稿，整理记账凭证与往来函证，参与存货盘点。
岗位要求：本科及以上，会计、财务管理相关专业，已通过 CPA 部分科目者优先。"""
next(item for item in app.text_area if item.label == "完整 JD").set_value(unrelated_jd)
next(item for item in app.button if item.label == "分析这个岗位").click().run()
if app.exception:
    raise AssertionError(f"审计岗诊断：{app.exception}")
page_text = "\n".join(item.value for item in app.markdown)
if "上传简历后才能进行可靠匹配" in page_text:
    raise AssertionError("简历已上传，却仍在提示「上传简历后才能进行可靠匹配」")
if "没有识别到与 JD 明确对应的技能" not in page_text:
    raise AssertionError("简历无技能命中时缺少如实的说明")

print({"pages": results, "diagnosis_metrics": metric_values, "batch_import": "ok",
       "batch_dedupe": "ok", "report_export": "ok", "csv_export": "ok",
       "role_distribution": "ok", "search_metachar": "ok", "constraint_escaping": "ok",
       "resume_honesty": "ok"})
test_data.cleanup()