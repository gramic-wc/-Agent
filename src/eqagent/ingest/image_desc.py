"""图纸理解：把插图交给通义千问 VL，生成可检索的结构化描述。

不做这一步，图纸就只是"一张图"，检索永远命中不到它——这是多模态检索最容易漏的一环。
"""

from __future__ import annotations

import logging

from .. import llm
from ..schema import Chunk

log = logging.getLogger(__name__)

PROMPT = (
    "你是工业设备维修工程师。请客观描述这张设备手册插图，输出中文，120 字以内：\n"
    "1) 这是什么类型的图（零件图 / 结构剖面 / 控制流程图 / 电气接线图 / 检修示意）；\n"
    "2) 图中可辨认的关键部件名称与编号；\n"
    "3) 与检修作业相关的信息（拆装顺序、油/气流向、测量点、扭矩或间隙要求）。\n"
    "只写图上确实能看到的，看不清就写「不清晰」，禁止推测。"
)


def describe_figures(chunks: list[Chunk], limit: int | None = None) -> list[Chunk]:
    """给 figure 类型 chunk 补 vlm_desc，并把描述拼进 text 以便被检索到。"""
    targets = [c for c in chunks if c.block_type == "figure" and c.image_path]
    if limit:
        targets = targets[:limit]
    consecutive_failures = 0
    for i, chunk in enumerate(targets, 1):
        try:
            desc = llm.vlm_describe(chunk.image_path, PROMPT)
        except llm.LLMError as exc:
            consecutive_failures += 1
            log.warning("图纸描述失败（%s）：%s", chunk.chunk_id, exc)
            message = str(exc)
            if any(f"HTTP {code}" in message for code in (400, 401, 403, 404)):
                raise llm.LLMError(f"VLM 鉴权/权限/参数错误，停止全量任务：{exc}") from exc
            if consecutive_failures >= 3:
                raise llm.LLMError(
                    f"连续 {consecutive_failures} 张图纸描述失败，停止全量 VLM；最后错误：{exc}"
                ) from exc
            continue
        consecutive_failures = 0
        chunk.vlm_desc = desc
        chunk.text = f"{chunk.text}\n图面内容：{desc}"
        log.info("VLM %d/%d %s", i, len(targets), chunk.chunk_id)
    return chunks
