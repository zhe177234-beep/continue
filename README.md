# 智学 · 个性化学习知识系统

智能科学与技术本科毕设工程项目，v0.4。提供资料入库、带原文出处问答、社区 GraphRAG、自主多 Agent、练习与学习统计。

**当前实现：Vue 3 + Spring Boot API 网关 + FastAPI + SQLite + 可选 Ollama。** Spring Boot 负责入口转发与请求边界；Python 服务管理业务、GraphRAG 和自主任务。已实现分层社区报告式 GraphRAG 的索引、局部查询和全局 Map-Reduce，以及可重新规划的多 Agent 协作。PostgreSQL/pgvector、图表语义和高级认知诊断仍属于后续扩展。

## 功能

- 账号注册、登录、退出；scrypt 密码哈希、服务端会话、HttpOnly Cookie；知识库按账号隔离。
- 每个账号创建多个知识库，上传 TXT/MD、文本或扫描 PDF、DOCX/PPTX；启用 OCR 后支持 PNG/JPG 文字识别。
- 文件大小与解压大小限制、SHA256 去重、分块持久化、文档原始页码或幻灯片编号。
- BM25、词频余弦、RRF 混合检索、知识关系两跳增强和关键词规则路由。
- 可选 Ollama 语义向量索引及生成回答；模型失败或引用编号无效时回退到原文摘录。
- 多轮对话、新建对话、问答历史；原文校验的模型关系提取与后台任务状态。
- GraphRAG：实体归一化和向量索引、Louvain 分层社区、带原文的社区报告、局部实体扩展与全局社区 Map-Reduce。无关系的资料也纳入社区。
- 自主多 Agent：规划者按目标选择资料、图谱或学习记录工具；回答者生成，独立审查者核对证据，反馈驱动再次检索。任务持久化、进度可见、可停止，设轮数、模型调用和时间预算。
- 单选、多选、判断、对象填空、关键词评分简答；错题本、Beta 平滑正确率与前置知识复习顺序。
- Docker 三服务启动、Windows/macOS/Linux 启动脚本、接口与算法说明、自动测试和 GitHub Actions。

## 前端与学习卡片

学习工作台已优化桌面与手机布局，并集成 GrapesJS 可视化学习卡片。支持拖拽、样式调整、设备预览、浏览器草稿和独立 HTML 导出。草稿仅保存在当前浏览器。使用与扩展见 [前端说明](docs/FRONTEND.md)。

## 电脑上运行：推荐 Docker

安装 Git 与 Docker Desktop，并先启动 Docker Desktop。在终端执行：

```bash
git clone https://github.com/zhe177234-beep/continue.git
cd continue
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

macOS / Linux：

```bash
bash scripts/start.sh
```

脚本复制 `.env.example` 为 `.env`、校验 Compose、构建并启动服务、等待健康检查。打开 **http://localhost:8080**，点击“首次使用？创建账号”，建立知识库，上传 `datasets/machine-learning.md`。提问“学习率如何影响梯度下降？”，再到练习页生成题目。

首次构建需要下载基础镜像和依赖；网络环境会影响耗时。默认不下载大模型，离线摘录、练习和学习统计均可使用。网页只绑定本机回环地址，不能直接从其他电脑访问。

## 可选：本地模型

Windows 一次下载模型并启动：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-models.ps1
```

macOS/Linux：`bash scripts/setup-models.sh`。默认下载 qwen3:0.6b 与 qwen3-embedding:0.6b；真实生成、向量检索和自动关系提取已通过 GitHub 云端测试。脚本保留 `.env.before-models` 配置备份，写入模型名后启动全部应用；模型下载失败会停止并明确提示。

上传后点击“更新语义索引”；在“知识关系”页可以自动抽取关系，任务进度显示在左侧。更换向量模型后需要重建索引。Ollama 没有公网端口，默认 CPU 推理；轻量模型可跑通接口，但领域回答质量需评测，引用编号校验不保证事实正确。

完整明天操作见 [最短操作指南](docs/TOMORROW.md)。模型信息来自 [Ollama qwen3](https://ollama.com/library/qwen3) 和 [qwen3-embedding](https://ollama.com/library/qwen3-embedding)。

## GraphRAG 与自主任务

在“知识关系”页点击“构建 GraphRAG”，等待后台任务完成，然后在问答页选择“GraphRAG 局部检索”或“GraphRAG 全局汇总”。全局汇总在后台逐个扫描所选层级的社区报告，完成后自动显示答案。

在“自主任务”页描述学习目标并启动。规划 Agent 选择当前知识库中的检索工具，回答 Agent 与审查 Agent 协作；证据不足时继续查找，无法通过审查时返回原文供人工核对。GraphRAG 未构建时仍可使用资料和学习记录工具。多个角色默认共用同一个本地模型，使用各自独立的提示和结构化输出。

本项目实现自己的 GraphRAG 工作流，采用 Louvain 分层社区，未集成微软官方 GraphRAG 全部组件或其 Leiden/DRIFT 模式。完整说明见 [GraphRAG 与 Agent 指南](docs/GRAPHRAG-AGENTS.md)。

## 不使用 Docker 的开发方式

需要 Python 3.12、Node 24；若使用 Java 网关，还需 JDK 17 与 Maven 3.9。

终端一（项目根目录）：

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn api:app --app-dir ai-service --host 127.0.0.1 --port 8000
```

终端二：

```bash
cd web
npm ci
npm run dev
```

打开 http://127.0.0.1:5173 。开发代理默认直接连接 AI 服务。API 文档：http://127.0.0.1:8000/docs 。非 Docker 方式默认关闭 OCR；启用时需要 Tesseract、chi_sim/eng 语言包，扫描 PDF 还需要 Poppler 的 pdftoppm。生成模型默认 URL 为本机 `http://127.0.0.1:11434`。

Java 网关单独运行：`mvn -f server/pom.xml package`，然后 `java -jar server/target/learning-gateway-0.3.0.jar`。入口端口 8081；设置前端环境变量 `API_TARGET=http://127.0.0.1:8081` 后重新启动 Vite，可经网关访问。

## 测试

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q tests
python ai-service/evaluate.py
mvn -f server/pom.xml test
cd web
npm ci
npm run build
npx playwright install chromium
npx playwright test
```

已启动 Docker 后，运行 `python scripts/smoke.py` 验证整条服务链路。它创建独立测试账号和知识库，验证上传、引用、练习、统计与退出；不修改你的知识库。详细验证状态见 `docs/VERIFICATION.md`，不要将未运行的容器或真实模型检查当作已通过。

## 数据与维护

- Docker 数据保存在 `knowledge-data` 命名卷；非 Docker 在 `data/v2`。
- `docker compose down` 保留数据；`docker compose down -v` 删除全部命名卷，包括模型数据。
- 删除资料会清理该资料的练习、索引，并清空当前知识库的问答历史，避免保留已经失效的引用。
- 停止服务后备份整个数据目录/卷；账号表和知识库索引需要一起备份。
- v0.1 的单库 `data/knowledge.db` 不自动迁移；请在新账号中重新上传资料，旧文件不会被启动脚本删除。

## 工程边界

单文件 10 MiB（10,485,760 字节），PDF/PPT 最多 100 页，每个知识库最多 2000 个片段，每账号最多 20 个知识库。自动关系提取处理全部片段，受任务时间预算限制。解析后文本最多 100 万字符、Office 解压内容最多 25 MiB，这些独立保护仍然保留。DOCX 不保留原始分页。扫描 PDF 最多 OCR 20 页；图表/公式语义理解尚未支持。

知识关系来自显式三元组或经原文校验的模型提取，谓词含义仍需复核。复习顺序结合前置关系与平滑正确率；简答评分仍仅检查关键词覆盖。向量以 SQLite JSON 持久化，查询时计算精确余弦，未采用 pgvector。自主 Agent 的工具限定在当前知识库的只读检索和学习记录，不执行电脑命令或访问其他账号。证据审查不能保证事实正确。

部署默认用于本机和本科项目演示。公网部署需另行配置 HTTPS、关闭公开注册、设置安全 Cookie、网关限流、独立解析工作进程与数据库迁移。默认账号不存在，必须注册。

进一步说明：[接口](docs/API.md)、[架构与论文实验](docs/ARCHITECTURE.md)、[部署排查](docs/DEPLOYMENT.md)。
