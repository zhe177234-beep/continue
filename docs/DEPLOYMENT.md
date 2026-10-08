# 电脑部署与故障排查

## Windows

安装 Git 与 Docker Desktop（按其安装器要求启用 WSL2/虚拟化），打开 Docker Desktop 等待引擎运行。克隆仓库后在项目根目录运行 `powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1`。该设置仅用于本次子进程，不修改全局策略。脚本打开 http://localhost:8080 。若自定义 WEB_PORT，将访问地址改为该端口。

## 手动部署

复制 `.env.example` 为 `.env`，再执行 `docker compose config --quiet`、`docker compose up --build -d`。查看 `docker compose ps` 与 `docker compose logs --tail=100`。仅 web 映射本机端口，gateway/ai/Ollama 均在容器网络内。

| 现象 | 排查 |
| --- | --- |
| 找不到 docker / 引擎连接失败 | 安装 Docker Desktop，并确认引擎已启动 |
| 镜像、pip 或 Maven 下载失败 | 检查电脑网络、Docker 代理设置；重新运行构建，不要跳过测试掩盖失败 |
| 8080 被占用 | 在 .env 设置 WEB_PORT=8082 后重建，访问 localhost:8082 |
| 网页打开但接口失败 | 查看 gateway 与 ai 日志；确认 /api/health 为 ok |
| 文档入库失败 | 单文件≤3 MiB，文本为 UTF-8，PDF≤100 页且含文本，不支持扫描 PDF |
| OCR 失败 | 图片需启用 ENABLE_OCR；非 Docker 方式需要 Tesseract 与 chi_sim/eng 语言包 |
| 语义索引返回 503 | 确认模型容器启动、模型已下载、EMBEDDING_MODEL 名称正确且内存足够 |
| 提示降级为原文 | 模型未配置、不可达、推理失败或生成引用不合格；查看模型日志 |
| 切换模型后结果异常 | 点击更新语义索引，旧模型向量不会作为当前模型索引使用 |

## 备份和恢复

先停止服务，再备份 knowledge-data 卷或整个 data/v2 目录。账号表与知识库索引必须一起备份。不要在服务持续写入时直接复制数据库；恢复前先保留现有数据副本。`docker compose down` 不删卷；加 `-v` 会删除数据库和模型卷。

## 验证和公网边界

安装开发依赖后运行 `python scripts/smoke.py --url http://localhost:8080`。它会新增独立测试账号及空知识库，测试文档完成后会删除；测试账号不会自动删除。

默认配置针对电脑本机运行。云端公网部署尚未在本次任务执行：需 HTTPS 反向代理、安全 Cookie、注册策略、网关限流、独立解析工作进程及备份方案。服务端 SQLite 当前适合小规模演示，并非大并发生产架构。
