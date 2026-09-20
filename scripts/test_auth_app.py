import os
import sys
import tempfile
from pathlib import Path

from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from storage import UserStore


app_path = Path(__file__).resolve().parents[1] / "app.py"

with tempfile.TemporaryDirectory() as directory:
    os.environ.pop("AI_RADAR_TEST_BYPASS_AUTH", None)
    os.environ["AI_RADAR_DB_PATH"] = str(Path(directory) / "auth-test.db")
    os.environ["AI_RADAR_KEY_PATH"] = str(Path(directory) / ".key")

    app = AppTest.from_file(str(app_path), default_timeout=30).run()
    assert not app.exception
    next(item for item in app.text_input if item.label == "设置用户名").set_value("resume_user")
    next(item for item in app.text_input if item.label == "设置密码").set_value("strong-password")
    next(item for item in app.text_input if item.label == "确认密码").set_value("strong-password")
    next(item for item in app.button if item.label == "创建账户").click().run()
    assert not app.exception
    assert app.session_state["auth_username"] == "resume_user"
    assert app.session_state["profile_school"] == ""
    assert app.session_state["profile_major"] == ""
    assert app.session_state["profile_graduation_year"] == "未填写"
    assert app.session_state["resume_text"] == ""
    assert app.session_state["api_key"] == ""
    assert app.session_state["user_jobs"] == []

    source_resume = Path(__file__).resolve().parents[2] / "简历" / "王嘉麟个人简历.docx"
    app.radio[0].set_value("我的资料").run()
    app.file_uploader[0].upload(
        source_resume.name,
        source_resume.read_bytes(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ).run()
    assert not app.exception
    assert app.session_state["profile_school"] == "首都经济贸易大学"
    assert app.session_state["profile_major"] == "经济统计学"
    assert app.session_state["profile_degree"] == "本科"
    assert app.session_state["profile_graduation_year"] == 2028
    assert "RAG" in app.session_state["profile_skills"]
    assert app.session_state["profile_school_tier"] == "未填写"
    assert app.session_state["profile_available_days"] == "未填写"
    assert any("上传简历后" in item.value and "手动填写" in item.value for item in app.info)

    next(item for item in app.text_input if item.label == "学校").set_value("持久化测试大学")
    next(item for item in app.text_input if item.label == "专业").set_value("经济统计学")
    for label, value in [
        ("学校层次", "非985/211"), ("学历", "本科"), ("毕业年份", 2028),
        ("每周最多出勤", 4), ("最长实习月数", 4),
    ]:
        next(item for item in app.selectbox if item.label == label).set_value(value)
    app.run()
    assert app.session_state["profile_school"] == "持久化测试大学"
    saved_after_profile = UserStore(Path(directory) / "auth-test.db", Path(directory) / ".key").load_state(
        int(app.session_state["auth_user_id"])
    )
    assert saved_after_profile["profile_school"] == "持久化测试大学"
    next(item for item in app.text_input if item.label == "API Key").set_value("sk-persisted-secret")
    next(item for item in app.button if item.label == "保存配置").click().run()
    assert app.session_state["api_config_status"] == "saved"
    assert app.session_state["profile_school"] == "持久化测试大学"
    saved_after_api = UserStore(Path(directory) / "auth-test.db", Path(directory) / ".key").load_state(
        int(app.session_state["auth_user_id"])
    )
    assert saved_after_api["profile_school"] == "持久化测试大学"

    app.radio[0].set_value("智能诊断").run()
    assert app.session_state["profile_school"] == "持久化测试大学"
    jd = "AI产品实习生\n每周4天，连续3个月。任职要求：本科大四学生，专业不限。负责Prompt和知识库运营。"
    next(item for item in app.text_area if item.label == "完整 JD").set_value(jd)
    next(item for item in app.button if item.label == "分析这个岗位").click().run()
    assert len(app.session_state["user_jobs"]) == 1
    assert app.session_state["profile_school"] == "持久化测试大学"
    saved_before_logout = UserStore(Path(directory) / "auth-test.db", Path(directory) / ".key").load_state(
        int(app.session_state["auth_user_id"])
    )
    assert saved_before_logout["profile_school"] == "持久化测试大学"

    next(item for item in app.button if item.label == "退出登录").click().run()
    assert not app.radio
    next(item for item in app.text_input if item.label == "用户名").set_value("resume_user")
    next(item for item in app.text_input if item.label == "密码").set_value("strong-password")
    next(item for item in app.button if item.label == "登录").click().run()
    assert not app.exception
    assert app.session_state["profile_school"] == "持久化测试大学"
    assert app.session_state["api_key"] == "sk-persisted-secret"
    assert len(app.session_state["user_jobs"]) == 1

    guest = AppTest.from_file(str(app_path), default_timeout=30).run()
    assert not any("密码只保存加盐哈希" in item.value for item in guest.caption)
    next(item for item in guest.button if item.label == "游客体验").click().run()
    assert guest.session_state["auth_mode"] == "guest"
    assert guest.session_state["auth_user_id"] is None
    guest.radio[0].set_value("我的资料").run()
    next(item for item in guest.text_input if item.label == "学校").set_value("游客测试大学").run()
    assert guest.session_state["profile_school"] == "游客测试大学"
    assert "游客测试大学" not in (Path(directory) / "auth-test.db").read_text(encoding="utf-8", errors="ignore")
    next(item for item in guest.button if item.label == "退出登录").click().run()
    next(item for item in guest.button if item.label == "游客体验").click().run()
    assert guest.session_state["profile_school"] == ""

print({"register": "passed", "login": "passed", "account_restore": "passed", "guest_isolation": "passed"})
