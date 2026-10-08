# 智学 · 个性化学习知识系统

智能科学与技术本科毕设工程项目，v0.3。提供资料入库、带原文出处问答、知识关系练习、错题与学习统计的完整应用流程。

**当前实现：Vue 3 + Spring Boot API 网关 + FastAPI + SQLite + 可选 Ollama。** Spring Boot 负责入口转发与请求边界；账号、知识库和学习业务暂由 Python 服务持久化。PostgreSQL/pgvector、社区摘要式完整 GraphRAG 和自主 Agent 尚未实现，不能把本版当作原始规划的全部终版。

## 功能

- 账号注册、登录、退出；scrypt 密码哈希、服务端会话、HttpOnly Cookie；知识库按账号隔离。
- 每个账号创建多个知识库，上传 TXT/MD、文本或扫描 PDF、DOCX/PPTX；启用 OCR 后支持 PNG/JPG 文字识别。
- 文件大小与解压大小限制、SHA256 去重、分块持久化、文档原始页码或幻灯片编号。
- BM25、词频余弦、RRF 混合检索、知识关系两跳增强和关键词规则路由。
- 可选 Ollama 语义向量索引及生成回答；模型失败或引用编号无效时回退到原文摘录。
- 多轮对话、新建对话、问答历史；原文校验的模型关系提取与后台任务状态。
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

单文件 3 MiB，PDF/PPT 最多 100 页，每个知识库最多 2000 个片段，每账号最多 20 个知识库。自动关系抽取每次最多 100 片段，更多资料请拆分知识库。DOCX 不保留原始分页，页码固定为 1。扫描 PDF 可对最多 20 个无文本页执行 OCR；图表/公式语义理解尚未支持，OCR 仅提取文字。

知识关系来自显式三元组或经原文校验的模型提取，谓词含义仍需复核。复习顺序结合已识别的前置关系与平滑正确率；简答评分仅检查关键词覆盖，不判断逻辑与同义表述。向量以 SQLite JSON 持久化，查询时进行精确余弦计算，未采用 pgvector 或近似索引。没有多 Agent 自主执行。

部署默认用于本机和本科项目演示。公网部署需另行配置 HTTPS、关闭公开注册、设置安全 Cookie、网关限流、独立解析工作进程与数据库迁移。默认账号不存在，必须注册。

进一步说明：[接口](docs/API.md)、[架构与论文实验](docs/ARCHITECTURE.md)、[部署排查](docs/DEPLOYMENT.md)。
