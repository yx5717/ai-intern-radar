import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm_client import chat_completion, test_connection


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
