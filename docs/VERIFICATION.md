# 100 MiB / 1000 页本机容量调整

验证日期：2026-10-09（北京时间）。按用户要求只更新本机，不上传 GitHub；下方历史云端记录不代表这次容量调整。

- 单文件上限 104,857,600 字节，文字 PDF/PPT 最多 1000 页；用户选择保留扫描 PDF 最多 OCR 20 页。
- 前端、Nginx、Java 网关及 Python 解析器均已更新，Docker 容器已重建并运行。健康接口的 limits 返回当前字节数、文档页数和 OCR 页数。
- 36 项 Python 测试、4 项 Java 测试、6 条生产浏览器流程通过，无跳过；包含客户端超限拒绝、解析与入库边界检查。
- 完整 Nginx → Java → FastAPI 链路实测：恰好 100 MiB DOCX 入库成功，增加 1 字节被拒绝；真实 1000 页 PDF 与 1000 页 PPTX 入库成功，均能检索第 1000 页出处；1001 页文件均被拒绝。
- 原有注册、上传、问答、练习、学习统计、删除与退出链路通过。原有知识库及模型卷保留，测试使用独立账号并删除测试资料。
- 配套安全上限为 1000 万文本字符、每库 20,000 分块、Office 解压 250 MiB / 50,000 条目。页面上限不是无限文本或不限内存承诺，GraphRAG 的模型调用与时间预算不变。

复测命令（先安装 requirements-dev.txt；后三项针对已运行的本机服务）：

```bash
python -m pytest -q tests
python scripts/upload_limit_smoke.py
python scripts/document_limit_smoke.py
python scripts/smoke.py
```

# v0.4 本机验证记录

验证日期：2026-10-09（北京时间）；实际环境为用户的 Windows 电脑和 Docker Desktop，项目在 `D:\王爱哲\GitHub\continue`。

| 检查 | 实际结果 |
| --- | --- |
| Python | 32 项通过，无跳过；新增社区层级、全库覆盖、失效索引、并发变更、原子发布、模型调用预算、动态重新规划、证据拒绝、任务停止、账号隔离及 10 MiB 边界检查 |
| Java | 4 项通过，无失败或跳过；含 10 MiB 文件所需的 multipart 请求空间及超限拒绝 |
| 前端 | 生产构建通过；5 条 Chromium 流程通过，包含学习流程、GrapesJS、社区报告/异步全局答案、自主任务进度/停止/结果和手机布局 |
| Docker | 本机四服务运行，健康接口返回 0.4.0；完整注册、上传、问答、批改、学习统计、删除与退出链路通过 |
| 上传上限 | 经实际 Nginx → Java → FastAPI 链路，10,485,760 字节 DOCX 入库成功，增加 1 字节被拒绝；解压大小和文本长度限制独立保留 |
| 真实模型 | qwen3:0.6b / qwen3-embedding:0.6b 的 1024 维向量、语义 Top1、关系抽取、社区报告、全局 Map-Reduce 和自主任务通过；真实部署测试还覆盖局部 GraphRAG 查询及证据审查完成 |
| Windows 脚本 | Windows PowerShell 5 与 PowerShell 7 的语法、配置备份、模型更换和启动逻辑测试通过；这些脚本测试使用替身，实际容器部署另行实测 |
| 资料保留 | 应用重新构建后保留原有知识库和模型命名卷；验证使用独立账号并清理测试资料 |

前端新增社区和 Agent 测试模拟长耗时模型任务接口，以稳定验证交互；真实模型验证通过独立后端与已部署服务脚本完成，不能将前端接口替身测试当作模型准确率评测。桌面与 390 像素手机截图已人工复查。

真实模型初次复测中，全局答案曾缺少引用，系统按设计退回原文；强化引用提示后复测生成契约通过。小模型即使合法引用，也可能漏答主题或产生不准确概括。通过上述测试仅证明工作流、权限、预算和输出契约，不保证领域事实正确，不是效果基准。GraphRAG 为本项目基于 Louvain 的社区报告实现，不是微软官方全部组件；Agent 仅执行当前知识库中的只读工具。

本节记录本机实测，云端 CI 以对应提交的 GitHub Actions 状态为准。以下保留历史版本验证记录，不代表本次新增代码已获云端验证。

# v0.3 验证记录

验证日期：2026-10-08 UTC（中国时间 10 月 9 日）。以下测试运行在开发环境和 GitHub 云端，未在用户电脑运行。

| 检查 | 实际结果 |
| --- | --- |
| Python | 最新本地 20 项通过，无跳过；含账号隔离、解析、并发去重、多轮对话隔离、后台任务、自动关系原文校验、两跳检索、五种题型、前置排序与循环处理 |
| Vue 构建 | 生产构建通过 |
| 浏览器 | 完整流程通过；覆盖注册、上传、出处、追问、新对话、五种题型、学习记录、退出，无前端运行异常 |
| 图片与扫描 PDF | 真实英文图片 OCR 和扫描 PDF OCR 通过；PDF OCR 保留页码 |
| Java | GitHub test 任务完成 Maven package 与 3 项网关测试 |
| Docker | GitHub docker-smoke 实际构建并启动三服务，完整上传、问答、练习、删除链路通过 |
| 真实模型 | GitHub real-model 实际下载并运行 qwen3:0.6b 和 qwen3-embedding:0.6b；2 条 1024 维向量成功入库，语义 Top1 命中正确资料，生成回答含合法引用，自动提取 2 条通过原文校验的关系 |
| 算法评估 | 3 条人工问题、5 种离线模式运行成功；只用于冒烟检查，不可作为论文效果结论 |
| Bash | start.sh 与 setup-models.sh 语法检查通过 |
| Windows PowerShell | Windows GitHub runner 通过语法解析、模型配置备份、模型更换与启动逻辑检查；Docker/网络/浏览器为替身，不等于 Windows 容器实际部署 |
| 中文 OCR 效果 | Docker 安装 chi_sim；当前效果测试为英文，中文识别准确率未评测 |

已通过的云端代码检查：`dd3b51d7b691cdd39efce0b14510f0dd85277c0f`，运行 https://github.com/zhe177234-beep/continue/actions/runs/37809933336 （test、docker-smoke、real-model 全部 success）。最终代码提交 `3d11b150fa1a30bad83ae101cdcba75c2f762f0a` 再次通过 https://github.com/zhe177234-beep/continue/actions/runs/37810890911 ：test、docker-smoke、real-model、windows-scripts 四项全部 success；包含 20 项 Python 测试、3 项 Java 测试与五题型浏览器流程。后续提交仅记录验证结果。

真实模型检查只证明连通性、向量检索和输出契约，不证明教学回答或知识关系的领域正确率。轻量模型可能回答不佳，系统会在模型异常或引用无效时降级到原文摘录。自动关系校验实体及原文摘录，无法自动证明谓词含义正确。

后台任务使用一个有界线程队列，状态持久化；重启时将中断任务标记失败，可重新执行。不是分布式队列。当前部署使用单个 AI 服务进程，不支持以多 worker 同时管理该队列。

浏览器 CDN 在当前开发网络无法使用正常安装路径，本地通过 CHROMIUM_PATH 指向独立 Chromium 验证；GitHub CI 使用正常 Playwright 下载。当前库依赖的 FastAPI TestClient 提示 httpx 的弃用警告，测试仍通过。


# GrapesJS 前端优化验证

## 2026-10-10 高级工作台与上传容量合并验证

MagicPath 设计预览构建成功，截图复查后修复预览中文字体；Vue 生产构建成功。Windows 隔离 Python 3.12 环境运行 36 项测试：34 通过，2 项 OCR 实机检查因缺少 OCR 工具跳过，不记为通过。

本地 Chromium 开发模式与生产构建预览分别通过 7 条流程：GraphRAG 社区与异步全局回答、Agent 进度/停止/出处、工作台真实统计与响应式导航、GrapesJS 拖拽/草稿/设备/导出、100 MiB 前端拦截、手机关系筛选/编辑器、完整学习流程。工作台检查覆盖 1440、1024、850、390、320 像素宽度，无文档横向溢出。本轮独立 FastAPI 环境也通过真实 1000 页 PDF/PPTX 上传、最后一页出处检索及 1001 页拒绝检查；这项本地检查未经过 Java/Nginx。

本轮本机 Docker 引擎不可连接，未在本机重复确认容器链路或真实模型；GitHub CI 保留独立 Docker、模型与 Windows 脚本检查，并新增真实 1000/1001 页 PDF/PPTX 上传边界验证。云端结果需按本轮运行状态另行确认，不能套用旧提交的成功结果。

云端代码提交 `9eab5110b063e57d57f02c13f376bff94cf85cfc` 已通过本轮 [GitHub 检查](https://github.com/zhe177234-beep/continue/actions/runs/38008054008)：test、docker-smoke、real-model、windows-scripts 四项均 success。Docker 日志确认精确 100 MiB DOCX 接受、超出 1 字节拒绝，真实 1000 页 PDF/PPTX 上传及末页引用成功，1001 页均拒绝；Java 4 项测试无失败或跳过，浏览器 7 项通过。真实模型检查实际运行 qwen3:0.6b 与 qwen3-embedding:0.6b，不代表教学质量已经评测。前端生产依赖审计本轮报告 0 个已知漏洞。之后的提交若仅记录结果，不代表又运行过代码检查。


代码提交：`ea5fde623ae39028be5d8967b1100a145bc511d3`。云端运行：https://github.com/zhe177234-beep/continue/actions/runs/37824638576 ，test、docker-smoke、real-model、windows-scripts 四项全部 success。

本地开发模式与生产构建预览分别通过三条 Chromium 流程：完整学习流程、GrapesJS 拖拽/文字编辑/撤销重做/设备切换/草稿恢复/原文插入/HTML 导出、手机布局/关系筛选/键盘插入。编辑器检查应用 CSP；手机视口 390×844，无文档横向溢出。生产构建成功；npm audit --omit=dev 检查时为 0 个已知漏洞。

截图复查发现并修复中文画布字体与组件标签字体问题；画布复用应用字体规则，并将中文字体置于字体列表首位。设备切换测试等待画布尺寸稳定后再验证真实拖拽，避免动画和字体加载导致坐标不稳定。

GrapesJS 为按需加载的较大依赖，构建会报告单块大小提示；主入口约 98.5 kB，编辑器包约 1.14 MB（gzip 约 308 kB），只有进入学习卡片时加载。字体文件未包含在导出 HTML 中，导出页面使用系统字体回退。

说明与实测截图见 [FRONTEND.md](FRONTEND.md)。草稿仅在当前浏览器保存，不跨设备同步。验证不代表所有浏览器或用户电脑的实际启动已经确认。后续提交仅记录测试结果。
