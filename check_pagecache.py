"""自检：页级缓存「命中结果 == 现场解析」且「PDF 变化即失效」。

    .venv/Scripts/python.exe check_pagecache.py
"""
import json, os, shutil, sys, tempfile
os.chdir(r"D:\pi 工作文件夹\项目学习")
sys.path.insert(0, r"D:\pi 工作文件夹\项目学习\src")

from pathlib import Path
import pymupdf as fitz
from eqagent.ingest import parse

PDF = Path(r"D:\pi 工作文件夹\项目学习\data\manuals\motor\YE3_样本_2.pdf")
FIG = Path(tempfile.mkdtemp())


def same(a, b):
    return [c.model_dump() for c in a] == [c.model_dump() for c in b]


def main() -> int:
    for f in (parse.settings.index_dir / "pagecache").glob("_selfcheck*"):
        f.unlink()

    cold = parse.parse_pdf(PDF, "_selfcheck", "YE3-160M", figure_dir=FIG)
    warm = parse.parse_pdf(PDF, "_selfcheck", "YE3-160M", figure_dir=FIG)
    assert same(cold, warm), "缓存命中的结果与现场解析不一致"

    cached = parse._load_page_cache(*parse._cache_target(PDF, "_selfcheck"), fitz.open(PDF).page_count)
    if cached is None:
        return print("FAIL: 缓存文件没写出来") or 1
    assert any(p["tables"] or p["lines"] for p in cached), "缓存里没有内容"

    # PDF 变了 → 缓存必须失效
    path, meta = parse._cache_target(PDF, "_selfcheck")
    fresh_meta = dict(meta, mtime=meta["mtime"] + 1)
    assert parse._load_page_cache(path, fresh_meta, len(cached)) is None, "mtime 变了缓存却没失效"

    # 页数对不上 → 同样失效
    assert parse._load_page_cache(path, meta, len(cached) + 1) is None, "页数变了缓存却没失效"

    # 损坏的缓存文件不能把入库搞崩
    path.write_text("{ not json", encoding="utf-8")
    assert parse._load_page_cache(path, meta, len(cached)) is None, "损坏缓存没被忽略"

    # plain 模式认不出表时必须整份回退版面分析（GA55_user_manual 那类无框线表格）
    ga55 = Path(r"D:\pi 工作文件夹\项目学习\data\manuals\ga55\GA55_user_manual.pdf")
    doc = fitz.open(ga55)
    pages = parse._extract_document(doc)
    tables = sum(len(p["tables"]) for p in pages)
    assert tables >= 40, f"GA55_user_manual 只认出 {tables} 个表，回退逻辑失效"

    print(f"OK  cold={len(cold)} chunks  warm 结果一致  失效/损坏/回退 全部正确  GA55 tables={tables}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        shutil.rmtree(FIG, ignore_errors=True)
