# 智学 · 个性化学习知识系统

智能科学与技术本科毕设工程项目，v0.2。提供资料入库、带原文出处问答、知识关系练习、错题与学习统计的完整应用流程。

**当前实现：Vue 3 + Spring Boot API 网关 + FastAPI + SQLite + 可选 Ollama。** Spring Boot 负责入口转发与请求边界；账号、知识库和学习业务暂由 Python 服务持久化。PostgreSQL/pgvector、完整 GraphRAG、自动实体抽取和自主 Agent 尚未实现，不能把本版当作原始规划的全部终版。

## 功能

- 账号注册、登录、退出；scrypt 密码哈希、服务端会话、HttpOnly Cookie；知识库按账号隔离。
- 每个账号创建多个知识库，上传 TXT/MD、文本型 PDF、DOCX/PPTX；启用 OCR 后支持 PNG/JPG 文字识别。
- 文件大小与解压大小限制、SHA256 去重、分块持久化、文档原始页码或幻灯片编号。
- BM25、词频余弦、RRF 混合检索、显式关系一跳增强和关键词规则路由。
- 可选 Ollama 语义向量索引及生成回答；模型失败或引用编号无效时回退到原文摘录。
- 问答历史、关系选择题、自动批改、错题本、Beta 平滑正确率与复习优先级。
- Docker 三服务启动、Windows/macOS/Linux 启动脚本、接口与算法说明、自动测试和 GitHub Actions。

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

默认 CHAT_MODEL 与 EMBEDDING_MODEL 为空，不调用模型。可启动容器内 Ollama：

```bash
docker compose --profile models up -d ollama
docker compose exec ollama ollama pull <你的聊天模型名称>
docker compose exec ollama ollama pull <你的向量模型名称>
```

把 `.env` 中两个模型变量填为已下载的确切名称，再运行 `docker compose up -d ai`。在网页上传资料后点击“更新语义索引”。模型变更后必须重新建立索引。

Ollama 不映射到公网端口。默认 CPU 推理；GPU 需自行配置 Compose 的设备映射。模型大小、中文能力和运行资源取决于所选模型。实际模型推理尚未在当前开发环境验证；传输契约与失败降级通过测试替身验证。不要将引用编号校验理解为事实验证。

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

打开 http://127.0.0.1:5173 。开发代理默认直接连接 AI 服务。API 文档：http://127.0.0.1:8000/docs 。非 Docker 方式默认关闭图片 OCR；启用时需要 Tesseract 和语言包。生成模型默认 URL 为本机 `http://127.0.0.1:11434`。

Java 网关单独运行：`mvn -f server/pom.xml package`，然后 `java -jar server/target/learning-gateway-0.2.0.jar`。入口端口 8081；设置前端环境变量 `API_TARGET=http://127.0.0.1:8081` 后重新启动 Vite，可经网关访问。

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

单文件 3 MiB，PDF/PPT 最多 100 页，每个知识库最多 2000 个片段，每账号最多 20 个知识库。DOCX 不保留原始分页，页码固定为 1。扫描 PDF、图片中的图表/公式语义理解尚未支持；图片 OCR 仅提取文字。

知识关系来自显式三元组，不是自动抽取；复习顺序按平滑正确率排序，不是认知诊断或前置知识推理。向量以 SQLite JSON 持久化，查询时进行精确余弦计算，未采用 pgvector 或近似索引。没有多 Agent 自主执行。

部署默认用于本机和本科项目演示。公网部署需另行配置 HTTPS、关闭公开注册、设置安全 Cookie、网关限流、独立解析工作进程与数据库迁移。默认账号不存在，必须注册。

进一步说明：[接口](docs/API.md)、[架构与论文实验](docs/ARCHITECTURE.md)、[部署排查](docs/DEPLOYMENT.md)。
