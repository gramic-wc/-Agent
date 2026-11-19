"""手册体检脚本：给一个 PDF（本地路径或直连 URL），看它对本项目到底有多少"可用料"。

为什么要这个脚本：
    手册"页数多"不等于"有用"。对本项目有用的只有三类东西——
    正文块（能引用）、表格块（故障码/参数/扭矩）、图片块（图纸理解）。
    这份脚本就是用本项目真实的解析链（ingest/parse.py）去数这三类有多少，
    数不出来就说明这份 PDF 入库后是废的，别浪费时间。

用法：
    # 体检本地文件
    uv run python scripts/check_manual.py data/manuals/ga55/GA55_instruction_book_en.pdf

    # 下载 + 体检（URL 含中文/空格也没关系，脚本会自动编码）
    uv run python scripts/check_manual.py "https://www.gsk.com.cn/uploadfiles/网站说明书/xxx.pdf"

    # 只看不下载（文件已存在时不重复下载）
    uv run python scripts/check_manual.py <url>

下载的文件落在 data/manuals/_probe/（已在 .gitignore 里，不会提交）。
URL 下载不会跑 VLM，不消耗 API 额度。
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import httpx  # noqa: E402

from eqagent.config import guess_device  # noqa: E402
from eqagent.ingest.parse import parse_pdf  # noqa: E402
from eqagent.ingest.quality import explain, is_garbage  # noqa: E402

PROBE_DIR = ROOT / "data" / "manuals" / "_probe"
FIG_DIR = PROBE_DIR / "_figs"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

# SOURCES.md 里的三条硬标准
MIN_TEXT = 20       # 正文块少于这个数，基本等于没文字层
MIN_TABLE = 1       # 至少要有表格（故障码表/参数表）
MIN_FIGURE = 1      # 至少要有图（否则多模态链路测不出来）


def _safe_name(url: str) -> str:
    """从 URL 取一个 Windows 合法的文件名。"""
    raw = unquote(urlparse(url).path)
    name = raw.rsplit("/", 1)[-1] or "download.pdf"
    name = re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "download.pdf"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def fetch(url: str) -> Path:
    """下载到 data/manuals/_probe/，已存在就跳过。"""
    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    out = PROBE_DIR / _safe_name(url)
    if out.exists() and out.stat().st_size > 0:
        print(f"⏭  已存在，跳过下载：{out.relative_to(ROOT)}")
        return out

    print(f"↓  下载中：{url}")
    with httpx.stream(
        "GET", url, follow_redirects=True, timeout=180.0, headers={"User-Agent": UA}
    ) as r:
        r.raise_for_status()
        with open(out, "wb") as f:
            for chunk in r.iter_bytes(1 << 16):
                f.write(chunk)

    size = out.stat().st_size
    head = out.read_bytes()[:5]
    # 三个常见坑：下成了登录页(HTML)、下成了 0 字节、被站点换成了其他格式
    if head[:4] != b"%PDF":
        print(f"✗  不是 PDF（开头是 {head!r}）—— 该站大概要登录，删掉换备选：{out}")
        out.unlink(missing_ok=True)
        sys.exit(2)
    print(f"✓  已保存 {size / 1024:.0f} KB → {out.relative_to(ROOT)}")
    return out


def probe(pdf: Path) -> int:
    """用真实解析链数块，打印体检报告。返回退出码。"""
    device = guess_device(pdf.stem) or guess_device(str(pdf.parent)) or "未识别"
    print(f"\n体检：{pdf.name}")
    print(f"推断型号：{device}   （识别不出就改文件名带上 GA55 / VMC850 / YE3）")

    chunks = parse_pdf(pdf, doc_id="_probe", device_model=device, figure_dir=FIG_DIR)
    counts = Counter(c.block_type for c in chunks)
    pages = {c.page for c in chunks}
    with_section = sum(1 for c in chunks if c.section_path)

    text_n = counts.get("text", 0)
    table_n = counts.get("table", 0)
    figure_n = counts.get("figure", 0)

    # 关键一步：块数正常不代表内容是字（坏字体 PDF 会抽出 qÖÜñèüê 这种）
    readable = [c for c in chunks if c.block_type != "figure"]
    garbage = [c for c in readable if is_garbage(c.text, c.block_type)]
    bad_ratio = len(garbage) / len(readable) if readable else 1.0

    print("-" * 58)
    print(f"  有内容页数   {len(pages)}")
    print(f"  正文块       {text_n}")
    print(f"  表格块       {table_n}")
    print(f"  图片块       {figure_n}")
    print(f"  有章节路径   {with_section}/{len(chunks)}")
    print(f"  乱码/无词块  {len(garbage)}/{len(readable)}（{bad_ratio:.0%}）")
    if garbage:
        top = Counter(explain(c.text, c.block_type) for c in garbage).most_common(2)
        print(f"             主因：{', '.join(f'{k}×{v}' for k, v in top)}")
    print("-" * 58)

    verdict = []
    if text_n < MIN_TEXT:
        verdict.append(f"✗ 正文太少({text_n})：可能是扫描件（无文字层），别硬修，换一份")
    if bad_ratio > 0.30:
        verdict.append(
            f"✗ 乱码块占 {bad_ratio:.0%}：自定义字体缺 ToUnicode，字抽不出来。"
            f"图好就用 skip_text.txt 只收图，图也不好就换一份"
        )
    if table_n < MIN_TABLE:
        verdict.append("△ 没有表格：故障码/参数表全靠正文描述，检索会打折")
    if figure_n < MIN_FIGURE:
        verdict.append("△ 没有图片：多模态链路测不出来")
    if with_section == 0:
        verdict.append("△ 章节路径全空：引用只能定位到页码，定位不到小节")

    if not verdict:
        print("✅ 通过：正文/表格/图三类齐全，章节路径可用")
    else:
        for v in verdict:
            print(v)
        print("（△ 可以入库但打折扣；✗ 建议换一份备选）")

    # 抽 3 条正文，人工翻 PDF 核对页码是否对得上
    samples = [c for c in chunks if c.block_type == "text"][:3]
    if samples:
        print("\n抽 3 条正文核对页码：")
        for c in samples:
            print(f"  p{c.page:<4} {c.section_path or '(无章节)':<24} | {c.text[:50]}")
        print("  → 拿 PDF 翻到这几页，看是不是这段。页码错=后面引用全废。")

    return 0 if (text_n >= MIN_TEXT and table_n >= MIN_TABLE and bad_ratio <= 0.30) else 1


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    arg = sys.argv[1]
    if arg.startswith(("http://", "https://")):
        try:
            pdf = fetch(arg)
        except httpx.HTTPStatusError as e:
            print(f"✗  下载失败 HTTP {e.response.status_code}：{arg}")
            print("   → 换 SOURCES.md 里的备选链接，不要死磕")
            sys.exit(2)
        except httpx.HTTPError as e:
            print(f"✗  下载失败 {type(e).__name__}：{e}")
            print("   → 超时/连接被拒，换备选链接")
            sys.exit(2)
    else:
        pdf = Path(arg)
        if not pdf.exists():
            print(f"✗  文件不存在：{pdf}")
            sys.exit(1)

    sys.exit(probe(pdf))


if __name__ == "__main__":
    main()
