import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm_client import PROVIDERS, chat_completion, normalize_provider_config, test_connection


expected_providers = {
    "DeepSeek": ("https://api.deepseek.com/v1", "deepseek-chat"),
    "通义千问": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
    "豆包": ("https://ark.cn-beijing.volces.com/api/v3", "doubao-seed-1-6-250615"),
    "GLM": ("https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
    "Kimi": ("https://api.moonshot.cn/v1", "moonshot-v1-8k"),
    "自定义": ("", ""),
}
assert set(PROVIDERS) == set(expected_providers)
for provider, (base_url, model) in expected_providers.items():
    assert PROVIDERS[provider] == {"base_url": base_url, "model": model}

old_url = "https://legacy.example.com/v1"
old_model = "legacy-model"
assert normalize_provider_config("已移除的旧服务商", old_url, old_model) == ("自定义", old_url, old_model)
assert normalize_provider_config("通义千问（DashScope）", old_url, old_model) == ("通义千问", old_url, old_model)


response = Mock(status_code=200)
response.json.return_value = {"choices": [{"message": {"content": "测试改写结果"}}]}
with patch("llm_client.requests.post", return_value=response) as mocked:
    result = chat_completion("session-key", "https://example.com/v1", "example-model", "测试提示词")
    assert result == "测试改写结果"
    call = mocked.call_args
    assert call.args[0] == "https://example.com/v1/chat/completions"
    assert call.kwargs["headers"]["Authorization"] == "Bearer session-key"
    assert b"example-model" in call.kwargs["data"]

connection_response = Mock(status_code=200)
connection_response.json.return_value = {"choices": [{"message": {"content": "OK"}}]}
with patch("llm_client.requests.post", return_value=connection_response) as mocked:
    assert test_connection("session-key", "https://api.deepseek.com/v1", "deepseek-chat") == "OK"
    assert b'"temperature": 0' in mocked.call_args.kwargs["data"]

unauthorized = Mock(status_code=401, text="invalid api key")
with patch("llm_client.requests.post", return_value=unauthorized):
    try:
        test_connection("bad-key", "https://api.deepseek.com/v1", "deepseek-chat")
        raise AssertionError("401 should raise RuntimeError")
    except RuntimeError as error:
        assert "API Key 无效" in str(error)

print({"api_request": "passed", "key_persistence": "covered by test_storage.py"})
