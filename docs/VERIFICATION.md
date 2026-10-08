# v0.2 验证记录

验证时间：2026-10-08。测试在开发容器中执行，不是在用户电脑执行。

| 检查 | 实际结果 |
| --- | --- |
| Python API / 检索 / 解析测试 | 14 项通过，无跳过；包含真实 PDF 页码、DOCX/PPTX、英文图片 OCR、并发去重、账号隔离、模型替身与故障降级 |
| Spring Boot 单元测试 | 3 项通过，验证请求体、Cookie、状态转发、跨站拒绝与上游故障 |
| Java 打包 | Maven package 成功，生成可执行 JAR |
| Vue 生产构建 | npm run build 成功 |
| 浏览器流程 | Chromium 中 1 条完整流程通过：注册、建库、上传、出处问答、练习、学习记录、退出；未捕获前端运行异常 |
| Java + AI 实际链路 | smoke.py 通过：健康、登录、multipart 上传、引用、出题、评分、统计、删除与退出 |
| 检索实验脚本 | 3 条人工问题、5 种离线模式运行成功，仅为冒烟检查 |
| npm audit | 检查时报告 0 个已知漏洞，不能保证不存在未披露问题 |
| Compose YAML / Bash | YAML 结构检查及 bash -n 通过 |
| Docker 镜像 / Compose 实际启动 | 开发环境无 Docker，尚未运行；CI 已配置 docker-smoke 作业 |
| PowerShell 启动脚本 | 已编写，当前 Linux 环境未实际执行 |
| 中文 OCR | 容器配置安装 chi_sim 语言包；本地实测仅英文，中文效果未实测 |
| 真实 Ollama 推理 | 未下载或运行真实模型；向量格式、引用编号、传输接口与故障降级通过替身测试 |

真实链路测试发现并修复网关提前消费 multipart 上传内容的问题：关闭 Spring 的 multipart 解析，由 AI 服务解析原始上传。浏览器测试发现并修复退出后仍处于注册模式的问题。

浏览器 CDN 在当前环境不可访问，使用独立 Chromium 可执行文件完成本地验证；仓库 Playwright 配置支持 CHROMIUM_PATH，同时保留正常的 Playwright 浏览器安装方式用于 CI 与用户电脑。

GitHub CI 结果以 Actions 页面为准；提交配置不代表云端 CI 已执行通过。Docker、PowerShell 和真实模型检查未通过本地实测，不应描述为“全部部署完成”。
