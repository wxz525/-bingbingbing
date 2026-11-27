"""火山方舟（Ark）大模型客户端：用于新闻/摘要的语义分类。

与 news_tagger.py 的关键词规则并列，可在配置了 ARK_MODEL 后作为更准确的分级方案。
仅使用标准库 urllib，避免新增依赖。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from app.config import get_settings

TOPIC_KEYS = [
    "macro",
    "tech",
    "pharma",
    "energy",
    "finance",
    "consumer",
    "infrastructure",
    "event",
    "capital_flow",
]
LEVEL_KEYS = ["macro", "sector", "single"]
SENTIMENT_KEYS = ["bullish", "neutral", "bearish"]

_SYSTEM_PROMPT = f"""你是金融资讯分类器。对给定资讯输出严格的 JSON，不要任何解释或代码块标记。
字段：
- topics: 数组，元素取自 {TOPIC_KEYS}，可多选，无匹配则为空数组
- market_level: 取自 {LEVEL_KEYS}，宏观市场=macro，细分行业/板块=sector，单个公司/个股=single
- sentiment: 取自 {SENTIMENT_KEYS}，利好=bullish，利空=bearish，无法判断=neutral
只输出 JSON。"""


class ArkError(RuntimeError):
    pass


def _endpoint() -> tuple[str, str, str, float]:
    settings = get_settings()
    if not settings.ark_enabled:
        raise ArkError("未配置 ARK_API_KEY / ARK_MODEL，请先在 backend/.env 中填写")
    return (
        settings.ark_base_url.rstrip("/"),
        settings.ark_api_key.strip(),
        settings.ark_model.strip(),
        float(settings.ark_timeout),
    )


def _post(payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    base, key, _model, _timeout = _endpoint()
    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            error = json.loads(raw).get("error", {})
            raise ArkError(f"HTTP {exc.code} {error.get('code')}: {error.get('message', '')}") from exc
        except json.JSONDecodeError:
            raise ArkError(f"HTTP {exc.code}: {raw[:200]}") from exc
    except urllib.error.URLError as exc:
        raise ArkError(f"网络错误: {exc.reason}") from exc


def _chat(user_content: str, timeout: float) -> str:
    _base, _key, model, _timeout = _endpoint()
    data = _post(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0,
            "max_tokens": 200,
        },
        timeout,
    )
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise ArkError(f"响应结构异常: {json.dumps(data, ensure_ascii=False)[:200]}") from exc


def _parse(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ArkError(f"模型输出不是合法 JSON: {raw[:200]}") from exc

    topics = [t for t in payload.get("topics", []) if t in TOPIC_KEYS]
    level = payload.get("market_level")
    sentiment = payload.get("sentiment")
    return {
        "topics": topics,
        "market_level": level if level in LEVEL_KEYS else "single",
        "sentiment": sentiment if sentiment in SENTIMENT_KEYS else "neutral",
    }


def classify(title: str, content: str = "") -> dict[str, Any]:
    """用大模型给单条资讯打三维标签。"""
    _base, _key, _model, timeout = _endpoint()
    user = f"标题：{title}\n正文：{content[:1500]}"
    return _parse(_chat(user, timeout))


def check() -> dict[str, Any]:
    """连通性自检：只发一句极短请求，返回耗时与模型回显。"""
    base, _key, model, timeout = _endpoint()
    started = time.perf_counter()
    data = _post(
        {
            "model": model,
            "messages": [{"role": "user", "content": "只回复两个字：可用"}],
            "max_tokens": 8,
        },
        timeout,
    )
    elapsed = round((time.perf_counter() - started) * 1000)
    reply = ""
    try:
        reply = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        pass
    return {"ok": True, "base_url": base, "model": model, "latency_ms": elapsed, "reply": reply}


if __name__ == "__main__":
    import sys

    if "--check" in sys.argv:
        print(json.dumps(check(), ensure_ascii=False))
    else:
        text = " ".join(a for a in sys.argv[1:] if not a.startswith("--")) or "沪深300指数今日上涨1.2%，科技板块领涨"
        print(json.dumps(classify(text), ensure_ascii=False))
