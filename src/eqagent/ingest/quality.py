"""入库质检：判断切出来的块里是不是「真字」。

为什么单独一个模块：
    PDF 抽出来的"字"不一定是字。像 GA55 instruction book 那种用自定义子集字体、
    又缺 ToUnicode 映射表的 PDF，PyMuPDF 抽到的是**字符编号**而不是字母：

        qÖÜñèüêáüû§èû§£        =        6==        665

    页数正常、块数正常、页码也正常，只有内容是垃圾。这种块一旦入库：
      · embedding 会给它算一个"语义向量"（其实是噪声）
      · BM25 会被 `6==`、`665` 这类串命中
      · 结果是它们挤掉真正有用的块 —— 比"少一份文档"危害大得多

    所以入库前必须做一次质检，宁可丢块，不可丢准。

判定规则（任一命中即判为垃圾）：
    1. 非正常字符占比 > 25%      —— 正常 = ASCII 可见字符 + 中文 + 中英文标点
    2. 同一字符连续重复 >= 8 次   —— 目录点线、`3333333`
    3. 抽不出任何一个"词"         —— ASCII 词长 >= 3 或中文 >= 2 的一个都没有
    4. 词的总长度占非空白字符 < 30% —— 数字符号堆（`| 6 | | 3 |`）

    第 4 条**只对正文块生效**。表格天然是数字多、字母少（扭矩表/参数表整行都是数），
    用同一把尺子会把好表格杀光，所以表格只查 1~3 条。

用法：
    from .quality import is_garbage, noise_ratio
    if is_garbage(chunk.text, chunk.block_type): ...
"""

from __future__ import annotations

import re

_CJK = r"\u3000-\u303f\u4e00-\u9fff\uff00-\uffef"
_NORMAL = re.compile(rf"[\x20-\x7e{_CJK}]")
_WORD = re.compile(r"[A-Za-z]{3,}|[\u4e00-\u9fff]{2,}")
_REPEAT = re.compile(r"(.)\1{7,}", re.S)
_SPACE = re.compile(r"\s")

MAX_NOISE_RATIO = 0.25
MIN_WORD_SHARE = 0.30


def noise_ratio(text: str) -> float:
    """非正常字符占比。0.0 = 全是正常字，1.0 = 全是乱码。"""
    t = text or ""
    if not t:
        return 1.0
    return 1.0 - len(_NORMAL.findall(t)) / len(t)


def word_share(text: str) -> float:
    """「词」占非空白字符的比例。用来区分正文和符号堆。"""
    t = text or ""
    compact = len(_SPACE.sub("", t))
    if compact == 0:
        return 0.0
    return sum(len(w) for w in _WORD.findall(t)) / compact


def is_garbage(text: str, block_type: str = "text") -> bool:
    """True = 这条内容没有语义价值，不该入库。block_type 传 'table' 会放宽第 4 条。"""
    t = (text or "").strip()
    if len(t) < 2:
        return True
    if noise_ratio(t) > MAX_NOISE_RATIO:
        return True
    if _REPEAT.search(t):
        return True
    if not _WORD.findall(t):
        return True
    if block_type == "table":
        return False
    return word_share(t) < MIN_WORD_SHARE


def explain(text: str, block_type: str = "text") -> str:
    """给日志/体检用的原因说明，便于人工复核。"""
    t = (text or "").strip()
    if len(t) < 2:
        return "过短"
    if noise_ratio(t) > MAX_NOISE_RATIO:
        return f"乱码字符占比 {noise_ratio(t):.0%}"
    if _REPEAT.search(t):
        return "同字符连续重复"
    if not _WORD.findall(t):
        return "无完整词"
    if block_type != "table" and word_share(t) < MIN_WORD_SHARE:
        return f"词占比仅 {word_share(t):.0%}（符号/数字堆）"
    return "正常"
