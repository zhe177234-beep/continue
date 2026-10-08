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
| Windows PowerShell | 新增 Windows CI：解析并以 Docker/网络替身运行配置与启动逻辑；不等于 Windows 容器实际部署，最终结果以 Actions 为准 |
| 中文 OCR 效果 | Docker 安装 chi_sim；当前效果测试为英文，中文识别准确率未评测 |

已通过的云端代码检查：`dd3b51d7b691cdd39efce0b14510f0dd85277c0f`，运行 https://github.com/zhe177234-beep/continue/actions/runs/37809933336 （test、docker-smoke、real-model 全部 success）。简答、前置路径和扩展浏览器检查在后续提交再次验证，结果以对应 Actions 为准。

真实模型检查只证明连通性、向量检索和输出契约，不证明教学回答或知识关系的领域正确率。轻量模型可能回答不佳，系统会在模型异常或引用无效时降级到原文摘录。自动关系校验实体及原文摘录，无法自动证明谓词含义正确。

后台任务使用一个有界线程队列，状态持久化；重启时将中断任务标记失败，可重新执行。不是分布式队列。当前部署使用单个 AI 服务进程，不支持以多 worker 同时管理该队列。

浏览器 CDN 在当前开发网络无法使用正常安装路径，本地通过 CHROMIUM_PATH 指向独立 Chromium 验证；GitHub CI 使用正常 Playwright 下载。当前库依赖的 FastAPI TestClient 提示 httpx 的弃用警告，测试仍通过。
