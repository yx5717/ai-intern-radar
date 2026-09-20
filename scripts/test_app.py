import os
import sys
import tempfile
from pathlib import Path

from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm_client import PROVIDERS
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

print({"pages": results, "diagnosis_metrics": metric_values})
test_data.cleanup()
