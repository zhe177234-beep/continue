# 智学：可追溯的学习知识系统

智能科学与技术本科毕设的第一阶段工程基线。研究题目：**基于知识图谱增强检索的个性化学习知识系统设计与实现**。

当前版本 v0.1 已实现一个本地可运行的资料检索闭环；不是完整毕设终版。

## 已实现

- TXT、Markdown、文本型 PDF 上传，UTF-8 校验、文件大小限制及内容去重。
- SQLite 持久化，按页切分，保存文档、页码及片段 ID；删除资料时级联删除索引与关系。
- BM25、词频余弦、RRF 混合检索与显式知识关系的一跳增强，支持规则式自动路由。
- 原文证据摘录与出处显示，相关性不足时提示补充资料。
- 网页资料管理、检索模式选择与知识关系列表。
- 本地运行、Docker Compose 配置、接口测试与小型检索实验脚本。

**算法边界：**词频向量不是语义 Embedding；关系由资料中明确的三元组读取，不是大模型自动抽取。问答是原文摘录，不是大模型生成，也不是完整 GraphRAG。相关性阈值不能保证事实正确。

## 运行（推荐先使用本地方式）

需要 Python 3.12 或更高版本。在项目根目录执行：

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell 使用：.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python ai-service/app.py
```

打开 http://127.0.0.1:8000 。上传 `datasets/machine-learning.md`，输入“学习率如何影响梯度下降？”或“梯度下降和学习率有什么关系？”。默认无需令牌，数据库保存在 `data/knowledge.db`。TXT/MD 路径无需安装第三方依赖；PDF 需要 pypdf。扫描 PDF、OCR、Word/PPT 当前未支持。

## Docker

先创建 `.env`，写入 `APP_TOKEN=你生成的至少16字符随机令牌`（不要提交该文件），然后运行：

```bash
docker compose up --build -d
docker compose logs -f
```

打开同一个本地地址，将令牌输入页面的“访问令牌”字段，点击刷新连接。SQLite 数据保存在命名卷中。`docker compose down` 保留数据，`docker compose down -v` 会删除数据库。

本版是单用户本地演示：默认仅监听回环地址，容器端口也只绑定本机。不要直接部署到公网。令牌不是完整的用户认证系统；尚无账号、权限隔离、HTTPS 和限流。数据库最多 2000 个片段，单文件最多 3 MiB，PDF 最多 100 页。

## 验证与实验

```bash
python -m unittest discover -s tests -v
python ai-service/evaluate.py
node --check web/app.js
```

测试覆盖上传、检索出处、接口鉴权、无关问题、非法输入、持久化、去重、删除级联以及空白 PDF 拒绝。实验脚本运行 3 条人工编写问题，计算 Recall@3、MRR@3；只验证流程，不是算法有效性的论文证据。完整实验设计见 `docs/ARCHITECTURE.md`。

## 后续交付计划

| 模块 | 当前状态 |
| --- | --- |
| 离线资料检索与出处闭环 | 已实现并有自动测试 |
| Docker 构建与部署 | 已提供配置，当前环境未实际运行 Docker |
| Vue 3 / Spring Boot / FastAPI / pgvector | 待迁移，本版采用静态网页和 Python 标准库服务 |
| 语义 Embedding、重排与模型生成 | 待实现 |
| 自动实体抽取、完整 GraphRAG | 待实现，已有显式关系对照基线 |
| OCR、图表理解、Word/PPT | 待实现 |
| 出题批改、学习画像、学习路径、Agent | 待实现 |
| 多用户账号与权限隔离 | 待实现 |
| 真实实验集、消融实验与论文材料 | 已给方案，待采集与验证 |

详见 `docs/API.md` 与 `docs/ARCHITECTURE.md`。
