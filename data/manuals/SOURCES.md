# 手册来源清单（实测版）

> 本文件记录**已验证可直连下载**的手册链接与实测切块数据。
> 数据由 `scripts/check_manual.py` 产出（正文/表/图 = 本项目的解析链实际能切出的块数），
> 不是文档页数估算——页数多但切不出表格和图的文档，对本项目没有价值。
>
> 全部为公开网络资源，仅本地学习使用。**PDF 不提交到仓库**（见 `.gitignore`）。
> 实测时间：2026-11-19

---

## 一、目标与现状

| 设备 | 目标份数 | 已验证可用 | 缺口 |
| --- | --- | --- | --- |
| 螺杆空压机 GA55 | 6~8 | 4 | 中文版操作说明书缺（现有主力为英文） |
| 立式加工中心 VMC850 | 6~8 | 3 | **缺专门针对 VMC850 整机的操作/维修说明书**，现有为数控系统级手册 |
| 三相异步电机 YE3-160M | 5~8 | 5 | 基本够用 |

**采集硬标准**（三条同时满足才算达标）：
1. 有**表格**（参数表 / 故障码表 / 扭矩表 / 保养周期表）
2. 有**章节编号**（`section_path` 才有内容，引用才能定位）
3. 全文至少 3 份带**插图**（剖面图 / 流程图 / 接线图），否则多模态链路测不出来

---

## 二、螺杆空压机（GA55）

放入 `data/manuals/ga55/`

| # | 文档 | 建议文件名 | 实测（页/正文/表/图） | 判定 |
| --- | --- | --- | --- | --- |
| 1 | Atlas Copco GA55/GA75/GA90C Instruction Book | `GA55_instruction_book_en.pdf` | 145 / 575 / 140 / 51 | ✅ **主力**：表格与图纸最全 |
| 2 | Atlas Copco GA55 User Manual (manualslib) | `GA55_user_manual.pdf` | 34 / 120 / 50 / 5 | ✅ 补充 |
| 3 | 一般用喷油螺杆空气压缩机 维修保养规范（团标） | `GA55_维护保养规范_团标.pdf` | 20 / 48 / 9 / 0 | ✅ 保养周期与记录表 |
| 4 | 一般用变频喷水单螺杆空气压缩机（团标） | `单螺杆_变频喷水_团标.pdf` | 14 / 34 / 8 / 1 | ○ 机型不同，作对照 |
| — | GA 55 官方 datasheet | `GA55_datasheet.pdf` | 1 / 2 / 2 / 0 | ✗ 太短，不要 |

链接：

```
https://jahancompressor.com/wp-content/uploads/2025/10/Atlas-Copco-GA75-1759661915.1284.pdf
https://data2.manualslib.com/cpdf/16/80/7977/484ca6.pdf
https://www.ttbz.org.cn/upload/file/20241122/6386791256391624113747184.pdf
https://www.ttbz.org.cn/upload/file/20241111/6386693417731008897372167.pdf
```

---

## 三、立式加工中心（VMC850）

放入 `data/manuals/vmc850/`

| # | 文档 | 建议文件名 | 实测（页/正文/表/图） | 判定 |
| --- | --- | --- | --- | --- |
| 1 | GSK983M 加工中心数控系统 PLC 使用说明（广数官方） | `VMC850_GSK983M_PLC使用说明.pdf` | 57 / 160 / 35 / 10 | ✅ 报警号与 PLC 信号表齐全 |
| 2 | SINUMERIK 系统手册（西门子 802D 系） | `VMC850_SINUMERIK_系统手册.pdf` | 407 / 1289 / 111 / 243 | ✅ 体量大，可按章裁剪后入库 |
| 3 | JN-NV900 立式加工中心 样本 | `VMC850_JN-NV900_样本.pdf` | 9 / 27 / 4 / 3 | ✅ 规格表 |
| — | VMC850 教材节选（qlit.edu.cn） | — | 3 / 0 / 3 / 0 | ✗ 无正文，不要 |

链接：

```
https://www.gsk.com.cn/uploadfiles/网站说明书/cnc/研发四室/983ma中文/GSK983M系列加工中心数控系统 PLC使用说明（2010年11月第1版）--2010-10-29定稿.pdf
http://download.swansc.com/PDF/SINUMERIK.pdf
https://www.chncit.com.cn/chncit/2024/08/01/jn-nv900三菱皮带8000转.pdf
```

> 第 1、2 份是**数控系统**手册，不是 VMC850 整机手册。文件名加 `VMC850_` 前缀，
> 或在 `manifest.csv` 里指定 `device_model=VMC850`，否则型号过滤失效（会被归到"未识别"）。

---

## 四、三相异步电机（YE3-160M）

放入 `data/manuals/motor/`

| # | 文档 | 建议文件名 | 实测（页/正文/表/图） | 判定 |
| --- | --- | --- | --- | --- |
| 1 | YE3 系列三相异步电动机 样本（皖南电机） | `YE3_皖南_样本.pdf` | 16 / 44 / 19 / 12 | ✅ 参数表 + 结构图最全 |
| 2 | YE3 系列超高效率三相异步电动机 样本 | `YE3_样本_2.pdf` | 9 / 21 / 11 / 6 | ✅ 补充 |
| 3 | YBX3 隔爆型三相异步电动机 使用说明书 | `YE3_YBX3_使用说明书.pdf` | 12 / 33 / 6 / 5 | ✅ 使用维护章节 |
| 4 | YXKK/YKK 系列高压三相异步电动机 说明书 | `YE3_高压电机_说明书.pdf` | 17 / 50 / 7 / 0 | ✅ 检修条目多 |
| 5 | YE5 系列三相异步电动机（团标） | `YE3_YE5_团标.pdf` | 27 / 70 / 26 / 3 | ✅ 表格最丰富 |

链接：

```
https://www.wnmotor.com/UploadFiles/File/2021-05/6375809677746967063135743.pdf
http://ahwnm.com/upload/file/20150325/20150325135719351935.pdf
https://www.donly.com.cn/static/upload/file/20250123/1737608641864963.pdf
http://www.huanengdj.com/file/p1zj5thknj.pdf
https://www.ttbz.org.cn/upload/file/20230830/6382900107894929446118959.pdf
```

> 注意：文件夹名 `motor` **不含**设备型号别名，所以文件名必须带 `YE3` 或 `160M`，
> 否则 `eq-ingest` 会把 `device_model` 置空、型号过滤失效。

---

## 五、一键下载（PowerShell）

在项目根目录执行，自动落到对应目录并改成规范文件名：

```powershell
$dl = {
  param($url, $out)
  Write-Host "↓ $out"
  try {
    Invoke-WebRequest -Uri $url -OutFile $out -TimeoutSec 180 -Headers @{ "User-Agent" = "Mozilla/5.0" }
  } catch { Write-Host "  ✗ 失败：$($_.Exception.Message)" -ForegroundColor Yellow }
}

New-Item -ItemType Directory -Force -Path data/manuals/ga55, data/manuals/vmc850, data/manuals/motor | Out-Null

& $dl "https://jahancompressor.com/wp-content/uploads/2025/10/Atlas-Copco-GA75-1759661915.1284.pdf" "data/manuals/ga55/GA55_instruction_book_en.pdf"
& $dl "https://data2.manualslib.com/cpdf/16/80/7977/484ca6.pdf" "data/manuals/ga55/GA55_user_manual.pdf"
& $dl "https://www.ttbz.org.cn/upload/file/20241122/6386791256391624113747184.pdf" "data/manuals/ga55/GA55_维护保养规范_团标.pdf"
& $dl "https://www.ttbz.org.cn/upload/file/20241111/6386693417731008897372167.pdf" "data/manuals/ga55/单螺杆_变频喷水_团标.pdf"

& $dl "http://download.swansc.com/PDF/SINUMERIK.pdf" "data/manuals/vmc850/VMC850_SINUMERIK_系统手册.pdf"
& $dl "https://www.chncit.com.cn/chncit/2024/08/01/jn-nv900三菱皮带8000转.pdf" "data/manuals/vmc850/VMC850_JN-NV900_样本.pdf"
# GSK 的 URL 含中文与空格，用 check_manual.py 下更稳（它会自动编码）：
uv run python scripts/check_manual.py "https://www.gsk.com.cn/uploadfiles/网站说明书/cnc/研发四室/983ma中文/GSK983M系列加工中心数控系统 PLC使用说明（2010年11月第1版）--2010-10-29定稿.pdf"

& $dl "https://www.wnmotor.com/UploadFiles/File/2021-05/6375809677746967063135743.pdf" "data/manuals/motor/YE3_皖南_样本.pdf"
& $dl "http://ahwnm.com/upload/file/20150325/20150325135719351935.pdf" "data/manuals/motor/YE3_样本_2.pdf"
& $dl "https://www.donly.com.cn/static/upload/file/20250123/1737608641864963.pdf" "data/manuals/motor/YE3_YBX3_使用说明书.pdf"
& $dl "http://www.huanengdj.com/file/p1zj5thknj.pdf" "data/manuals/motor/YE3_高压电机_说明书.pdf"
& $dl "https://www.ttbz.org.cn/upload/file/20230830/6382900107894929446118959.pdf" "data/manuals/motor/YE3_YE5_团标.pdf"
```

`check_manual.py` 会把文件下到 `data/manuals/_probe/`，体检通过后手动挪进对应目录并改名。

---

## 六、下载后自检（必做）

```powershell
# 单份体检
uv run python scripts/check_manual.py data/manuals/ga55/GA55_instruction_book_en.pdf

# 全量入库后看分布
uv run eq-ingest --no-vlm
uv run python -c "import json,collections;rows=[json.loads(l) for l in open('data/index/chunks.jsonl',encoding='utf-8')];print(len(rows));print(collections.Counter(r['block_type'] for r in rows));print(collections.Counter(r['device_model'] or '未识别' for r in rows))"
```

通过标准：`block_type` 三类都有；`device_model` 无"未识别"（有就补 manifest 或改文件名）。

---

## 七、已排除的来源（别再浪费时间）

| 站点 | 原因 |
| --- | --- |
| 百度文库 / 道客巴巴 / 原创力文档(book118) / 豆丁 / 人人文库 | 需登录或付费，无法批量下载，且多数禁止转载 |
| manualslib 网页版 | 网页需注册；只有其 `data2.manualslib.com/cpdf/...pdf` 直连可取 |
| 各类政府采购招标文件 | 搜"手册"时噪声极大，正文无用 |

搜索技巧：百度直接加 `filetype:pdf`，并把 `wenku/doc88/book118/docin` 的结果过滤掉；
命中教育机构（`.edu.cn`）、团体标准平台（`ttbz.org.cn`）、厂商官网的 PDF 质量最高。

---

## 八、下载记录（自己填）

| 日期 | 文件名 | 页 | 正文 | 表 | 图 | 结论 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-11-19 | （示例）GA55_instruction_book_en.pdf | 145 | 575 | 140 | 51 | ✅ | 英文，表格图纸齐全 |
