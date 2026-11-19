"""通义千问客户端：对话 / 视觉 / 向量 / 重排，统一走这里，方便加缓存与重试。"""

from __future__ import annotations

import base64
import json
import logging
import time
from pathlib import Path
from typing import Any, Sequence

import httpx

from .config import settings

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    if not settings.api_key:
        raise LLMError("缺少 DASHSCOPE_API_KEY：把 .env.example 复制成 .env 并填入 key")
    return {"Authorization": f"Bearer {settings.api_key}", "Content-Type": "application/json"}


def _post(url: str, payload: dict, *, retries: int = 3, timeout: float = 120.0) -> dict:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, headers=_headers(), json=payload)
            if resp.status_code == 200:
                return resp.json()
            last = LLMError(f"HTTP {resp.status_code}: {resp.text[:400]}")
            if resp.status_code in {400, 401, 404}:
                break  # 参数/鉴权错误，重试无意义
        except httpx.HTTPError as exc:
            last = exc
        time.sleep(1.5 * (attempt + 1))
    raise LLMError(f"请求失败 {url} :: {last}")


# ---------------------------------------------------------------- 向量


def embed(texts: Sequence[str]) -> list[list[float]]:
    if not texts:
        return []
    out: list[list[float]] = []
    batch = max(1, settings.embed_batch)
    for i in range(0, len(texts), batch):
        part = [t if (t or "").strip() else "空" for t in texts[i : i + batch]]
        data = _post(
            f"{settings.base_url}/embeddings",
            {"model": settings.embed_model, "input": part, "encoding_format": "float"},
            timeout=120,
        )
        items = sorted(data["data"], key=lambda d: d["index"])
        out.extend([it["embedding"] for it in items])
    return out


# ---------------------------------------------------------------- 对话


def chat(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    json_mode: bool = False,
    timeout: float = 120.0,
) -> str:
    payload: dict[str, Any] = {
        "model": model or settings.llm_model,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    data = _post(f"{settings.base_url}/chat/completions", payload, timeout=timeout)
    return (data["choices"][0]["message"].get("content") or "").strip()


def _loads(text: str) -> dict:
    s = text.strip()
    if "```" in s:
        seg = s.split("```")
        s = seg[1] if len(seg) > 1 else s
        s = s.removeprefix("json").strip()
    i, j = s.find("{"), s.rfind("}")
    if i >= 0 and j > i:
        s = s[i : j + 1]
    return json.loads(s)


def json_chat(messages: list[dict], *, model: str | None = None, temperature: float = 0.1) -> dict:
    """要求模型输出 JSON；解析失败补一次「只输出 JSON」的重试。"""
    text = chat(messages, model=model, temperature=temperature, json_mode=True)
    try:
        return _loads(text)
    except json.JSONDecodeError:
        text = chat(
            messages + [{"role": "user", "content": "只输出一个合法 JSON 对象，不要任何解释文字。"}],
            model=model,
            temperature=0,
            json_mode=True,
        )
        return _loads(text)


def vlm_describe(image_path: Path | str, prompt: str, *, model: str | None = None) -> str:
    b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    return chat(messages, model=model or settings.vlm_model, temperature=0.1, timeout=180)


# ---------------------------------------------------------------- 重排


def rerank(query: str, documents: Sequence[str], top_n: int = 8) -> list[tuple[int, float]] | None:
    """返回 [(原下标, 分数)]；失败返回 None，调用方退回 RRF 顺序。"""
    if not settings.rerank_enabled or not documents:
        return None
    url = f"{settings.native_base}/services/rerank/text-rerank/text-rerank"
    payload = {
        "model": settings.rerank_model,
        "input": {"query": query, "documents": list(documents)},
        "parameters": {"return_documents": False, "top_n": min(top_n, len(documents))},
    }
    try:
        data = _post(url, payload, retries=2, timeout=60)
    except LLMError as exc:
        log.warning("rerank 不可用，退回 RRF 排序：%s", exc)
        return None
    results = (data.get("output") or {}).get("results") or []
    return [(int(r["index"]), float(r["relevance_score"])) for r in results]
