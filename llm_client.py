from __future__ import annotations

import json

import requests


PROVIDERS = {
    "DeepSeek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    "通义千问（DashScope）": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    "自定义 OpenAI 兼容接口": {"base_url": "", "model": ""},
}


def _request_error_message(status_code: int, detail: str = "") -> str:
    messages = {
        400: "请求参数不正确，请检查模型名称和 Base URL。",
        401: "API Key 无效或没有访问权限，请检查是否复制完整。",
        402: "账户余额不足，请先到模型服务商控制台充值或检查额度。",
        403: "当前 API Key 无权访问这个模型。",
        404: "接口地址或模型不存在，请检查 Base URL 和模型名称。",
        429: "请求过于频繁或额度受限，请稍后再试并检查账户额度。",
    }
    message = messages.get(status_code, "模型服务暂时不可用，请稍后再试。")
    if status_code >= 500:
        message = "模型服务商暂时异常，请稍后再试。"
    return f"连接失败（{status_code}）：{message}"


def chat_completion(api_key: str, base_url: str, model: str, prompt: str, temperature: float = 0.2) -> str:
    if not api_key.strip():
        raise ValueError("未配置 API Key。")
    if not base_url.strip() or not model.strip():
        raise ValueError("Base URL 和模型名称不能为空。")
    url = f"{base_url.rstrip('/')}/chat/completions"
    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"},
            data=json.dumps({
                "model": model.strip(),
                "messages": [
                    {"role": "system", "content": "你是严谨的中文求职分析助手。不得虚构候选人经历，必须区分硬约束、能力缺口和简历表达缺口。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "stream": False,
            }, ensure_ascii=False).encode("utf-8"),
            timeout=120,
        )
    except requests.Timeout as error:
        raise RuntimeError("连接超时：请检查网络和 Base URL 后重试。") from error
    except requests.ConnectionError as error:
        raise RuntimeError("无法连接模型服务：请检查网络和 Base URL。") from error
    except requests.RequestException as error:
        raise RuntimeError("API 请求未能发出，请检查网络设置后重试。") from error
    if response.status_code >= 400:
        raise RuntimeError(_request_error_message(response.status_code, response.text[:500]))
    payload = response.json()
    try:
        return payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("API 返回格式无法识别。") from error


def test_connection(api_key: str, base_url: str, model: str) -> str:
    """Send the smallest useful request to verify credentials and model access."""
    return chat_completion(api_key, base_url, model, "只回复 OK", temperature=0)
