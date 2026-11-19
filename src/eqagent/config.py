"""全局配置：所有可调参数集中在这里，避免散落在各模块。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"


def _path(env_key: str, default: Path) -> Path:
    return Path(os.getenv(env_key) or default)


def _flag(env_key: str, default: str = "1") -> bool:
    return os.getenv(env_key, default).strip() in {"1", "true", "True", "yes"}


@dataclass(frozen=True)
class Settings:
    api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    base_url: str = os.getenv(
        "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    native_base: str = os.getenv("DASHSCOPE_NATIVE_BASE", "https://dashscope.aliyuncs.com/api/v1")

    llm_model: str = os.getenv("LLM_MODEL", "qwen-plus")
    vlm_model: str = os.getenv("VLM_MODEL", "qwen-vl-max-latest")
    embed_model: str = os.getenv("EMBED_MODEL", "text-embedding-v3")
    embed_dim: int = int(os.getenv("EMBED_DIM", "1024"))
    embed_batch: int = int(os.getenv("EMBED_BATCH", "10"))
    rerank_model: str = os.getenv("RERANK_MODEL", "gte-rerank-v2")
    rerank_enabled: bool = _flag("RERANK_ENABLED")

    qdrant_url: str = os.getenv("QDRANT_URL", "")
    qdrant_path: Path = _path("QDRANT_PATH", DATA_DIR / "qdrant")
    collection: str = os.getenv("COLLECTION", "eq_chunks")

    manuals_dir: Path = _path("MANUALS_DIR", DATA_DIR / "manuals")
    cases_path: Path = _path("CASES_PATH", DATA_DIR / "cases" / "cases.jsonl")
    parts_path: Path = _path("PARTS_PATH", DATA_DIR / "parts" / "parts.json")
    figure_dir: Path = _path("FIGURE_DIR", DATA_DIR / "figure_cache")
    index_dir: Path = _path("INDEX_DIR", DATA_DIR / "index")
    workorder_dir: Path = _path("WORKORDER_DIR", DATA_DIR / "work_orders")
    eval_path: Path = _path("EVAL_PATH", DATA_DIR / "eval" / "dev.jsonl")

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)


settings = Settings()

# 三台设备：覆盖旋转机械 / 电气 / 精密机床三类故障机理
DEVICES: dict[str, dict] = {
    "GA55": {
        "type": "螺杆空压机",
        "aliases": ["GA55", "GA 55", "GA-55", "阿特拉斯", "螺杆空压机", "空压机"],
    },
    "VMC850": {
        "type": "立式加工中心",
        "aliases": ["VMC850", "VMC 850", "VMC-850", "加工中心", "数控铣", "刀库"],
    },
    "YE3-160M": {
        "type": "三相异步电机",
        "aliases": ["YE3", "YE3-160M", "160M", "三相异步电机", "异步电机", "电机"],
    },
}


def device_type_of(model: str) -> str:
    return DEVICES.get(model, {}).get("type", "")


def guess_device(text: str) -> str:
    """按别名从自由文本里认设备型号；识别不出返回空串（后续走转人工）。"""
    low = (text or "").lower()
    for model, meta in DEVICES.items():
        for alias in meta["aliases"]:
            if alias.lower() in low:
                return model
    return ""
